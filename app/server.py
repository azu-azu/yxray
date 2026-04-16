"""FastAPI app definition: /health endpoint and React StaticFiles mount."""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from app.routers import (
    branch,
    folder_picker,
    git_identity,
    history,
    projects,
    remote,
    save,
    settings,
    watch,
)
from app.services import config_store
from app.services.watcher_manager import watcher_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Start file watchers for all registered projects on server startup.

    Captures the running event loop FIRST (before start_watching) so that
    watchdog daemon threads can push events via loop.call_soon_threadsafe.
    Stops all observers cleanly on shutdown.
    """
    # Startup: capture event loop before start_watching (Pitfall 3 in RESEARCH.md)
    loop = asyncio.get_running_loop()
    watcher_manager.set_event_loop(loop)
    cfg = config_store.load_config()
    for proj in cfg.get("projects", []):
        watcher_manager.start_watching(proj["id"], proj["path"])
    yield
    # Shutdown: stop all observers cleanly (stop_watching uses join(timeout=2))
    for project_id in list(watcher_manager._observers.keys()):
        watcher_manager.stop_watching(project_id)


app = FastAPI(title="Alteryx Git Companion", lifespan=lifespan)

app.include_router(projects.router)
app.include_router(git_identity.router)
app.include_router(folder_picker.router)
app.include_router(watch.router)
app.include_router(save.router)
app.include_router(history.router)
app.include_router(settings.router)
app.include_router(remote.router)
app.include_router(branch.router)


def _static_dir() -> Path:
    """Return the path to the compiled React frontend dist directory.

    - Inside a PyInstaller onefile bundle: uses sys._MEIPASS (the temp
      extraction directory where bundled files are placed at runtime).
    - During development / testing: uses a path relative to this file.
    """
    if getattr(sys, "frozen", False):
        # Running inside a PyInstaller bundle
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).parent
    return base / "frontend" / "dist"


class SPAStaticFiles(StaticFiles):
    """StaticFiles subclass that returns index.html for unknown routes.

    Standard StaticFiles returns 404 for paths not found in the directory.
    For a Single Page Application, unknown routes should fall back to index.html
    so the client-side router can handle them.
    """

    async def get_response(self, path: str, scope: Any) -> Response:
        try:
            return await super().get_response(path, scope)
        except Exception:
            # Fall back to index.html for unknown routes (SPA client-side routing)
            return await super().get_response("index.html", scope)


@app.get("/health")
def health() -> dict[str, str]:
    """Return server health status and application version."""
    return {"status": "ok", "version": version("alteryx-git-companion")}


# Mount the React SPA as a catch-all AFTER all API routes.
# SPAStaticFiles serves index.html for unknown routes (SPA fallback).
# Wrapped in try/except so a missing dist/ dir doesn't crash the server during
# development or unit tests.
try:
    app.mount(
        "/",
        SPAStaticFiles(directory=str(_static_dir()), html=True),
        name="frontend",
    )
except RuntimeError:
    logger.warning(
        "Frontend dist/ directory not found at %s — static files not served. "
        "Run 'make build' to compile the React frontend.",
        _static_dir(),
    )
