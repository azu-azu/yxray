"""Settings router -- GET/POST /api/settings for auto-start toggle."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import autostart  # noqa: F401

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsBody(BaseModel):
    launch_on_startup: bool


@router.get("")
def get_settings() -> dict:
    """Return current auto-start setting."""
    return {"launch_on_startup": autostart.is_autostart_enabled()}


@router.post("")
def post_settings(body: SettingsBody) -> dict:
    """Update auto-start setting."""
    if body.launch_on_startup:
        autostart.register_autostart()
    else:
        autostart.unregister_autostart()
    return {"launch_on_startup": autostart.is_autostart_enabled()}
