"""Failing test stubs for Phase 15 settings router.

Tests GET /api/settings and POST /api/settings endpoints.
app.routers.settings does not exist yet -- tests are in RED state.
They will be driven GREEN in Plan 03.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Graceful RED: wrap import so tests report FAILED not collection ERROR
# ---------------------------------------------------------------------------

try:
    from starlette.testclient import TestClient

    from app.routers import settings as _settings_module  # noqa: F401
    from app.server import app as _fastapi_app

    _client = TestClient(_fastapi_app)
    _settings_imported = True
except (ImportError, AttributeError):
    _settings_imported = False
    _client = None  # type: ignore[assignment]


def _require_settings():
    """Fail clearly if settings router not yet implemented."""
    if not _settings_imported:
        pytest.fail("app.routers.settings not implemented yet")


# ---------------------------------------------------------------------------
# test_get_settings_returns_enabled_state
# ---------------------------------------------------------------------------


def test_get_settings_returns_enabled_state():
    """GET /api/settings returns 200 {"launch_on_startup": True} when enabled."""
    _require_settings()

    with patch(
        "app.routers.settings.autostart.is_autostart_enabled", return_value=True
    ):
        resp = _client.get("/api/settings")

    assert resp.status_code == 200
    data = resp.json()
    assert data == {"launch_on_startup": True}, (
        f"Expected {{'launch_on_startup': True}}, got {data}"
    )


# ---------------------------------------------------------------------------
# test_get_settings_returns_disabled_state
# ---------------------------------------------------------------------------


def test_get_settings_returns_disabled_state():
    """GET /api/settings returns {"launch_on_startup": False} when disabled."""
    _require_settings()

    with patch(
        "app.routers.settings.autostart.is_autostart_enabled", return_value=False
    ):
        resp = _client.get("/api/settings")

    assert resp.status_code == 200
    data = resp.json()
    assert data == {"launch_on_startup": False}, (
        f"Expected {{'launch_on_startup': False}}, got {data}"
    )


# ---------------------------------------------------------------------------
# test_post_settings_enable
# ---------------------------------------------------------------------------


def test_post_settings_enable():
    """POST /api/settings {"launch_on_startup": true} calls register_autostart()."""
    _require_settings()

    with (
        patch(
            "app.routers.settings.autostart.register_autostart", return_value=True
        ) as mock_register,
        patch("app.routers.settings.autostart.unregister_autostart") as mock_unregister,
    ):
        resp = _client.post("/api/settings", json={"launch_on_startup": True})

    assert resp.status_code == 200
    mock_register.assert_called_once()
    mock_unregister.assert_not_called()


# ---------------------------------------------------------------------------
# test_post_settings_disable
# ---------------------------------------------------------------------------


def test_post_settings_disable():
    """POST /api/settings {"launch_on_startup": false} calls unregister_autostart()."""
    _require_settings()

    with (
        patch(
            "app.routers.settings.autostart.unregister_autostart", return_value=True
        ) as mock_unregister,
        patch("app.routers.settings.autostart.register_autostart") as mock_register,
    ):
        resp = _client.post("/api/settings", json={"launch_on_startup": False})

    assert resp.status_code == 200
    mock_unregister.assert_called_once()
    mock_register.assert_not_called()
