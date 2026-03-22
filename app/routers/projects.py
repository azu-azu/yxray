"""Router for /api/projects — CRUD operations for project registration."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import config_store, git_ops
from app.services.watcher_manager import watcher_manager

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectIn(BaseModel):
    path: str


# NOTE: /check must be defined BEFORE /{project_id} so FastAPI resolves it correctly.


@router.get("/check")
def check_project(path: str) -> dict:
    """Pre-flight check used by frontend before calling POST /api/projects.
    Returns {is_git_repo: bool} so the frontend can show a confirmation dialog
    before running git init."""
    return {"is_git_repo": git_ops.is_git_repo(path)}


@router.get("")
def list_projects() -> list:
    """List all registered projects."""
    cfg = config_store.load_config()
    return cfg.get("projects", [])


@router.post("", status_code=201)
def add_project(body: ProjectIn) -> dict:
    """Register a new project folder."""
    p = Path(body.path)
    if not p.exists():
        raise HTTPException(status_code=400, detail="Path does not exist")
    path_str = str(p)
    cfg = config_store.load_config()
    if any(proj["path"] == path_str for proj in cfg.get("projects", [])):
        raise HTTPException(status_code=409, detail="Project already registered")
    if not git_ops.is_git_repo(path_str):
        git_ops.git_init(path_str)
    project = {"id": str(uuid.uuid4()), "path": path_str, "name": p.name}
    cfg.setdefault("projects", []).append(project)
    config_store.save_config(cfg)
    watcher_manager.start_watching(project["id"], path_str)
    return project


@router.delete("/{project_id}")
def remove_project(project_id: str) -> dict:
    """Remove a registered project by ID."""
    cfg = config_store.load_config()
    projects = cfg.get("projects", [])
    match = next((p for p in projects if p["id"] == project_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Project not found")
    cfg["projects"] = [p for p in projects if p["id"] != project_id]
    if cfg.get("active_project") == project_id:
        cfg["active_project"] = None
    config_store.save_config(cfg)
    watcher_manager.stop_watching(project_id)
    return {"removed": project_id}
