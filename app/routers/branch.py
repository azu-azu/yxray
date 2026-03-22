"""Branch management router — Phase 17.

Endpoints:
    GET  /api/branch/{project_id}             — list branches
    POST /api/branch/{project_id}/create      — create experiment branch
    POST /api/branch/{project_id}/checkout    — checkout branch (dirty check)
    DELETE /api/branch/{project_id}/delete    — delete branch (main guard)
    GET  /api/branch/{project_id}/merge-base  — merge-base SHA vs main/master
"""

from __future__ import annotations

import datetime
import re
import subprocess

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services import git_ops

router = APIRouter(prefix="/api/branch", tags=["branch"])


class BranchCreateRequest(BaseModel):
    folder: str
    description: str


class BranchCheckoutRequest(BaseModel):
    folder: str
    branch: str


class BranchDeleteRequest(BaseModel):
    folder: str
    branch: str
    force: bool = False


def _format_branch_name(description: str) -> str:
    """Format user description into experiment/YYYY-MM-DD-slug."""
    today = datetime.date.today().isoformat()
    slug = re.sub(r"[^a-z0-9-]+", "-", description.lower().strip()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return f"experiment/{today}-{slug}"


@router.get("/{project_id}")
def list_branches(
    project_id: str,
    folder: str = Query(...),
) -> list[dict]:
    """Return branches for the project folder."""
    return git_ops.git_list_branches(folder)


@router.post("/{project_id}/create")
def create_branch(project_id: str, body: BranchCreateRequest) -> dict:
    """Create a new experiment branch from HEAD."""
    branch_name = _format_branch_name(body.description)
    try:
        git_ops.git_create_branch(body.folder, branch_name)
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "branch_name": branch_name}


@router.post("/{project_id}/checkout")
def checkout_branch(project_id: str, body: BranchCheckoutRequest) -> dict:
    """Checkout a branch; blocked if working tree is dirty."""
    changed = git_ops.git_changed_workflows(body.folder)
    if changed:
        return {
            "success": False,
            "error": f"Save changes before switching ({len(changed)} files)",
        }
    result = git_ops.git_checkout(body.folder, body.branch)
    return result if result is not None else {"success": True}


@router.delete("/{project_id}/delete")
def delete_branch(project_id: str, body: BranchDeleteRequest) -> dict:
    """Delete a branch; blocked for protected branch names."""
    if body.branch in ("main", "master"):
        return {"success": False, "error": "Cannot delete main branch"}
    result = git_ops.git_delete_branch(body.folder, body.branch, force=body.force)
    return result if result is not None else {"success": True}


@router.get("/{project_id}/merge-base")
def get_merge_base(
    project_id: str,
    folder: str = Query(...),
    branch: str = Query(...),
) -> dict:
    """Return the SHA where `branch` diverged from main/master.

    Returns {"merge_base_sha": "abc123"} or {"merge_base_sha": null}.
    """
    for base in ("main", "master"):
        result = subprocess.run(
            ["git", "-C", folder, "merge-base", branch, base],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return {"merge_base_sha": result.stdout.strip()}
    return {"merge_base_sha": None}
