"""GitLab REST API service — PAT validation and project creation."""

from __future__ import annotations

import re

import httpx

GITLAB_BASE = "https://gitlab.com/api/v4"


def validate_gitlab_token(token: str) -> dict | None:
    """Validate a GitLab PAT via GET /api/v4/user.

    Returns user info dict on success, None if token is invalid (401).
    """
    resp = httpx.get(
        f"{GITLAB_BASE}/user",
        headers={"PRIVATE-TOKEN": token},
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def create_gitlab_project(token: str, name: str) -> dict:
    """POST /api/v4/projects — create a private GitLab project.

    Returns GitLab API response dict with http_url_to_repo, etc.
    """
    resp = httpx.post(
        f"{GITLAB_BASE}/projects",
        headers={"PRIVATE-TOKEN": token},
        json={"name": name, "visibility": "private"},
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# MR helpers
# ---------------------------------------------------------------------------


def parse_gitlab_namespace_path(repo_url: str) -> str:
    """Extract the namespace/project path from a GitLab clone URL.

    Accepts both .git-suffixed and plain HTTPS URLs.
    Raises ValueError if the URL does not match.
    """
    m = re.match(r"https://gitlab\.com/(.+?)(?:\.git)?$", repo_url)
    if not m:
        raise ValueError(f"Cannot parse GitLab URL: {repo_url}")
    return m.group(1)


def get_gitlab_project_id(token: str, namespace_path: str) -> int:
    """GET /projects/{encoded_path} — resolve numeric project ID.

    Encodes the namespace slash as %2F per GitLab API requirements.
    """
    encoded = namespace_path.replace("/", "%2F")
    resp = httpx.get(
        f"{GITLAB_BASE}/projects/{encoded}",
        headers={"PRIVATE-TOKEN": token},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def create_merge_request(
    token: str,
    project_id: int,
    title: str,
    source_branch: str,
    target_branch: str = "main",
    description: str = "",
) -> dict:
    """POST /projects/{project_id}/merge_requests — open a merge request.

    Returns the GitLab API response dict (contains web_url, iid, etc.).
    """
    resp = httpx.post(
        f"{GITLAB_BASE}/projects/{project_id}/merge_requests",
        headers={"PRIVATE-TOKEN": token},
        json={
            "title": title,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "description": description,
        },
    )
    resp.raise_for_status()
    return resp.json()


def get_open_mr_for_branch(token: str, project_id: int, branch: str) -> dict | None:
    """GET /projects/{project_id}/merge_requests?source_branch=X&state=opened.

    Returns the first open MR dict for the branch, or None if none exists.
    """
    resp = httpx.get(
        f"{GITLAB_BASE}/projects/{project_id}/merge_requests",
        headers={"PRIVATE-TOKEN": token},
        params={"source_branch": branch, "state": "opened"},
    )
    resp.raise_for_status()
    items = resp.json()
    return items[0] if items else None
