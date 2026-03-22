"""History router — list commits and diff endpoints."""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

from alteryx_diff.pipeline import DiffRequest
from alteryx_diff.pipeline import run as pipeline_run
from alteryx_diff.renderers.graph_renderer import GraphRenderer
from alteryx_diff.renderers.html_renderer import HTMLRenderer
from app.services import git_ops  # noqa: F401 — required for mock.patch targeting

router = APIRouter(prefix="/api/history", tags=["history"])


def _run_diff(old_bytes: bytes, new_bytes: bytes, filename: str) -> str:
    """Run ACD pipeline on two byte blobs and return HTML report.

    Uses mkstemp (Windows-safe) — NamedTemporaryFile is not safe on Windows.
    """
    fd_a, path_a = tempfile.mkstemp(suffix=".yxmd")
    fd_b, path_b = tempfile.mkstemp(suffix=".yxmd")
    try:
        os.write(fd_a, old_bytes)
        os.close(fd_a)
        os.write(fd_b, new_bytes)
        os.close(fd_b)
        response = pipeline_run(
            DiffRequest(path_a=pathlib.Path(path_a), path_b=pathlib.Path(path_b))
        )
        graph_html = GraphRenderer().render(
            response.result,
            response.doc_a.connections,
            response.doc_a.nodes,
            response.doc_b.nodes,
        )
        return HTMLRenderer().render(
            response.result,
            file_a=f"{filename} (previous)",
            file_b=f"{filename} (this version)",
            graph_html=graph_html,
        )
    finally:
        os.unlink(path_a)
        os.unlink(path_b)


@router.get("/{project_id}")
def list_history(
    project_id: str,
    folder: str = Query(...),
    branch: str | None = Query(None),
) -> list[dict]:
    """Return commit history for the project folder.

    Returns a list of commit entries with sha, message, author, timestamp,
    files_changed, has_parent, and is_pushed fields.

    Optional ?branch=<name> filters history to that branch.
    """
    if not git_ops.git_has_commits(folder):
        return []
    entries = git_ops.git_log(folder, branch=branch)
    pushed = git_ops.git_pushed_shas(folder)
    for entry in entries:
        entry["is_pushed"] = entry["sha"] in pushed
    return entries


@router.get("/{sha}/diff")
def get_diff(
    sha: str,
    folder: str = Query(...),
    file: str = Query(...),
    compare_to: str | None = Query(None),
) -> object:
    """Return a diff for the given sha and file.

    Returns {"is_first_commit": true} when sha has no parent or when the file
    did not exist in the parent commit (i.e. this is the first version of the file).
    Returns an HTML response when a previous version of the file exists to compare.
    """
    parent_sha = compare_to if compare_to else f"{sha}~1"
    has_parent = (
        subprocess.run(
            ["git", "-C", folder, "rev-parse", "--verify", parent_sha],
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )
    if not has_parent:
        return JSONResponse({"is_first_commit": True})
    try:
        old_bytes = git_ops.git_show_file(folder, parent_sha, file)
    except FileNotFoundError:
        # File didn't exist in the parent — this is the first version of this file
        return JSONResponse({"is_first_commit": True})
    try:
        new_bytes = git_ops.git_show_file(folder, sha, file)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    html = _run_diff(old_bytes, new_bytes, file)
    return HTMLResponse(content=html)
