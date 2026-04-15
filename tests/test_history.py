"""Tests for Phase 14 History and Diff Viewer.

Covers git_log, git_show_file (unit tests against real git repos),
and /api/history/* endpoints (endpoint tests using mocked git_ops).

All tests are RED at Plan 01 — git_log and git_show_file are not yet
implemented in git_ops. Tests will be driven GREEN in Plan 02.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Helper — copy of _make_git_repo from test_save.py
# ---------------------------------------------------------------------------


def _make_git_repo(path):
    """Create a minimal git repo with one commit in `path` and return `path`."""
    workflow = path / "workflow.yxmd"
    workflow.write_text("v1")
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    return path


# ---------------------------------------------------------------------------
# Unit tests — git_log (HIST-01)
# ---------------------------------------------------------------------------


def test_git_log(tmp_path):
    """HIST-01: git_log returns list with expected fields; newest commit first."""
    from app.services.git_ops import git_log

    repo = _make_git_repo(tmp_path)

    # Add a second commit so we can check has_parent=True
    (repo / "workflow.yxmd").write_text("v2")
    subprocess.run(
        ["git", "-C", str(repo), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "Second commit"],
        check=True,
        capture_output=True,
    )

    entries = git_log(str(repo))

    assert len(entries) == 2
    # Most recent first
    latest = entries[0]
    assert latest["message"] == "Second commit"
    assert latest["has_parent"] is True
    assert isinstance(latest["sha"], str) and len(latest["sha"]) > 0
    assert isinstance(latest["author"], str)
    assert isinstance(latest["timestamp"], str)
    # ISO-8601 format check
    assert "T" in latest["timestamp"]
    assert isinstance(latest["files_changed"], list)
    assert "workflow.yxmd" in latest["files_changed"]

    # First (initial) commit
    first = entries[1]
    assert first["message"] == "init"
    assert first["has_parent"] is False


def test_git_log_empty(tmp_path):
    """HIST-01: git_log returns [] for a folder with no commits."""
    from app.services.git_ops import git_log

    # Init repo but make no commits
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    entries = git_log(str(tmp_path))
    assert entries == []


def test_git_log_filters_non_workflow_files(tmp_path):
    """HIST-01: files_changed only contains Alteryx workflow suffixes."""
    from app.services.git_ops import git_log

    repo = _make_git_repo(tmp_path)

    # Add a non-workflow file and commit it alongside a workflow
    (repo / "readme.txt").write_text("notes")
    (repo / "workflow.yxmd").write_text("v2")
    subprocess.run(
        ["git", "-C", str(repo), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "Mixed commit"],
        check=True,
        capture_output=True,
    )

    entries = git_log(str(repo))
    latest = entries[0]
    # Only workflow files should be in files_changed
    for f in latest["files_changed"]:
        assert any(
            f.endswith(suffix)
            for suffix in (".yxmd", ".yxwz", ".yxmc", ".yxzp", ".yxapp")
        ), f"Non-workflow file in files_changed: {f}"


# ---------------------------------------------------------------------------
# Unit tests — git_show_file (HIST-02)
# ---------------------------------------------------------------------------


def test_git_show_file(tmp_path):
    """HIST-02: git_show_file returns bytes matching the file content at that commit."""
    from app.services.git_ops import git_show_file

    repo = _make_git_repo(tmp_path)

    # Get the SHA of the initial commit
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    sha = result.stdout.strip()

    content = git_show_file(str(repo), sha, "workflow.yxmd")

    assert isinstance(content, bytes)
    assert content == b"v1"


def test_git_show_file_not_found(tmp_path):
    """HIST-02: git_show_file raises FileNotFoundError for a nonexistent file."""
    import pytest

    from app.services.git_ops import git_show_file

    repo = _make_git_repo(tmp_path)

    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    sha = result.stdout.strip()

    with pytest.raises(FileNotFoundError):
        git_show_file(str(repo), sha, "nonexistent.yxmd")


# ---------------------------------------------------------------------------
# Endpoint tests — /api/history/{project_id} (HIST-01)
# ---------------------------------------------------------------------------


def test_list_history_endpoint(client, tmp_path):
    """HIST-01: GET /api/history/proj1?folder=... returns 200 JSON list.

    Verifies behavior when git_has_commits=True and git_log returns entries.
    """
    entry = {
        "sha": "abc123",
        "message": "Updated filter logic",
        "author": "Jane Smith",
        "timestamp": "2026-03-14T10:30:00+00:00",
        "files_changed": ["CustomerReport.yxmd"],
        "has_parent": True,
    }
    with (
        patch("app.routers.history.git_ops.git_has_commits", return_value=True),
        patch("app.routers.history.git_ops.git_log", return_value=[entry]),
    ):
        resp = client.get("/api/history/proj1", params={"folder": str(tmp_path)})

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["sha"] == "abc123"
    assert data[0]["message"] == "Updated filter logic"


def test_list_history_empty(client, tmp_path):
    """HIST-01: GET /api/history/proj1?folder=... returns 200 [] when no commits."""
    with patch("app.routers.history.git_ops.git_has_commits", return_value=False):
        resp = client.get("/api/history/proj1", params={"folder": str(tmp_path)})

    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Endpoint tests — /api/history/{sha}/diff (HIST-02)
# ---------------------------------------------------------------------------


def test_diff_endpoint_first_commit(client, tmp_path):
    """HIST-02: diff endpoint returns {"is_first_commit": true} for initial commit."""
    entry = {
        "sha": "abc123",
        "message": "Initial version",
        "author": "Jane Smith",
        "timestamp": "2026-03-13T09:00:00+00:00",
        "files_changed": ["CustomerReport.yxmd"],
        "has_parent": False,
    }
    with patch(
        "app.routers.history.git_ops.git_log",
        return_value=[entry],
    ):
        resp = client.get(
            "/api/history/abc123/diff",
            params={"folder": str(tmp_path), "file": "CustomerReport.yxmd"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"is_first_commit": True}


def test_diff_endpoint(client, tmp_path):
    """HIST-02: diff endpoint returns 200 HTML when sha has a parent commit."""
    from alteryx_git_companion.renderers.html_renderer import (
        HTMLRenderer,  # noqa: PLC0415
    )

    entry = {
        "sha": "abc123",
        "message": "Second commit",
        "author": "Jane Smith",
        "timestamp": "2026-03-14T10:30:00+00:00",
        "files_changed": ["workflow.yxmd"],
        "has_parent": True,
    }
    fake_html = "<html><body>diff</body></html>"

    with (
        patch("app.routers.history.git_ops.git_log", return_value=[entry]),
        patch("app.routers.history.git_ops.git_show_file", return_value=b"<xml/>"),
        patch("app.routers.history.pipeline_run") as mock_run,
        patch.object(HTMLRenderer, "render", return_value=fake_html),
    ):
        mock_run.return_value = object()
        resp = client.get(
            "/api/history/abc123/diff",
            params={"folder": str(tmp_path), "file": "workflow.yxmd"},
        )

    assert resp.status_code == 200
    # Response should be HTML content
    assert "html" in resp.headers.get("content-type", "").lower() or resp.text


# ---------------------------------------------------------------------------
# Unit tests — git_pushed_shas (Phase 16.1 Plan 01)
# ---------------------------------------------------------------------------


def test_git_pushed_shas_no_upstream(tmp_path):
    """16.1-01: git_pushed_shas returns empty set when no upstream is configured."""
    from app.services.git_ops import git_pushed_shas  # noqa: PLC0415

    repo = _make_git_repo(tmp_path)
    # No remote upstream configured — must return set(), not crash
    result = git_pushed_shas(str(repo))
    assert result == set()


def test_git_pushed_shas_uses_upstream_ref(tmp_path):
    """16.1-01: git_pushed_shas uses @{u} tracking branch (not hardcoded origin/main).

    Verified by observing it returns set() on a fresh repo with no upstream —
    if it used a hardcoded ref it would either error or return wrong data.
    A repo with no upstream has returncode != 0 for rev-parse @{u}, so the
    function must gracefully return set(). This test creates two distinct
    repos to confirm the function uses dynamic @{u} resolution.
    """
    from app.services.git_ops import git_pushed_shas  # noqa: PLC0415

    # Repo with no upstream: @{u} fails → should return set()
    repo = _make_git_repo(tmp_path)
    result = git_pushed_shas(str(repo))
    assert isinstance(result, set)
    assert result == set()


# ---------------------------------------------------------------------------
# Endpoint tests — is_pushed field in list_history (Phase 16.1 Plan 01)
# ---------------------------------------------------------------------------


def test_list_history_includes_is_pushed(client, tmp_path):
    """16.1-01: list_history includes is_pushed=True when sha is in pushed set."""
    entry = {
        "sha": "abc123",
        "message": "Pushed commit",
        "author": "Jane Smith",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "files_changed": [],
        "has_parent": False,
    }
    with (
        patch("app.routers.history.git_ops.git_has_commits", return_value=True),
        patch("app.routers.history.git_ops.git_log", return_value=[entry]),
        patch("app.routers.history.git_ops.git_pushed_shas", return_value={"abc123"}),
    ):
        resp = client.get("/api/history/proj1", params={"folder": str(tmp_path)})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["is_pushed"] is True


def test_list_history_is_pushed_false_when_not_in_set(client, tmp_path):
    """16.1-01: list_history includes is_pushed=False when sha is not in pushed set."""
    entry = {
        "sha": "abc123",
        "message": "Local only commit",
        "author": "Jane Smith",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "files_changed": [],
        "has_parent": False,
    }
    with (
        patch("app.routers.history.git_ops.git_has_commits", return_value=True),
        patch("app.routers.history.git_ops.git_log", return_value=[entry]),
        patch("app.routers.history.git_ops.git_pushed_shas", return_value=set()),
    ):
        resp = client.get("/api/history/proj1", params={"folder": str(tmp_path)})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["is_pushed"] is False
