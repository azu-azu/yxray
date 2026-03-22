"""Platform-aware network path detection for watcher observer selection.

Used by WatcherManager.start_watching() to choose between watchdog's
native Observer (local drives) and PollingObserver (network/SMB/UNC paths).
"""

from __future__ import annotations

import os
import platform

DRIVE_REMOTE = 4  # Windows GetDriveType constant — DRIVE_REMOTE


def is_network_path(path: str) -> bool:
    """Return True if path is on a network/SMB/UNC filesystem.

    Detection order:
    1. UNC path check (// or \\\\) — fast, platform-independent
    2. Windows: GetDriveTypeW via ctypes for mapped drives (Z:\\)
    3. macOS: /Volumes/ + st_dev cross-mount check
    4. Linux: /proc/mounts check for cifs/nfs filesystem types
    Falls back to False (local) if detection is inconclusive.
    """
    # Normalize to forward slashes for UNC check
    normalized = path.replace("\\", "/")
    if normalized.startswith("//"):
        return True

    system = platform.system()

    if system == "Windows":
        return _windows_is_network(path)

    if system == "Darwin":
        return _macos_is_network(path)

    if system == "Linux":
        return _linux_is_network(path)

    return False


def _windows_is_network(path: str) -> bool:
    """Check Windows mapped drives via GetDriveTypeW (DRIVE_REMOTE = 4)."""
    try:
        import ctypes

        drive = os.path.splitdrive(path)[0]
        if not drive:
            return False
        root = drive + "\\"
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(root)  # type: ignore[attr-defined]
        return drive_type == DRIVE_REMOTE
    except Exception:
        return False


def _macos_is_network(path: str) -> bool:
    """Detect macOS network mounts via /Volumes/ prefix + st_dev comparison."""
    try:
        # /Volumes/ is where macOS SMB/AFP mounts appear
        if "/Volumes/" in path:
            path_dev = os.stat(path).st_dev
            parent_dev = os.stat(os.path.dirname(path) or "/").st_dev
            return path_dev != parent_dev
    except OSError:
        pass
    return False


def _linux_is_network(path: str) -> bool:
    """Check /proc/mounts for cifs/nfs/smbfs filesystem types."""
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[2].lower() in (
                    "cifs",
                    "nfs",
                    "nfs4",
                    "smbfs",
                ):
                    mount_point = parts[1]
                    if path.startswith(mount_point):
                        return True
    except OSError:
        pass
    return False
