"""Windows auto-start service via HKCU Run registry key.

Registers, queries, and unregisters the 'Alteryx Git Companion' entry in the
Windows registry Run key so the app launches at login with --background mode.

All winreg imports are DEFERRED inside function bodies so this module is safe
to import on macOS/Linux (e.g. in CI). Platform checks happen before winreg
is imported.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "Alteryx Git Companion"


def _get_exe_path() -> str:
    """Return the quoted executable path with --background flag.

    In a PyInstaller bundle (sys.frozen), use sys.executable directly.
    In development, use 'python -m app.main'.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --background'
    return f'"{sys.executable}" -m app.main --background'


def register_autostart() -> bool:
    """Register the app in HKCU Run key so it launches at login.

    Returns:
        True on success, False if not on Windows or registry write failed.
    """
    if sys.platform != "win32":
        return False
    import winreg  # noqa: PLC0415 (deferred import for cross-platform safety)

    try:
        value = _get_exe_path()
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, value)
        return True
    except OSError as exc:
        logger.warning("Failed to register autostart: %s", exc)
        return False


def is_autostart_enabled() -> bool:
    """Return True if the HKCU Run key entry exists for this app.

    Returns:
        True if key present, False if absent or not on Windows.
    """
    if sys.platform != "win32":
        return False
    import winreg  # noqa: PLC0415

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _APP_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("Failed to check autostart status: %s", exc)
        return False


def unregister_autostart() -> bool:
    """Remove the app from HKCU Run key (idempotent — absent key returns True).

    Returns:
        True on success or if key was already absent, False on unexpected error.
    """
    if sys.platform != "win32":
        return False
    import winreg  # noqa: PLC0415

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _APP_NAME)
        return True
    except FileNotFoundError:
        return True  # already absent — treat as success
    except OSError as exc:
        logger.warning("Failed to unregister autostart: %s", exc)
        return False
