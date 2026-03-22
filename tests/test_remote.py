"""Failing test stubs for Phase 16 — Remote Auth and Push.

All tests are in RED state: assertion/NotImplementedError, NOT collection errors.
Covers REMOTE-01 through REMOTE-06. Driven GREEN in Plans 16-02 and 16-03.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Graceful RED: wrap imports so tests report FAILED not collection ERROR
# ---------------------------------------------------------------------------

try:
    from starlette.testclient import TestClient

    from app.routers import remote as _remote_module  # noqa: F401
    from app.server import app as _fastapi_app

    _client = TestClient(_fastapi_app)
    _remote_imported = True
except (ImportError, AttributeError):
    _remote_imported = False
    _client = None  # type: ignore[assignment]

try:
    import app.services.remote_auth  # noqa: F401

    _remote_auth_imported = True
except ImportError:
    _remote_auth_imported = False

try:
    import app.services.github_api  # noqa: F401

    _github_api_imported = True
except ImportError:
    _github_api_imported = False

try:
    import app.services.gitlab_api  # noqa: F401

    _gitlab_api_imported = True
except ImportError:
    _gitlab_api_imported = False

try:
    import app.services.git_ops  # noqa: F401

    _git_ops_imported = True
except ImportError:
    _git_ops_imported = False


def _require_remote():
    if not _remote_imported:
        pytest.fail("app.routers.remote not implemented yet")


def _require_remote_auth():
    if not _remote_auth_imported:
        pytest.fail("app.services.remote_auth not implemented yet")


def _require_github_api():
    if not _github_api_imported:
        pytest.fail("app.services.github_api not implemented yet")


def _require_gitlab_api():
    if not _gitlab_api_imported:
        pytest.fail("app.services.gitlab_api not implemented yet")


def _require_git_ops():
    if not _git_ops_imported:
        pytest.fail("app.services.git_ops not implemented yet")


# ---------------------------------------------------------------------------
# REMOTE-01: GitHub Device Flow
# ---------------------------------------------------------------------------


def test_request_device_code():
    """remote_auth.request_device_code() returns dict with user_code and device_code."""
    _require_remote_auth()
    from app.services import remote_auth

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "device_code": "dev_abc",
        "user_code": "ABCD-1234",
        "verification_uri": "https://github.com/login/device",
        "expires_in": 900,
        "interval": 5,
    }
    mock_resp.raise_for_status.return_value = None

    with patch("app.services.remote_auth.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        result = remote_auth.request_device_code()

    assert "user_code" in result
    assert "device_code" in result


def test_poll_authorization_pending():
    """poll_and_store continues on authorization_pending then returns on success."""
    _require_remote_auth()
    from app.services import remote_auth

    responses = [
        MagicMock(json=MagicMock(return_value={"error": "authorization_pending"})),
        MagicMock(json=MagicMock(return_value={"error": "authorization_pending"})),
        MagicMock(json=MagicMock(return_value={"access_token": "ght_abc"})),
    ]

    mock_keyring = MagicMock()
    with (
        patch("app.services.remote_auth.httpx") as mock_httpx,
        patch("app.services.remote_auth.time") as mock_time,
        patch("app.services.remote_auth.keyring", mock_keyring),
    ):
        mock_httpx.post.side_effect = responses
        mock_time.time.side_effect = [0, 1, 2, 3]  # stays within deadline
        mock_time.sleep.return_value = None

        remote_auth.poll_and_store("dev_abc", 5)

    # poll_and_store stores token; either returned value or keyring.set_password called
    assert mock_httpx.post.call_count == 3


def test_poll_slow_down_increases_interval():
    """poll_and_store adds 5s to interval when GitHub returns slow_down error."""
    _require_remote_auth()
    from app.services import remote_auth

    responses = [
        MagicMock(json=MagicMock(return_value={"error": "slow_down"})),
        MagicMock(json=MagicMock(return_value={"access_token": "tok"})),
    ]

    mock_keyring = MagicMock()
    sleep_calls: list[int] = []

    def capture_sleep(n: int) -> None:
        sleep_calls.append(n)

    with (
        patch("app.services.remote_auth.httpx") as mock_httpx,
        patch("app.services.remote_auth.time") as mock_time,
        patch("app.services.remote_auth.keyring", mock_keyring),
    ):
        mock_httpx.post.side_effect = responses
        mock_time.time.side_effect = [0, 1, 2]
        mock_time.sleep.side_effect = capture_sleep

        remote_auth.poll_and_store("dev_abc", 5)

    # After slow_down the interval must have grown by 5; second sleep should be >= 10
    assert len(sleep_calls) >= 2, "Expected at least 2 sleep calls (initial + retry)"
    assert sleep_calls[1] >= 10, (
        f"After slow_down, sleep interval should be >=10, got {sleep_calls[1]}"
    )


def test_post_github_start():
    """POST /api/remote/github/start returns {user_code, verification_uri}, 200."""
    _require_remote()

    mock_device_resp = {
        "device_code": "dev_abc",
        "user_code": "ABCD-1234",
        "verification_uri": "https://github.com/login/device",
        "expires_in": 900,
        "interval": 5,
    }

    with patch(
        "app.routers.remote.remote_auth.request_device_code",
        return_value=mock_device_resp,
    ):
        resp = _client.post("/api/remote/github/start")

    assert resp.status_code == 200
    data = resp.json()
    assert "user_code" in data, f"Expected user_code in response, got {data}"
    assert "verification_uri" in data, (
        f"Expected verification_uri in response, got {data}"
    )


def test_get_github_status_connected():
    """GET /api/remote/github/status returns {connected: True} when token in keyring."""
    _require_remote()

    with patch(
        "app.routers.remote.remote_auth.get_github_token", return_value="ght_abc"
    ):
        resp = _client.get("/api/remote/github/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("connected") is True, f"Expected connected: True, got {data}"


def test_get_github_status_disconnected():
    """GET /api/remote/github/status returns {connected: False} with no token."""
    _require_remote()

    with patch("app.routers.remote.remote_auth.get_github_token", return_value=None):
        resp = _client.get("/api/remote/github/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("connected") is False, f"Expected connected: False, got {data}"


def test_post_github_connect():
    """POST /api/remote/github/connect stores GitHub PAT; returns {connected: True}."""
    _require_remote()

    with patch("app.routers.remote.remote_auth.store_github_token") as mock_store:
        resp = _client.post(
            "/api/remote/github/connect", json={"token": "ghp_test_token"}
        )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("connected") is True, f"Expected connected: True, got {data}"
    mock_store.assert_called_once_with("ghp_test_token")


def test_get_gitlab_status_connected():
    """GET /api/remote/gitlab/status returns {connected: True} when token in keyring."""
    _require_remote()

    with patch(
        "app.routers.remote.remote_auth.get_gitlab_token", return_value="glpat-abc"
    ):
        resp = _client.get("/api/remote/gitlab/status")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("connected") is True, f"Expected connected: True, got {data}"


def test_get_gitlab_status_disconnected():
    """GET /api/remote/gitlab/status returns {connected: False} with no token."""
    _require_remote()

    with patch("app.routers.remote.remote_auth.get_gitlab_token", return_value=None):
        resp = _client.get("/api/remote/gitlab/status")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("connected") is False, f"Expected connected: False, got {data}"


# ---------------------------------------------------------------------------
# REMOTE-02: GitLab PAT validation
# ---------------------------------------------------------------------------


def test_validate_gitlab_token_valid():
    """validate_gitlab_token returns user dict when httpx GET returns status 200."""
    _require_remote_auth()
    from app.services import remote_auth

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"username": "user", "id": 42}

    with patch("app.services.remote_auth.httpx") as mock_httpx:
        mock_httpx.get.return_value = mock_resp
        result = remote_auth.validate_gitlab_token("glpat-xxx")

    assert result is not None
    assert isinstance(result, dict)


def test_validate_gitlab_token_invalid():
    """validate_gitlab_token returns None when httpx GET returns status 401."""
    _require_remote_auth()
    from app.services import remote_auth

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("app.services.remote_auth.httpx") as mock_httpx:
        mock_httpx.get.return_value = mock_resp
        result = remote_auth.validate_gitlab_token("bad-token")

    assert result is None


def test_post_gitlab_connect_valid():
    """POST /api/remote/gitlab/connect with valid token returns {connected: True}."""
    _require_remote()

    user_dict = {"username": "user", "id": 42}
    with (
        patch(
            "app.routers.remote.remote_auth.validate_gitlab_token",
            return_value=user_dict,
        ),
        patch("app.routers.remote.remote_auth.store_gitlab_token") as mock_store,
    ):
        resp = _client.post("/api/remote/gitlab/connect", json={"token": "glpat-xxx"})

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("connected") is True, f"Expected connected: True, got {data}"
    mock_store.assert_called_once_with("glpat-xxx")


def test_post_gitlab_connect_invalid():
    """POST /api/remote/gitlab/connect with bad token returns connected: False."""
    _require_remote()

    with patch(
        "app.routers.remote.remote_auth.validate_gitlab_token", return_value=None
    ):
        resp = _client.post("/api/remote/gitlab/connect", json={"token": "bad-token"})

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("connected") is False, f"Expected connected: False, got {data}"
    assert "error" in data, f"Expected error key in response, got {data}"


# ---------------------------------------------------------------------------
# REMOTE-03: Credential storage
# ---------------------------------------------------------------------------


def test_store_and_get_github_token():
    """store_github_token stores via keyring; get_github_token retrieves via keyring."""
    _require_remote_auth()

    mock_keyring = MagicMock()
    with patch.dict("sys.modules", {"keyring": mock_keyring}):
        # Re-import to pick up mocked keyring module
        import importlib

        import app.services.remote_auth as ra_mod

        importlib.reload(ra_mod)

        mock_keyring.get_password.return_value = "ght_tok"
        ra_mod.store_github_token("ght_tok")
        ra_mod.get_github_token()

    mock_keyring.set_password.assert_called_once()
    set_args = mock_keyring.set_password.call_args
    assert "github" in str(set_args).lower() or "AlteryxGitCompanion" in str(
        set_args
    ), f"Expected SERVICE_GITHUB in keyring.set_password call, got {set_args}"
    mock_keyring.get_password.assert_called_once()


def test_credentials_not_in_config_store():
    """store_github_token does NOT call config_store.save_config."""
    _require_remote_auth()

    mock_keyring = MagicMock()
    with (
        patch.dict("sys.modules", {"keyring": mock_keyring}),
        patch("app.services.config_store.save_config") as mock_save,
    ):
        import importlib

        import app.services.remote_auth as ra_mod

        importlib.reload(ra_mod)

        ra_mod.store_github_token("ght_tok")

    mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# REMOTE-04: git push
# ---------------------------------------------------------------------------


def test_git_push_calls_subprocess():
    """git_ops.git_push calls subprocess with git -C folder push args."""
    _require_git_ops()
    from app.services import git_ops

    with patch("app.services.git_ops.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        git_ops.git_push("/fake/folder", "https://github.com/owner/repo.git", "ght_tok")

    calls = mock_sub.run.call_args_list
    assert len(calls) >= 1, "Expected at least one subprocess.run call"

    # At minimum one call must contain ["git", "-C", "/fake/folder", "push", ...]
    push_call_found = any(
        isinstance(c.args[0], list)
        and "git" in c.args[0]
        and "-C" in c.args[0]
        and "/fake/folder" in c.args[0]
        and "push" in c.args[0]
        for c in calls
    )
    assert push_call_found, (
        f"Expected a subprocess call with git -C /fake/folder push ..., got {calls}"
    )


def test_git_push_uses_askpass_not_url_token():
    """git_ops.git_push uses GIT_ASKPASS env var; token NOT embedded in remote URL."""
    _require_git_ops()
    from app.services import git_ops

    captured_envs: list[dict] = []
    captured_urls: list[str] = []

    def mock_run(args, **kwargs):
        env = kwargs.get("env", {})
        if env:
            captured_envs.append(dict(env))
        # Capture any URL-like string in args that might contain the token
        for arg in args:
            if isinstance(arg, str) and "github.com" in arg:
                captured_urls.append(arg)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("app.services.git_ops.subprocess") as mock_sub:
        mock_sub.run.side_effect = mock_run
        git_ops.git_push(
            "/fake/folder", "https://github.com/owner/repo.git", "ght_tok_secret"
        )

    # GIT_ASKPASS must appear in at least one env dict
    askpass_found = any("GIT_ASKPASS" in env for env in captured_envs)
    assert askpass_found, f"Expected GIT_ASKPASS in env, captured envs: {captured_envs}"

    # Token must NOT appear embedded in any URL passed to subprocess
    token_in_url = any("ght_tok_secret" in url for url in captured_urls)
    assert not token_in_url, (
        f"Token should not be embedded in remote URL, found in: {captured_urls}"
    )


def test_post_push_success():
    """POST /api/remote/push returns {success: True} when git_push succeeds."""
    _require_remote()

    with (
        patch("app.routers.remote.git_ops.git_push") as mock_push,
        patch(
            "app.routers.remote.remote_auth.get_github_token", return_value="ght_tok"
        ),
        patch(
            "app.routers.remote.config_store.get_remote_repo",
            return_value={"github_url": "https://github.com/owner/repo.git"},
        ),
    ):
        mock_push.return_value = None
        resp = _client.post(
            "/api/remote/push",
            json={"project_id": "proj-1", "folder": "/fake/folder"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True, f"Expected success: True, got {data}"


# ---------------------------------------------------------------------------
# REMOTE-05: Auto repo creation
# ---------------------------------------------------------------------------


def test_create_github_repo_private():
    """github_api.create_github_repo posts to /user/repos with private=True."""
    _require_github_api()
    from app.services import github_api

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "clone_url": "https://github.com/owner/my-workflows.git",
        "html_url": "https://github.com/owner/my-workflows",
    }

    with patch("app.services.github_api.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        github_api.create_github_repo("ght_tok", "my-workflows")

    mock_httpx.post.assert_called_once()
    post_call = mock_httpx.post.call_args
    # Verify URL contains /user/repos
    url_arg = post_call.args[0] if post_call.args else post_call.kwargs.get("url", "")
    assert "/user/repos" in url_arg, f"Expected /user/repos in POST URL, got {url_arg}"
    # Verify private=True in json payload
    json_payload = post_call.kwargs.get("json", {})
    assert json_payload.get("private") is True, (
        f"Expected private: True in POST payload, got {json_payload}"
    )


def test_find_available_repo_name_collision():
    """find_available_repo_name appends -2, -3 suffix on collision until free."""
    _require_github_api()
    from app.services import github_api

    # First two attempts collide; third is free
    exists_responses = [True, True, False]

    with patch(
        "app.services.github_api.github_repo_exists", side_effect=exists_responses
    ):
        result = github_api.find_available_repo_name("ght_tok", "owner", "repo")

    assert result == "repo-3", f"Expected 'repo-3', got {result!r}"


def test_create_gitlab_project_private():
    """gitlab_api.create_gitlab_project posts to /projects with visibility=private."""
    _require_gitlab_api()
    from app.services import gitlab_api

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "http_url_to_repo": "https://gitlab.com/user/my-workflows.git"
    }

    with patch("app.services.gitlab_api.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        gitlab_api.create_gitlab_project("glpat-xxx", "my-workflows")

    mock_httpx.post.assert_called_once()
    post_call = mock_httpx.post.call_args
    url_arg = post_call.args[0] if post_call.args else post_call.kwargs.get("url", "")
    assert "/projects" in url_arg, f"Expected /projects in POST URL, got {url_arg}"
    json_payload = post_call.kwargs.get("json", {})
    assert json_payload.get("visibility") == "private", (
        f"Expected visibility: private in POST payload, got {json_payload}"
    )


# ---------------------------------------------------------------------------
# REMOTE-06: Ahead/behind indicator
# ---------------------------------------------------------------------------


def test_git_ahead_behind():
    """git_ops.git_ahead_behind returns (ahead, behind) from rev-list --count output."""
    _require_git_ops()
    from app.services import git_ops

    def mock_run(args, **kwargs):
        result = MagicMock()
        result.stdout = ""
        result.returncode = 0
        if "--abbrev-ref" in args and "@{u}" in args:
            result.stdout = "origin/main\n"
            result.returncode = 0
        elif "rev-list" in args and any("HEAD" in a for a in args):
            joined = " ".join(args)
            if "HEAD..origin" in joined or "HEAD.." in joined:
                # behind: HEAD..upstream (commits upstream has that HEAD lacks)
                result.stdout = "1\n"
            else:
                # ahead: upstream..HEAD (commits HEAD has that upstream lacks)
                result.stdout = "3\n"
        return result

    with patch("app.services.git_ops.subprocess") as mock_sub:
        mock_sub.run.side_effect = mock_run
        ahead, behind = git_ops.git_ahead_behind("/fake/folder")

    assert ahead == 3, f"Expected ahead=3, got {ahead}"
    assert behind == 1, f"Expected behind=1, got {behind}"


def test_git_ahead_behind_no_upstream():
    """git_ops.git_ahead_behind returns (0, 0) when no upstream is configured."""
    _require_git_ops()
    from app.services import git_ops

    def mock_run(args, **kwargs):
        result = MagicMock()
        result.returncode = 1  # rev-parse --abbrev-ref @{u} fails when no upstream
        result.stdout = ""
        return result

    with patch("app.services.git_ops.subprocess") as mock_sub:
        mock_sub.run.side_effect = mock_run
        result = git_ops.git_ahead_behind("/fake/folder")

    assert result == (0, 0), f"Expected (0, 0) when no upstream, got {result}"


def test_git_fetch_calls_subprocess():
    """git_ops.git_fetch calls subprocess with git -C folder fetch origin."""
    _require_git_ops()
    from app.services import git_ops

    with patch("app.services.git_ops.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        git_ops.git_fetch(
            "/fake/folder", "https://github.com/owner/repo.git", "ght_tok"
        )

    calls = mock_sub.run.call_args_list
    assert len(calls) >= 1, "Expected at least one subprocess.run call"

    fetch_call_found = any(
        isinstance(c.args[0], list)
        and "git" in c.args[0]
        and "-C" in c.args[0]
        and "/fake/folder" in c.args[0]
        and "fetch" in c.args[0]
        for c in calls
    )
    assert fetch_call_found, (
        f"Expected a subprocess call with git -C /fake/folder fetch ..., got {calls}"
    )


def test_git_fetch_uses_askpass():
    """git_ops.git_fetch uses GIT_ASKPASS env var for credential injection."""
    _require_git_ops()
    from app.services import git_ops

    captured_envs: list[dict] = []

    def mock_run(args, **kwargs):
        env = kwargs.get("env", {})
        if env:
            captured_envs.append(dict(env))
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("app.services.git_ops.subprocess") as mock_sub:
        mock_sub.run.side_effect = mock_run
        git_ops.git_fetch(
            "/fake/folder", "https://github.com/owner/repo.git", "ght_tok"
        )

    askpass_found = any("GIT_ASKPASS" in env for env in captured_envs)
    assert askpass_found, f"Expected GIT_ASKPASS in env, captured envs: {captured_envs}"


def test_get_remote_status_ahead_behind():
    """GET /api/remote/status returns ahead, behind and connection status fields."""
    _require_remote()

    with (
        patch("app.routers.remote.git_ops.git_ahead_behind", return_value=(2, 0)),
        patch(
            "app.routers.remote.remote_auth.get_github_token", return_value="ght_abc"
        ),
        patch("app.routers.remote.remote_auth.get_gitlab_token", return_value=None),
    ):
        resp = _client.get(
            "/api/remote/status",
            params={"folder": "/fake/folder"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "ahead" in data, f"Expected ahead in response, got {data}"
    assert "behind" in data, f"Expected behind in response, got {data}"
    assert data.get("ahead") == 2, f"Expected ahead=2, got {data}"
    assert data.get("behind") == 0, f"Expected behind=0, got {data}"
    assert data.get("github_connected") is True, (
        f"Expected github_connected: True, got {data}"
    )
    assert data.get("gitlab_connected") is False, (
        f"Expected gitlab_connected: False, got {data}"
    )


def test_get_remote_status_includes_repo_url():
    """GET /api/remote/status returns repo_url from config_store."""
    _require_remote()

    with (
        patch("app.routers.remote.git_ops.git_ahead_behind", return_value=(0, 0)),
        patch("app.routers.remote.git_ops.git_fetch"),
        patch(
            "app.routers.remote.remote_auth.get_github_token", return_value="ght_abc"
        ),
        patch("app.routers.remote.remote_auth.get_gitlab_token", return_value=None),
        patch(
            "app.routers.remote.config_store.get_remote_repo",
            return_value={"github_url": "https://github.com/user/repo.git"},
        ),
    ):
        resp = _client.get(
            "/api/remote/status",
            params={"project_id": "proj-1", "folder": "/fake/folder"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "repo_url" in data, f"Expected repo_url in response, got {data}"
    assert data["repo_url"] == "https://github.com/user/repo.git", (
        f"Expected repo_url from config_store, got {data}"
    )


# ---------------------------------------------------------------------------
# config_store helpers: get_remote_repo, set_remote_repo
# ---------------------------------------------------------------------------


def test_config_store_set_and_get_remote_repo(tmp_path, monkeypatch):
    """set_remote_repo stores URL; get_remote_repo retrieves it."""
    monkeypatch.setattr(
        "app.services.config_store._config_path", lambda: tmp_path / "config.json"
    )
    from app.services import config_store

    config_store.set_remote_repo(
        "proj-abc", "github", "https://github.com/user/repo.git"
    )
    result = config_store.get_remote_repo("proj-abc")

    assert result.get("github_url") == "https://github.com/user/repo.git", (
        f"Expected github_url in remote_repos, got {result}"
    )


def test_config_store_get_remote_repo_missing(tmp_path, monkeypatch):
    """get_remote_repo returns empty dict when no entry for project_id."""
    monkeypatch.setattr(
        "app.services.config_store._config_path", lambda: tmp_path / "config.json"
    )
    from app.services import config_store

    result = config_store.get_remote_repo("nonexistent-proj")
    assert result == {}, f"Expected empty dict for missing project, got {result}"
