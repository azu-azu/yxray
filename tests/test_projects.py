"""Test stubs for ONBOARD-01, ONBOARD-02, ONBOARD-04 — RED phase (Plan 01).

All tests should FAIL with 501 at this stage because router stubs raise
HTTPException(501). Plan 02 will make them GREEN by implementing the endpoints.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.server import app

_EMPTY_CONFIG = {"version": 1, "projects": [], "active_project": None}


def test_list_projects_empty(tmp_path):
    """GET /api/projects returns 200 with empty list when config has no projects."""
    with (
        patch(
            "app.routers.projects.config_store.load_config",
            return_value=_EMPTY_CONFIG,
        ),
        patch("app.routers.projects.config_store.save_config") as _mock_save,
    ):
        client = TestClient(app)
        response = client.get("/api/projects")
        assert response.status_code == 200
        assert response.json() == []


def test_check_project_not_git(tmp_path):
    """GET /api/projects/check?path=... returns 200 with {is_git_repo: false}."""
    folder = str(tmp_path)
    with patch("app.routers.projects.git_ops.is_git_repo", return_value=False):
        client = TestClient(app)
        response = client.get("/api/projects/check", params={"path": folder})
        assert response.status_code == 200
        assert response.json() == {"is_git_repo": False}


def test_check_project_is_git(tmp_path):
    """GET /api/projects/check?path=... returns 200 with {is_git_repo: true}."""
    folder = str(tmp_path)
    with patch("app.routers.projects.git_ops.is_git_repo", return_value=True):
        client = TestClient(app)
        response = client.get("/api/projects/check", params={"path": folder})
        assert response.status_code == 200
        assert response.json() == {"is_git_repo": True}


def test_add_project_new_git_repo(tmp_path):
    """POST /api/projects with valid path returns 201 with project object."""
    folder = str(tmp_path)
    with (
        patch(
            "app.routers.projects.config_store.load_config",
            return_value=_EMPTY_CONFIG.copy(),
        ),
        patch("app.routers.projects.config_store.save_config"),
        patch("app.routers.projects.git_ops.is_git_repo", return_value=False),
        patch("app.routers.projects.git_ops.git_init"),
    ):
        client = TestClient(app)
        response = client.post("/api/projects", json={"path": folder})
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["path"] == folder
        assert "name" in data


def test_add_project_runs_git_init(tmp_path):
    """POST /api/projects for a folder with no .git causes git_init to be called."""
    folder = str(tmp_path)
    with (
        patch(
            "app.routers.projects.config_store.load_config",
            return_value=_EMPTY_CONFIG.copy(),
        ),
        patch("app.routers.projects.config_store.save_config"),
        patch("app.routers.projects.git_ops.is_git_repo", return_value=False),
        patch("app.routers.projects.git_ops.git_init") as mock_git_init,
    ):
        client = TestClient(app)
        client.post("/api/projects", json={"path": folder})
        mock_git_init.assert_called_once_with(folder)


def test_add_project_skips_git_init(tmp_path):
    """POST /api/projects with a folder that already has .git does NOT call git_init."""
    folder = str(tmp_path)
    with (
        patch(
            "app.routers.projects.config_store.load_config",
            return_value=_EMPTY_CONFIG.copy(),
        ),
        patch("app.routers.projects.config_store.save_config"),
        patch("app.routers.projects.git_ops.is_git_repo", return_value=True),
        patch("app.routers.projects.git_ops.git_init") as mock_git_init,
    ):
        client = TestClient(app)
        client.post("/api/projects", json={"path": folder})
        mock_git_init.assert_not_called()


def test_remove_project(tmp_path):
    """DELETE /api/projects/{id} removes the project from config and returns 200."""
    project_id = "test-uuid-1234"
    existing_config = {
        "version": 1,
        "projects": [
            {
                "id": project_id,
                "path": str(tmp_path),
                "name": tmp_path.name,
            }
        ],
        "active_project": None,
    }
    with (
        patch(
            "app.routers.projects.config_store.load_config",
            return_value=existing_config,
        ),
        patch("app.routers.projects.config_store.save_config") as mock_save,
    ):
        client = TestClient(app)
        response = client.delete(f"/api/projects/{project_id}")
        assert response.status_code == 200
        # Verify save_config was called with the project removed
        mock_save.assert_called_once()
        saved_cfg = mock_save.call_args[0][0]
        assert not any(p["id"] == project_id for p in saved_cfg["projects"])


def test_list_multiple_projects(tmp_path):
    """GET /api/projects returns all registered projects."""
    proj1 = str(tmp_path / "proj1")
    proj2 = str(tmp_path / "proj2")
    config_with_two = {
        "version": 1,
        "projects": [
            {"id": "uuid-1", "path": proj1, "name": "proj1"},
            {"id": "uuid-2", "path": proj2, "name": "proj2"},
        ],
        "active_project": None,
    }
    with patch(
        "app.routers.projects.config_store.load_config",
        return_value=config_with_two,
    ):
        client = TestClient(app)
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        ids = [p["id"] for p in data]
        assert "uuid-1" in ids
        assert "uuid-2" in ids
