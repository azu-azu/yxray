"""Test stubs for ONBOARD-03 — RED phase (Plan 01).

All tests should FAIL with 501 at this stage because router stubs raise
HTTPException(501). Plan 02 will make them GREEN by implementing the endpoints.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.server import app


def test_get_identity_missing():
    """GET /api/git/identity returns {name: null, email: null} when not configured."""
    with patch(
        "app.services.git_ops.get_git_identity",
        return_value={"name": None, "email": None},
    ):
        client = TestClient(app)
        response = client.get("/api/git/identity")
        assert response.status_code == 200
        data = response.json()
        assert data == {"name": None, "email": None}


def test_set_identity():
    """POST /api/git/identity with name/email returns 200 and calls set_git_identity."""
    with patch("app.services.git_ops.set_git_identity") as mock_set:
        client = TestClient(app)
        response = client.post(
            "/api/git/identity",
            json={"name": "Alice", "email": "alice@example.com"},
        )
        assert response.status_code == 200
        mock_set.assert_called_once_with("Alice", "alice@example.com")
