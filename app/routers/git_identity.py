"""Router for /api/git/identity — global git user configuration."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

import app.services.git_ops as git_ops_svc

router = APIRouter(prefix="/api/git/identity", tags=["git"])


class IdentityIn(BaseModel):
    name: str
    email: str


@router.get("")
def get_identity() -> dict:
    """Get the current global git user.name and user.email."""
    return git_ops_svc.get_git_identity()


@router.post("")
def set_identity(body: IdentityIn) -> dict:
    """Set global git user.name and user.email."""
    git_ops_svc.set_git_identity(body.name, body.email)
    return {"ok": True}
