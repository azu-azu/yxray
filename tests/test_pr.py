"""Unit tests for PR/MR service functions — Phase 18.1 Plan 01.

RED state: tests import and call functions that do not exist yet in the service
modules.  All tests are expected to fail with AttributeError until Plan 01 Task 2
drives them GREEN.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# GitHub PR tests
# ---------------------------------------------------------------------------


def test_parse_github_url():
    from app.services.github_api import parse_github_owner_repo

    # .git suffix stripped
    assert parse_github_owner_repo("https://github.com/owner/repo.git") == (
        "owner",
        "repo",
    )
    # no .git suffix
    assert parse_github_owner_repo("https://github.com/owner/repo") == (
        "owner",
        "repo",
    )
    # invalid URL raises ValueError
    with pytest.raises(ValueError):
        parse_github_owner_repo("https://invalid.com/foo")


def test_create_github_pr():
    from app.services.github_api import create_pull_request

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "html_url": "https://github.com/owner/repo/pull/1"
    }

    with patch("app.services.github_api.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_response

        result = create_pull_request(
            token="tok",
            owner="owner",
            repo="repo",
            title="My PR",
            head="experiment/foo",
        )

    assert result == {"html_url": "https://github.com/owner/repo/pull/1"}
    mock_httpx.post.assert_called_once()


def test_get_open_github_pr_exists():
    from app.services.github_api import get_open_pr_for_branch

    pr_item = {"html_url": "https://github.com/owner/repo/pull/1", "number": 1}
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [pr_item]

    with patch("app.services.github_api.httpx") as mock_httpx:
        mock_httpx.get.return_value = mock_response

        result = get_open_pr_for_branch(
            token="tok",
            owner="owner",
            repo="repo",
            branch="experiment/foo",
        )

    assert result == pr_item


def test_get_open_github_pr_none():
    from app.services.github_api import get_open_pr_for_branch

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = []

    with patch("app.services.github_api.httpx") as mock_httpx:
        mock_httpx.get.return_value = mock_response

        result = get_open_pr_for_branch(
            token="tok",
            owner="owner",
            repo="repo",
            branch="experiment/foo",
        )

    assert result is None


# ---------------------------------------------------------------------------
# GitLab MR tests
# ---------------------------------------------------------------------------


def test_parse_gitlab_namespace():
    from app.services.gitlab_api import parse_gitlab_namespace_path

    # .git suffix stripped
    assert parse_gitlab_namespace_path("https://gitlab.com/ns/proj.git") == "ns/proj"
    # no .git suffix
    assert parse_gitlab_namespace_path("https://gitlab.com/ns/proj") == "ns/proj"


def test_get_gitlab_project_id():
    from app.services.gitlab_api import get_gitlab_project_id

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"id": 12345}

    with patch("app.services.gitlab_api.httpx") as mock_httpx:
        mock_httpx.get.return_value = mock_response

        result = get_gitlab_project_id(token="tok", namespace_path="ns/proj")

    assert result == 12345
    # URL must encode "/" as "%2F"
    call_url = mock_httpx.get.call_args[0][0]
    assert "%2F" in call_url


def test_create_gitlab_mr():
    from app.services.gitlab_api import create_merge_request

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "web_url": "https://gitlab.com/ns/proj/-/merge_requests/1"
    }

    with patch("app.services.gitlab_api.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_response

        result = create_merge_request(
            token="tok",
            project_id=12345,
            title="My MR",
            source_branch="experiment/foo",
        )

    assert result == {"web_url": "https://gitlab.com/ns/proj/-/merge_requests/1"}
    mock_httpx.post.assert_called_once()


def test_get_open_gitlab_mr_exists():
    from app.services.gitlab_api import get_open_mr_for_branch

    mr_item = {"web_url": "https://gitlab.com/ns/proj/-/merge_requests/1", "iid": 1}
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [mr_item]

    with patch("app.services.gitlab_api.httpx") as mock_httpx:
        mock_httpx.get.return_value = mock_response

        result = get_open_mr_for_branch(
            token="tok",
            project_id=12345,
            branch="experiment/foo",
        )

    assert result == mr_item


def test_get_open_gitlab_mr_none():
    from app.services.gitlab_api import get_open_mr_for_branch

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = []

    with patch("app.services.gitlab_api.httpx") as mock_httpx:
        mock_httpx.get.return_value = mock_response

        result = get_open_mr_for_branch(
            token="tok",
            project_id=12345,
            branch="experiment/foo",
        )

    assert result is None
