"""Failing test stubs for Phase 15 main.py enhancements.

Tests the --background flag (suppress browser) and is_instance_running().
These functions do not exist yet in app.main — tests are in RED state.
They will be driven GREEN in Plan 03.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Graceful RED: import app.main; individual functions may not exist yet
# ---------------------------------------------------------------------------

try:
    import app.main as _main_module
except ImportError:
    _main_module = None  # type: ignore[assignment]


def _get_fn(name: str):
    """Return named function from app.main or None."""
    if _main_module is None:
        return None
    return getattr(_main_module, name, None)


def _require(name: str):
    """Return function or fail with a clear RED message."""
    fn = _get_fn(name)
    if fn is None:
        pytest.fail(f"app.main.{name} not implemented yet")
    return fn


# ---------------------------------------------------------------------------
# test_background_flag_suppresses_browser
# ---------------------------------------------------------------------------


def test_background_flag_suppresses_browser():
    """When --background is in sys.argv, main() must NOT schedule a browser open.

    RED: app.main.main() has no --background flag handling yet.
    This test verifies that threading.Timer is NOT called when --background is
    set, i.e. no browser-open is scheduled.
    """
    _require("main")  # ensure main exists

    # We must also require that the function inspects sys.argv for --background.
    # Check for the presence of background_mode flag support as a sentinel.
    # If is_instance_running doesn't exist, it's definitely RED for this feature.
    if not hasattr(_main_module, "is_instance_running"):
        pytest.fail(
            "app.main.main() does not support --background flag yet "
            "(is_instance_running not implemented)"
        )

    mock_sock = MagicMock()
    mock_server = MagicMock()
    mock_server.serve = AsyncMock(return_value=None)

    with (
        patch("sys.argv", ["app", "--background"]),
        patch("app.main.webbrowser.open") as mock_browser,
        patch(
            "app.main.find_available_port",
            return_value=(7433, mock_sock),
        ),
        patch("app.main.uvicorn.Server", return_value=mock_server),
        patch("app.main.uvicorn.Config", return_value=MagicMock()),
        patch("app.main.asyncio.run", return_value=None),
        patch("app.main.threading.Timer") as mock_timer,
    ):
        _main_module.main()

    # In --background mode, timer.start() must NOT be called with webbrowser.open
    # The simplest assertion: if a timer was created, its function must not open browser
    if mock_timer.called:
        timer_fn = mock_timer.call_args[0][1]
        # Call it and ensure browser doesn't open
        with patch("app.main.webbrowser.open") as inner_browser:
            timer_fn()
        inner_browser.assert_not_called()
    else:
        # No timer created — browser definitely not opened
        mock_browser.assert_not_called()


# ---------------------------------------------------------------------------
# test_is_instance_running_true
# ---------------------------------------------------------------------------


def test_is_instance_running_true():
    """is_instance_running() returns True when binding raises OSError (port in use)."""
    is_running = _require("is_instance_running")

    mock_sock = MagicMock()
    mock_sock.bind.side_effect = OSError("address already in use")

    with patch("socket.socket", return_value=mock_sock):
        result = is_running()

    assert result is True, f"Expected True (port in use), got {result!r}"


# ---------------------------------------------------------------------------
# test_is_instance_running_false
# ---------------------------------------------------------------------------


def test_is_instance_running_false():
    """is_instance_running() returns False when bind succeeds (no other instance)."""
    is_running = _require("is_instance_running")

    mock_sock = MagicMock()
    mock_sock.bind.return_value = None  # success — no OSError

    with patch("socket.socket", return_value=mock_sock):
        result = is_running()

    assert result is False, f"Expected False (no instance running), got {result!r}"


# ---------------------------------------------------------------------------
# test_main_does_not_reregister_when_already_enabled
# ---------------------------------------------------------------------------


def test_main_does_not_reregister_when_already_enabled():
    """main() must NOT call register_autostart() if autostart is already enabled."""
    mock_sock = MagicMock()
    mock_server = MagicMock()
    mock_server.serve = AsyncMock(return_value=None)
    with (
        patch("sys.argv", ["app"]),
        patch("app.main.is_instance_running", return_value=False),
        patch("app.main.find_available_port", return_value=(7433, mock_sock)),
        patch("app.main.uvicorn.Server", return_value=mock_server),
        patch("app.main.uvicorn.Config", return_value=MagicMock()),
        patch("app.main.asyncio.run", return_value=None),
        patch("app.main.autostart.is_autostart_enabled", return_value=True),
        patch("app.main.autostart.register_autostart") as mock_register,
        patch("app.main.tray.start_tray"),
        patch("app.main.threading.Timer"),
        patch("app.main.webbrowser.open"),
    ):
        from app.main import main

        main()
    mock_register.assert_not_called()
