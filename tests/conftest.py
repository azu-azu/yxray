"""Shared pytest fixtures for app tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI TestClient fixture with _static_dir() patched to a temp dir.

    Creates a minimal index.html in the temp dir so StaticFiles mounts without
    errors, allowing /health and other routes to be tested in isolation.
    """
    # Create a minimal index.html in the temp static dir
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<!DOCTYPE html><html></html>")

    # Patch _static_dir in app.server to return our temp dir
    import app.server as server_module

    monkeypatch.setattr(server_module, "_static_dir", lambda: dist)

    # Re-mount static files with patched dir
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from app.server import app

    # Remove existing static mount if present, then re-add with temp path
    # (StaticFiles is already mounted at app creation time, so we patch before import)
    # The monkeypatch above patches _static_dir but the mount already happened —
    # we need to provide a fresh app instance for tests.
    test_app = FastAPI()

    # Copy routes from the real app
    for route in app.routes:
        if not hasattr(route, "methods"):
            # It's a Mount (static files) — skip it; we'll add our own
            continue
        test_app.routes.append(route)

    # Add static files mount pointing at temp dir
    test_app.mount(
        "/",
        StaticFiles(directory=str(dist), html=True),
        name="frontend",
    )

    yield TestClient(test_app)
