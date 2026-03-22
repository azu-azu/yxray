"""Entry point for the Alteryx Git Companion app.

Responsibilities:
- Port probe: find the first available port in 7433–7443 range.
- Single-instance detection: if port 7433 is already bound, another instance
  is running — open browser to it and exit.
- Background mode: --background flag suppresses browser open (used by autostart).
- Autostart registration: writes HKCU Run key on first launch (silent on failure).
- Tray thread: starts system tray icon in a daemon thread alongside uvicorn.
- Uvicorn programmatic start: pass the pre-bound socket to avoid race condition.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import socket
import sys
import threading
import webbrowser

import uvicorn

from app import tray
from app.server import app as fastapi_app
from app.services import autostart


def find_available_port(
    start: int = 7433, count: int = 11
) -> tuple[int, socket.socket]:
    """Return (port, bound_socket) for the first available port in the range.

    The caller MUST pass the returned socket to uvicorn.Config to avoid a race
    condition between probing and binding.

    Args:
        start: First port to try (default 7433).
        count: Number of ports to probe (default 11, covering 7433–7443).

    Raises:
        OSError: If all ports in the range are already in use.
    """
    for port in range(start, start + count):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return port, sock
        except OSError:
            sock.close()
    raise OSError(
        f"All ports {start}–{start + count - 1} are in use. "
        "Close another instance of Alteryx Git Companion and try again."
    )


def is_instance_running() -> bool:
    """Return True if another instance is already running on port 7433.

    Delegates to find_available_port(start=7433, count=1) so that test patches
    on find_available_port propagate correctly. If the port is free the socket
    is closed and False is returned; if all ports (just 7433) are in use an
    OSError is raised by find_available_port and we return True.
    """
    try:
        _, sock = find_available_port(start=7433, count=1)
        sock.close()
        return False
    except OSError:
        return True


def main() -> None:
    """Start the FastAPI server, tray icon, and (optionally) open the browser."""
    background_mode = "--background" in sys.argv

    # Single-instance detection: surface existing instance if already running.
    if is_instance_running():
        if not background_mode:
            webbrowser.open("http://localhost:7433")
        sys.exit(0)

    port, sock = find_available_port()

    # Register autostart silently (Windows only; no-op + warning on failure).
    # Guard: only register if not already enabled — prevents overwriting user's
    # Settings toggle on every manual launch.
    if not autostart.is_autostart_enabled():
        autostart.register_autostart()

    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    # Start tray icon in a daemon thread before the event loop blocks.
    tray_thread = threading.Thread(
        target=tray.start_tray,
        args=(port, server),
        daemon=True,
    )
    tray_thread.start()

    # Open browser only on manual (non-background) launch.
    if not background_mode:
        timer = threading.Timer(
            1.0, lambda: webbrowser.open(f"http://localhost:{port}")
        )
        timer.daemon = True
        timer.start()

    asyncio.run(server.serve(sockets=[sock]))


if __name__ == "__main__":
    # freeze_support() MUST be first — prevents infinite spawn on Windows onefile
    multiprocessing.freeze_support()
    main()
