"""Failing test stubs for Phase 15 autostart service.

These tests are in RED state -- app.services.autostart does not exist yet.
Tests will be driven GREEN in Plan 02.

Import pattern: sys.modules injection for winreg (Windows-only module).
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Graceful RED: if module doesn't exist, stubs return None and tests fail()
# ---------------------------------------------------------------------------

try:
    from app.services import autostart as _autostart_module
except ImportError:
    _autostart_module = None  # type: ignore[assignment]


def _get_fn(name: str):
    """Return the named function from autostart module, or None."""
    if _autostart_module is None:
        return None
    return getattr(_autostart_module, name, None)


def _require(name: str):
    """Return function or fail with a clear RED message."""
    fn = _get_fn(name)
    if fn is None:
        pytest.fail(f"app.services.autostart.{name} not implemented yet")
    return fn


# ---------------------------------------------------------------------------
# Helper: inject a fake winreg into sys.modules so imports inside autostart
# don't blow up on non-Windows. We control return values via the mock attrs.
# ---------------------------------------------------------------------------


def _make_winreg_mock() -> MagicMock:
    mock = MagicMock()
    mock.HKEY_CURRENT_USER = 0x80000001
    mock.KEY_SET_VALUE = 0x0002
    mock.KEY_ALL_ACCESS = 0xF003F
    mock.REG_SZ = 1
    return mock


# ---------------------------------------------------------------------------
# test_register_writes_run_key
# ---------------------------------------------------------------------------


def test_register_writes_run_key():
    """register_autostart() calls SetValueEx with key 'Alteryx Git Companion'
    and a value string that contains '--background'."""
    register = _require("register_autostart")

    winreg_mock = _make_winreg_mock()
    with (
        patch.dict(sys.modules, {"winreg": winreg_mock}),
        patch("sys.platform", "win32"),
    ):
        register()

    # SetValueEx must have been called
    assert winreg_mock.SetValueEx.called, "winreg.SetValueEx was not called"

    # Extract call args: SetValueEx(key, value_name, reserved, type, value)
    call_args = winreg_mock.SetValueEx.call_args
    assert call_args is not None, "SetValueEx call_args is None"
    _key, value_name, _reserved, _reg_type, value_data = call_args[0]

    assert value_name == "Alteryx Git Companion", (
        f"Expected key name 'Alteryx Git Companion', got {value_name!r}"
    )
    assert "--background" in str(value_data), (
        f"Expected '--background' in value data, got {value_data!r}"
    )


# ---------------------------------------------------------------------------
# test_is_enabled_false
# ---------------------------------------------------------------------------


def test_is_enabled_false():
    """is_autostart_enabled() returns False when registry key is absent."""
    is_enabled = _require("is_autostart_enabled")

    winreg_mock = _make_winreg_mock()
    winreg_mock.OpenKey.side_effect = FileNotFoundError("key not found")

    with (
        patch.dict(sys.modules, {"winreg": winreg_mock}),
        patch("sys.platform", "win32"),
    ):
        result = is_enabled()

    assert result is False, f"Expected False, got {result!r}"


# ---------------------------------------------------------------------------
# test_is_enabled_true
# ---------------------------------------------------------------------------


def test_is_enabled_true():
    """is_autostart_enabled() returns True when registry key exists."""
    is_enabled = _require("is_autostart_enabled")

    winreg_mock = _make_winreg_mock()
    winreg_mock.OpenKey.return_value = MagicMock()
    winreg_mock.QueryValueEx.return_value = ("C:\\app.exe --background", 1)

    with (
        patch.dict(sys.modules, {"winreg": winreg_mock}),
        patch("sys.platform", "win32"),
    ):
        result = is_enabled()

    assert result is True, f"Expected True, got {result!r}"


# ---------------------------------------------------------------------------
# test_unregister_removes_key
# ---------------------------------------------------------------------------


def test_unregister_removes_key():
    """unregister_autostart() calls DeleteValue with 'Alteryx Git Companion'."""
    unregister = _require("unregister_autostart")

    winreg_mock = _make_winreg_mock()
    winreg_mock.OpenKey.return_value = MagicMock()

    with (
        patch.dict(sys.modules, {"winreg": winreg_mock}),
        patch("sys.platform", "win32"),
    ):
        unregister()

    assert winreg_mock.DeleteValue.called, "winreg.DeleteValue was not called"
    call_args = winreg_mock.DeleteValue.call_args
    _key, value_name = call_args[0]
    assert value_name == "Alteryx Git Companion", (
        f"Expected 'Alteryx Git Companion', got {value_name!r}"
    )


# ---------------------------------------------------------------------------
# test_unregister_already_absent
# ---------------------------------------------------------------------------


def test_unregister_already_absent():
    """unregister_autostart() returns True when key missing (absent = success)."""
    unregister = _require("unregister_autostart")

    winreg_mock = _make_winreg_mock()
    winreg_mock.OpenKey.side_effect = FileNotFoundError("key not found")

    with (
        patch.dict(sys.modules, {"winreg": winreg_mock}),
        patch("sys.platform", "win32"),
    ):
        result = unregister()

    assert result is True, f"Expected True (absent = success), got {result!r}"


# ---------------------------------------------------------------------------
# test_non_windows_returns_false
# ---------------------------------------------------------------------------


def test_non_windows_returns_false():
    """On non-Windows, register_autostart() and is_autostart_enabled() -> False."""
    register = _require("register_autostart")
    is_enabled = _require("is_autostart_enabled")

    with patch("sys.platform", "linux"):
        reg_result = register()
        enabled_result = is_enabled()

    assert reg_result is False, (
        f"register_autostart() should return False on linux, got {reg_result!r}"
    )
    assert enabled_result is False, (
        f"is_autostart_enabled() should return False on linux, got {enabled_result!r}"
    )
