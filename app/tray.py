"""System tray icon module for Alteryx Git Companion.

Provides:
  - _compute_state(status_data: dict) -> (str, str): pure function for state/tooltip
  - TrayIcon: wraps pystray.Icon with polling loop and menu
  - start_tray(port, server): entry point called from main()

pystray is guarded by try/except so unit tests run on macOS CI without it.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
import webbrowser
from pathlib import Path

try:
    import pystray
    from pystray import MenuItem as PystrayMenuItem

    PYSTRAY_AVAILABLE = True
except ImportError:
    pystray = None  # type: ignore[assignment]
    PystrayMenuItem = None  # type: ignore[assignment]
    PYSTRAY_AVAILABLE = False

try:
    import requests as _requests

    _REQUESTS_AVAILABLE = True
except ImportError:
    _requests = None  # type: ignore[assignment]
    _REQUESTS_AVAILABLE = False

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

_APP_NAME = "Alteryx Git Companion"


def _compute_state(status_data: dict) -> tuple[str, str]:
    """Compute tray icon state and tooltip from watch status data.

    Args:
        status_data: Mapping of project_id -> {"changed_count": int, ...}.
                     Empty dict means no projects are being watched.

    Returns:
        (state, tooltip) where state is "idle" | "watching" | "changes".
    """
    total_changes = sum(v.get("changed_count", 0) for v in status_data.values())
    any_watching = bool(status_data)

    if total_changes > 0:
        word = "change" if total_changes == 1 else "changes"
        return (
            "changes",
            f"{_APP_NAME} \u2014 {total_changes} {word} detected",
        )
    elif any_watching:
        return ("watching", f"{_APP_NAME} \u2014 watching")
    else:
        return ("idle", _APP_NAME)


def _get_asset_path(filename: str) -> Path:
    """Return path to an asset file, supporting PyInstaller bundles.

    Inside a PyInstaller onefile bundle: uses sys._MEIPASS.
    During development / testing: uses a path relative to this file.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).parent.parent
    return base / "assets" / filename


def _make_icon_image(color: tuple[int, int, int, int], letter: str) -> Image.Image:
    """Generate a 64x64 RGBA icon with a colored background and a letter."""
    img = Image.new("RGBA", (64, 64), color)
    draw = ImageDraw.Draw(img)
    draw.text((26, 18), letter, fill=(255, 255, 255, 255))
    return img


class TrayIcon:
    """System tray icon that polls /api/watch/status and updates icon/tooltip.

    Attributes:
        port: The port uvicorn is listening on.
        server: The uvicorn.Server instance for graceful shutdown.
    """

    def __init__(self, port: int, server: object) -> None:
        self.port = port
        self.server = server
        self._img_idle = self._load_image("icon.ico")
        self._img_watching = self._load_image("icon-watching.ico")
        self._img_changes = self._load_image("icon-changes.ico")

    def _load_image(self, name: str) -> Image.Image:
        """Load a PIL Image from assets, falling back to programmatic generation."""
        path = _get_asset_path(name)
        if path.exists():
            try:
                return Image.open(path).convert("RGBA")
            except Exception:
                logger.warning("Failed to open icon %s, using fallback", path)

        # Programmatic fallbacks
        if name == "icon-watching.ico":
            return _make_icon_image((34, 197, 94, 255), "W")
        elif name == "icon-changes.ico":
            return _make_icon_image((245, 158, 11, 255), "!")
        else:
            # idle: white square
            return Image.new("RGBA", (64, 64), (255, 255, 255, 255))

    def _get_status_data(self) -> dict:
        """Fetch /api/watch/status from the local server."""
        if not _REQUESTS_AVAILABLE:
            return {}
        try:
            resp = _requests.get(
                f"http://localhost:{self.port}/api/watch/status", timeout=3
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {}

    def _poll_loop(self, icon: object) -> None:
        """Background polling loop: update icon and tooltip every 5 seconds."""
        while getattr(icon, "visible", False):
            status_data = self._get_status_data()
            state, tooltip = _compute_state(status_data)

            if state == "changes":
                img = self._img_changes
            elif state == "watching":
                img = self._img_watching
            else:
                img = self._img_idle

            icon.icon = img  # type: ignore[union-attr]
            icon.title = tooltip  # type: ignore[union-attr]
            time.sleep(5)

    def _setup(self, icon: object) -> None:
        """Called by pystray after the icon is shown; starts the polling thread."""
        t = threading.Thread(target=self._poll_loop, args=(icon,), daemon=True)
        t.start()

    def run(self) -> None:
        """Build the pystray.Icon and run it (blocking call)."""
        if not PYSTRAY_AVAILABLE:
            logger.warning("pystray not available -- tray icon disabled")
            return

        def on_open(icon: object, item: object) -> None:  # noqa: ARG001
            webbrowser.open(f"http://localhost:{self.port}")

        def on_quit(icon: object, item: object) -> None:  # noqa: ARG001
            icon.stop()  # type: ignore[union-attr]
            self.server.should_exit = True  # type: ignore[union-attr]

        menu = pystray.Menu(
            PystrayMenuItem("Open Alteryx Git Companion", on_open, default=True),
            PystrayMenuItem("Quit", on_quit),
        )
        icon = pystray.Icon(
            _APP_NAME,
            self._img_idle,
            _APP_NAME,
            menu,
        )
        icon.run(setup=self._setup)


def start_tray(port: int, server: object) -> None:
    """Entry point: create TrayIcon and run it (blocking).

    Intended to be called from a daemon thread by main().
    """
    t = TrayIcon(port, server)
    t.run()


if __name__ == "__main__":
    # Generate placeholder icon files if they don't exist.
    assets_dir = Path(__file__).parent.parent / "assets"
    assets_dir.mkdir(exist_ok=True)

    watching_path = assets_dir / "icon-watching.ico"
    if not watching_path.exists():
        img = _make_icon_image((34, 197, 94, 255), "W")
        img.save(str(watching_path))
        print(f"Generated {watching_path}")

    changes_path = assets_dir / "icon-changes.ico"
    if not changes_path.exists():
        img2 = _make_icon_image((245, 158, 11, 255), "!")
        img2.save(str(changes_path))
        print(f"Generated {changes_path}")
