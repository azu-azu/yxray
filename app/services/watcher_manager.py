"""WatcherManager: central orchestrator for watchdog observer lifecycles.

Manages file-system watchers for Alteryx workflow files
(.yxmd, .yxwz, .yxmc, .yxzp, .yxapp),
debounces file events, runs git status rescans, and pushes badge_update
events to SSE subscriber queues.

Thread-boundary bridge: watchdog daemon threads push to asyncio queues via
loop.call_soon_threadsafe — never call q.put_nowait() directly from a
watchdog thread.

Usage:
    from app.services.watcher_manager import watcher_manager

    # In FastAPI lifespan (before start_watching):
    watcher_manager.set_event_loop(asyncio.get_event_loop())
    watcher_manager.start_watching(project_id, path)
"""

import asyncio
import contextlib
import logging
import threading

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from app.services.git_ops import count_workflows, git_changed_workflows, git_has_commits
from app.services.watcher_utils import is_network_path

logger = logging.getLogger(__name__)

POLL_TIMEOUT_SECONDS = 5
DEBOUNCE_SECONDS = 1.5


class _WorkflowEventHandler(PatternMatchingEventHandler):
    """Watchdog handler that triggers a debounced rescan on any workflow file event.

    Uses on_any_event (not on_modified) to catch Alteryx's temp-file-rename
    save pattern, which emits a created event for the final workflow file.
    """

    def __init__(
        self,
        project_id: str,
        path: str,
        on_change: object,
    ) -> None:
        super().__init__(
            patterns=["*.yxmd", "*.yxwz", "*.yxmc", "*.yxzp", "*.yxapp"],
            ignore_patterns=["*.tmp", "~*"],
            ignore_directories=True,
            case_sensitive=False,
        )
        self._project_id = project_id
        self._path = path
        self._on_change = on_change

    def on_any_event(self, event: object) -> None:
        self._on_change(self._project_id, self._path)


class WatcherManager:
    """Singleton-style manager for watchdog observers across multiple projects.

    IMPORTANT: Call set_event_loop() BEFORE start_watching() in the FastAPI
    lifespan so the asyncio loop is ready when the first file event fires.
    """

    def __init__(self) -> None:
        self._observers: dict[str, Observer | PollingObserver] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._change_counts: dict[str, int] = {}
        self._total_workflows: dict[str, int] = {}
        self._subscribers: list[asyncio.Queue] = []
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the asyncio event loop to use for thread-safe queue pushes.

        Must be called before start_watching(). Typically called once in
        the FastAPI lifespan with asyncio.get_event_loop().
        """
        self._loop = loop

    def start_watching(self, project_id: str, path: str) -> None:
        """Start watching *path* for workflow file changes.

        Idempotent: returns immediately if already watching *project_id*.
        Selects PollingObserver(timeout=5) for network/UNC paths and the
        native Observer for local paths.

        Also triggers an initial _rescan to populate badge state.
        """
        if project_id in self._observers:
            logger.debug("Already watching project %s — skipping", project_id)
            return

        handler = _WorkflowEventHandler(
            project_id=project_id,
            path=path,
            on_change=self._schedule_rescan,
        )

        if is_network_path(path):
            observer: Observer | PollingObserver = PollingObserver(
                timeout=POLL_TIMEOUT_SECONDS
            )
        else:
            observer = Observer()

        observer.schedule(handler, path, recursive=True)
        observer.start()
        self._observers[project_id] = observer

        # Initial badge state
        self._rescan(project_id, path)

    def stop_watching(self, project_id: str) -> None:
        """Stop the observer for *project_id* and clean up all state."""
        observer = self._observers.pop(project_id, None)
        if observer is not None:
            observer.stop()
            observer.join(timeout=2)
            if observer.is_alive():
                logger.warning(
                    "Observer for project %s did not stop within timeout — "
                    "possible dead network share",
                    project_id,
                )

        # Cancel any pending debounce timer
        timer = self._timers.pop(project_id, None)
        if timer is not None:
            timer.cancel()

        self._change_counts.pop(project_id, None)
        self._total_workflows.pop(project_id, None)

    def subscribe(self) -> asyncio.Queue:
        """Return a new asyncio.Queue that will receive badge_update events."""
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove *q* from the subscriber list (no-op if already removed)."""
        with self._lock, contextlib.suppress(ValueError):
            self._subscribers.remove(q)

    def clear_count(self, project_id: str) -> None:
        """Zero the change count for *project_id* and push an SSE event.

        Called by Phase 13 after a successful git commit so the badge resets.
        """
        self._change_counts[project_id] = 0
        self._push_badge_update(project_id, 0)

    def get_status(self) -> dict:
        """Return badge status for all configured projects.

        Lazy-imports config_store to avoid circular imports at module load time.
        """
        from app.services.config_store import load_config  # noqa: PLC0415

        config = load_config()
        result = {}
        for project in config.get("projects", []):
            pid = project["id"]
            path = project["path"]
            result[pid] = {
                "changed_count": self._change_counts.get(pid, 0),
                "total_workflows": self._total_workflows.get(pid, 0),
                "has_any_commits": git_has_commits(path),
            }
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _schedule_rescan(self, project_id: str, path: str) -> None:
        """Debounce file events: cancel any pending timer, start a fresh one."""
        existing = self._timers.get(project_id)
        if existing is not None:
            existing.cancel()

        timer = threading.Timer(
            DEBOUNCE_SECONDS,
            self._rescan,
            args=(project_id, path),
        )
        timer.daemon = True
        timer.start()
        self._timers[project_id] = timer

    def _rescan(self, project_id: str, path: str) -> None:
        """Run git status and update badge counts, then push SSE event."""
        changed = git_changed_workflows(path)
        total = count_workflows(path)
        count = len(changed)

        self._change_counts[project_id] = count
        self._total_workflows[project_id] = total

        self._push_badge_update(project_id, count)

    def _push_badge_update(self, project_id: str, count: int) -> None:
        """Push a badge_update event to all subscriber queues.

        Uses loop.call_soon_threadsafe so it is safe to call from a watchdog
        daemon thread. Iterates a snapshot of _subscribers to avoid mutation
        during iteration.
        """
        if self._loop is None:
            logger.warning(
                "No event loop set — cannot push badge_update for %s. "
                "Call set_event_loop() before start_watching().",
                project_id,
            )
            return

        event = {
            "type": "badge_update",
            "project_id": project_id,
            "changed_count": count,
        }

        for q in list(self._subscribers):
            self._loop.call_soon_threadsafe(q.put_nowait, event)


# Module-level singleton — import this throughout the application
watcher_manager = WatcherManager()
