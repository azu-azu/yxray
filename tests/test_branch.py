"""RED test suite for Phase 17 — Branch Management.

All tests are RED state: endpoints raise NotImplementedError.
Covers BRANCH-01 (list/create), BRANCH-02 (checkout), BRANCH-03 (delete/merge-base).
Tests will be driven GREEN in Plans 17-02 and 17-03.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Graceful RED: wrap imports so tests report FAILED not collection ERROR
# ---------------------------------------------------------------------------

try:
    from starlette.testclient import TestClient

    from app.routers import branch as _branch_module  # noqa: F401
    from app.server import app as _fastapi_app

    _client = TestClient(_fastapi_app)
    _branch_imported = True
except (ImportError, AttributeError):
    _branch_imported = False
    _client = None  # type: ignore[assignment]


def _require_branch():
    if not _branch_imported:
        pytest.fail("app.routers.branch not implemented yet")


# ---------------------------------------------------------------------------
# BRANCH-01: List branches
# ---------------------------------------------------------------------------


def test_git_list_branches():
    """GET /api/branch/{id}?folder=... returns [{name, is_current}]."""
    _require_branch()
    mock_branches = [
        {"name": "main", "is_current": True},
        {"name": "experiment/2026-03-10-price-test", "is_current": False},
    ]
    with patch("app.routers.branch.git_ops") as mock_git_ops:
        mock_git_ops.git_list_branches.return_value = mock_branches
        response = _client.get("/api/branch/proj1?folder=/some/folder")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "main"
    assert data[0]["is_current"] is True


def test_list_branches_endpoint():
    """Integration call — checks response is a list."""
    _require_branch()
    with patch("app.routers.branch.git_ops") as mock_git_ops:
        mock_git_ops.git_list_branches.return_value = []
        response = _client.get("/api/branch/proj1?folder=/tmp/test")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# BRANCH-01: Create branch
# ---------------------------------------------------------------------------


def test_git_create_branch():
    """POST /api/branch/{id}/create returns {branch_name, success: True}."""
    _require_branch()
    with patch("app.routers.branch.git_ops") as mock_git_ops:
        mock_git_ops.git_create_branch.return_value = (
            "experiment/2026-03-15-price-calc-test"
        )
        response = _client.post(
            "/api/branch/proj1/create",
            json={"folder": "/some/folder", "description": "price calc test"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "branch_name" in data
    assert data["branch_name"].startswith("experiment/")


def test_branch_name_format():
    """POST create: branch_name starts with 'experiment/' containing slugified desc."""
    _require_branch()
    with patch("app.routers.branch.git_ops") as mock_git_ops:
        mock_git_ops.git_create_branch.return_value = (
            "experiment/2026-03-15-price-calc-test"
        )
        response = _client.post(
            "/api/branch/proj1/create",
            json={"folder": "/some/folder", "description": "price calc test"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["branch_name"].startswith("experiment/")
    assert "price-calc-test" in data["branch_name"]


# ---------------------------------------------------------------------------
# BRANCH-02: Checkout
# ---------------------------------------------------------------------------


def test_git_checkout():
    """POST /api/branch/{id}/checkout with {folder, branch} returns {success: True}."""
    _require_branch()
    with patch("app.routers.branch.git_ops") as mock_git_ops:
        mock_git_ops.git_checkout.return_value = None
        mock_git_ops.git_changed_workflows.return_value = []
        response = _client.post(
            "/api/branch/proj1/checkout",
            json={"folder": "/some/folder", "branch": "experiment/2026-03-15-test"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_checkout_blocked_if_dirty():
    """Checkout blocked when git_changed_workflows returns files."""
    _require_branch()
    with patch("app.routers.branch.git_ops") as mock_git_ops:
        mock_git_ops.git_changed_workflows.return_value = ["file.yxmd"]
        response = _client.post(
            "/api/branch/proj1/checkout",
            json={"folder": "/some/folder", "branch": "experiment/2026-03-15-test"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Save changes" in data.get("error", "")


# ---------------------------------------------------------------------------
# BRANCH-03: Delete branch
# ---------------------------------------------------------------------------


def test_git_delete_branch():
    """DELETE /api/branch/{id}/delete with {folder, branch} returns {success: True}."""
    _require_branch()
    with patch("app.routers.branch.git_ops") as mock_git_ops:
        mock_git_ops.git_delete_branch.return_value = None
        response = _client.request(
            "DELETE",
            "/api/branch/proj1/delete",
            json={"folder": "/some/folder", "branch": "experiment/2026-03-15-test"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_delete_main_blocked():
    """DELETE with branch='main' → {success: False, error contains 'Cannot delete'}."""
    _require_branch()
    with patch("app.routers.branch.git_ops"):
        response = _client.request(
            "DELETE",
            "/api/branch/proj1/delete",
            json={"folder": "/some/folder", "branch": "main"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Cannot delete" in data.get("error", "")


# ---------------------------------------------------------------------------
# BRANCH-03: Merge base
# ---------------------------------------------------------------------------


def test_get_merge_base_endpoint():
    """GET /api/branch/{id}/merge-base returns {merge_base_sha}."""
    _require_branch()
    mock_completed = MagicMock()
    mock_completed.returncode = 0
    mock_completed.stdout = "abc123\n"

    with patch("app.routers.branch.subprocess.run", return_value=mock_completed):
        response = _client.get(
            "/api/branch/proj1/merge-base",
            params={
                "folder": "/some/folder",
                "branch": "experiment/2026-03-15-test",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["merge_base_sha"] == "abc123"


def test_get_merge_base_returns_null_when_both_fail():
    """When both main and master fail, merge_base_sha is null."""
    _require_branch()
    mock_fail = MagicMock()
    mock_fail.returncode = 1
    mock_fail.stdout = ""

    with patch("app.routers.branch.subprocess.run", return_value=mock_fail):
        response = _client.get(
            "/api/branch/proj1/merge-base",
            params={
                "folder": "/some/folder",
                "branch": "experiment/2026-03-15-test",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["merge_base_sha"] is None


# ---------------------------------------------------------------------------
# Additive: history endpoint with branch param
# ---------------------------------------------------------------------------


def test_list_history_with_branch():
    """GET /api/history/{id} with branch=main returns 200 (branch param accepted)."""
    _require_branch()
    with patch("app.routers.history.git_ops") as mock_git_ops:
        mock_git_ops.git_has_commits.return_value = True
        mock_git_ops.git_log.return_value = []
        mock_git_ops.git_pushed_shas.return_value = set()
        response = _client.get(
            "/api/history/proj1",
            params={"folder": "/some/folder", "branch": "main"},
        )
    assert response.status_code == 200
