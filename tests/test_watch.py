"""Wave 0 test scaffold for Phase 12 file-watcher helpers.

Tests cover:
  WATCH-01: git_changed_workflows, count_workflows (badge refresh triggers)
  WATCH-02: is_network_path (PollingObserver selection)
  WATCH-03: git_has_commits (no-commits guard on first watch)

Imports are intentionally bare (no try/except) — the ImportError is the RED
state for all non-skipped tests until Task 2 creates the modules.
"""

import asyncio
import subprocess
from unittest.mock import MagicMock, patch

from app.services.git_ops import count_workflows, git_changed_workflows, git_has_commits
from app.services.watcher_utils import is_network_path

# ---------------------------------------------------------------------------
# WATCH-01: git_changed_workflows
# ---------------------------------------------------------------------------


def test_git_changed_workflows(tmp_path):
    """git_changed_workflows returns Alteryx workflow filenames; excludes others."""
    # Set up a real git repo with one committed .yxmd file
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create and commit a .yxmd file so it's in git history
    committed_yxmd = tmp_path / "analysis.yxmd"
    committed_yxmd.write_text("<root/>")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Modify the committed .yxmd (unstaged modification)
    committed_yxmd.write_text("<root updated/>")

    # Add an untracked new .yxwz file
    new_yxwz = tmp_path / "pipeline.yxwz"
    new_yxwz.write_text("<root/>")

    # Add a .yxmc macro (should appear — it's a workflow type)
    new_yxmc = tmp_path / "macro.yxmc"
    new_yxmc.write_text("<root/>")

    # Add files that should NOT appear in results
    (tmp_path / "notes.txt").write_text("irrelevant")

    result = git_changed_workflows(str(tmp_path))

    assert isinstance(result, list)
    filenames = [r.split("/")[-1] if "/" in r else r for r in result]
    assert "analysis.yxmd" in filenames
    assert "pipeline.yxwz" in filenames
    assert "macro.yxmc" in filenames
    assert not any(f.endswith(".txt") for f in result)


# ---------------------------------------------------------------------------
# WATCH-01: count_workflows
# ---------------------------------------------------------------------------


def test_count_workflows(tmp_path):
    """count_workflows counts all Alteryx workflow file types recursively."""
    (tmp_path / "a.yxmd").write_text("<root/>")
    (tmp_path / "b.yxmd").write_text("<root/>")
    (tmp_path / "c.yxwz").write_text("<root/>")
    (tmp_path / "d.yxmc").write_text("<root/>")
    (tmp_path / "e.yxzp").write_text("<root/>")
    (tmp_path / "f.yxapp").write_text("<root/>")
    (tmp_path / "readme.txt").write_text("ignore me")
    # Subdirectory files ARE counted (recursive)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "g.yxmd").write_text("<root/>")

    assert count_workflows(str(tmp_path)) == 7


# ---------------------------------------------------------------------------
# WATCH-03: git_has_commits
# ---------------------------------------------------------------------------


def test_git_has_commits_false(tmp_path):
    """git_has_commits returns False for a freshly git-init-ed repo with no commits."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    assert git_has_commits(str(tmp_path)) is False


def test_git_has_commits_true(tmp_path):
    """git_has_commits returns True when at least one commit exists."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "file.txt").write_text("content")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    assert git_has_commits(str(tmp_path)) is True


# ---------------------------------------------------------------------------
# WATCH-02: is_network_path
# ---------------------------------------------------------------------------


def test_is_network_path_unc_backslash():
    """is_network_path returns True for UNC backslash paths."""
    assert is_network_path("\\\\server\\share\\workflows") is True


def test_is_network_path_unc_forward():
    """is_network_path returns True for UNC forward-slash paths."""
    assert is_network_path("//server/share/workflows") is True


def test_is_network_path_local_unix():
    """is_network_path returns False for standard Unix absolute paths."""
    assert is_network_path("/home/user/workflows") is False


# ---------------------------------------------------------------------------
# WATCH-01/02: WatcherManager stubs (Plan 02)
# ---------------------------------------------------------------------------


def test_badge_push_on_rescan():
    """WatcherManager emits SSE badge event after _rescan completes."""
    from app.services.watcher_manager import WatcherManager

    mgr = WatcherManager()
    loop = asyncio.new_event_loop()
    mgr.set_event_loop(loop)
    q = mgr.subscribe()
    with (
        patch(
            "app.services.watcher_manager.git_changed_workflows",
            return_value=["workflow.yxmd"],
        ),
        patch("app.services.watcher_manager.count_workflows", return_value=5),
    ):
        mgr._rescan("proj-1", "/tmp/proj")
    # Drain the queue synchronously
    event = loop.run_until_complete(q.get())
    loop.close()
    assert event["type"] == "badge_update"
    assert event["project_id"] == "proj-1"
    assert event["changed_count"] == 1


def test_polling_observer_for_network():
    """WatcherManager uses PollingObserver when is_network_path returns True."""
    from app.services.watcher_manager import WatcherManager

    mgr = WatcherManager()
    with (
        patch("app.services.watcher_manager.is_network_path", return_value=True),
        patch("app.services.watcher_manager.PollingObserver") as MockPoll,
        patch("app.services.watcher_manager.Observer") as MockObs,
        patch(
            "app.services.watcher_manager.git_changed_workflows",
            return_value=[],
        ),
        patch("app.services.watcher_manager.count_workflows", return_value=0),
    ):
        mock_obs_instance = MagicMock()
        MockPoll.return_value = mock_obs_instance
        mgr.set_event_loop(asyncio.new_event_loop())
        mgr.start_watching("proj-1", "//server/share")
        MockPoll.assert_called_once_with(timeout=5)
        MockObs.assert_not_called()


# ---------------------------------------------------------------------------
# WATCH-01/03: Integration stubs (Plan 03 — requires running server)
# ---------------------------------------------------------------------------


def test_sse_endpoint_headers():
    """GET /api/watch/events must return 200 with text/event-stream content-type.

    Calls the route handler directly (no HTTP transport) to check the
    EventSourceResponse object's status_code and media_type. This avoids the
    known issue where TestClient.stream() blocks until the SSE stream ends
    (which is never for an infinite generator).
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.routers.watch import watch_events

    # is_disconnected returns True on the first check to make the generator exit
    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=True)

    async def _test():
        with (
            patch(
                "app.routers.watch.watcher_manager.subscribe",
                return_value=asyncio.Queue(),
            ),
            patch("app.routers.watch.watcher_manager.unsubscribe"),
        ):
            response = await watch_events(request=mock_request)
        assert response.status_code == 200
        assert "text/event-stream" in (response.media_type or "")

    asyncio.run(_test())


def test_watch_status_no_commits():
    """GET /api/watch/status returns has_any_commits: False for repo with no commits."""
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from app.server import app

    client = TestClient(app)
    mock_status = {
        "proj-1": {"changed_count": 0, "total_workflows": 3, "has_any_commits": False}
    }
    with patch(
        "app.routers.watch.watcher_manager.get_status", return_value=mock_status
    ):
        r = client.get("/api/watch/status")
    assert r.status_code == 200
    data = r.json()
    assert data["proj-1"]["has_any_commits"] is False


def test_watch_status_total_workflows():
    """GET /api/watch/status returns total_workflows matching filesystem count."""
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from app.server import app

    client = TestClient(app)
    mock_status = {
        "proj-1": {"changed_count": 2, "total_workflows": 5, "has_any_commits": True}
    }
    with patch(
        "app.routers.watch.watcher_manager.get_status", return_value=mock_status
    ):
        r = client.get("/api/watch/status")
    assert r.status_code == 200
    assert r.json()["proj-1"]["total_workflows"] == 5
