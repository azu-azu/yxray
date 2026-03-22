"""Save version router — commit, undo, and discard endpoints."""

from __future__ import annotations

import subprocess

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import git_ops
from app.services.watcher_manager import watcher_manager

router = APIRouter(prefix="/api/save", tags=["save"])


class CommitBody(BaseModel):
    project_id: str
    folder: str
    files: list[str]
    message: str


class UndoBody(BaseModel):
    project_id: str
    folder: str


class DiscardBody(BaseModel):
    project_id: str
    folder: str
    files: list[str]


@router.post("/commit")
def commit_version(body: CommitBody) -> dict:
    """Stage selected files and create a git commit. Clears the change badge via SSE."""
    if not body.files:
        raise HTTPException(status_code=400, detail="files list must not be empty")
    if not git_ops.is_git_repo(body.folder):
        git_ops.git_init(body.folder)
    try:
        git_ops.git_commit_files(body.folder, body.files, body.message)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=str(exc.stderr)) from exc
    watcher_manager.clear_count(body.project_id)
    return {"ok": True}


@router.post("/undo")
def undo_last_version(body: UndoBody) -> dict:
    """Soft-reset the last commit.

    Returns has_any_commits so frontend can update state.
    """
    try:
        git_ops.git_undo_last_commit(body.folder)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            status_code=400, detail="Nothing to undo — no parent commit exists"
        ) from exc
    has_commits = git_ops.git_has_commits(body.folder)
    # After undo, files are back in changed state — trigger watcher rescan via badge
    # The watcher will re-detect changes on next scan; no manual SSE push needed here.
    return {"ok": True, "has_any_commits": has_commits}


@router.post("/discard")
def discard_changes(body: DiscardBody) -> dict:
    """Copy checked files to .acd-backup then restore to HEAD. Clears badge via SSE."""
    if not body.files:
        raise HTTPException(status_code=400, detail="files list must not be empty")
    try:
        git_ops.git_discard_files(body.folder, body.files)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=str(exc.stderr)) from exc
    watcher_manager.clear_count(body.project_id)
    return {"ok": True}
