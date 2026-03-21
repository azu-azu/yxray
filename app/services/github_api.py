"""GitHub REST API service — repo creation, user info, collision resolution."""

from __future__ import annotations

import re

import httpx

GITHUB_API_BASE = "https://api.github.com"


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def slugify_folder_name(name: str) -> str:
    """Convert a folder name to a URL-safe slug.

    Uses only lowercase alphanumerics and hyphens.
    Falls back to 'my-workflows' for empty input.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower())
    return slug.strip("-") or "my-workflows"


def get_github_username(token: str) -> str:
    """GET /user — resolve the authenticated user's login name."""
    resp = httpx.get(
        f"{GITHUB_API_BASE}/user",
        headers=_github_headers(token),
    )
    resp.raise_for_status()
    return resp.json()["login"]


def github_repo_exists(token: str, owner: str, repo_name: str) -> bool:
    """Return True if the repo owner/repo_name exists on GitHub."""
    resp = httpx.get(
        f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}",
        headers=_github_headers(token),
    )
    return resp.status_code == 200


def create_github_repo(token: str, name: str) -> dict:
    """POST /user/repos — create a private repo.

    Returns GitHub API response dict with clone_url, html_url, etc.
    """
    resp = httpx.post(
        f"{GITHUB_API_BASE}/user/repos",
        headers=_github_headers(token),
        json={"name": name, "private": True, "auto_init": False},
    )
    resp.raise_for_status()
    return resp.json()


def find_available_repo_name(token: str, owner: str, base_slug: str) -> str:
    """Find a non-colliding repo name by appending -2, -3, etc. as needed."""
    candidate = base_slug
    suffix = 2
    while github_repo_exists(token, owner, candidate):
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
    return candidate


# ---------------------------------------------------------------------------
# PR helpers
# ---------------------------------------------------------------------------


def parse_github_owner_repo(repo_url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub clone URL.

    Accepts both .git-suffixed and plain HTTPS URLs.
    Raises ValueError if the URL does not match.
    """
    m = re.match(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
    if not m:
        raise ValueError(f"Cannot parse GitHub URL: {repo_url}")
    return m.group(1), m.group(2)


def create_pull_request(
    token: str,
    owner: str,
    repo: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
) -> dict:
    """POST /repos/{owner}/{repo}/pulls — open a pull request.

    Returns the GitHub API response dict (contains html_url, number, etc.).
    """
    resp = httpx.post(
        f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls",
        headers=_github_headers(token),
        json={"title": title, "head": head, "base": base, "body": body},
    )
    resp.raise_for_status()
    return resp.json()


def get_open_pr_for_branch(
    token: str, owner: str, repo: str, branch: str
) -> dict | None:
    """GET /repos/{owner}/{repo}/pulls?head=owner:branch&state=open.

    Returns the first open PR dict for the branch, or None if none exists.
    """
    resp = httpx.get(
        f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls",
        headers=_github_headers(token),
        params={"head": f"{owner}:{branch}", "state": "open"},
    )
    resp.raise_for_status()
    items = resp.json()
    return items[0] if items else None
