"""Remote auth service — GitHub Device Flow and GitLab PAT credential management.

Stores all credentials in OS keyring; never writes tokens to config_store.
"""

from __future__ import annotations

import sys
import time

import httpx
import keyring

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEVICE_CODE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
GITLAB_BASE = "https://gitlab.com/api/v4"
CLIENT_ID = "Ov23liIZIzK0pYwmA580"
SERVICE_GITHUB = "AlteryxGitCompanion:github"
SERVICE_GITLAB = "AlteryxGitCompanion:gitlab"
USERNAME_KEY = "token"


# ---------------------------------------------------------------------------
# PyInstaller keyring backend fix
# ---------------------------------------------------------------------------


def _ensure_backend() -> None:
    """Select the correct keyring backend when running as a frozen PyInstaller bundle.

    Without this, PyInstaller strips backend discovery metadata and keyring falls
    back to a null (no-op) backend, silently losing all stored credentials.
    """
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            import keyring.backends.Windows  # type: ignore[import-not-found]

            keyring.set_keyring(keyring.backends.Windows.WinVaultKeyring())
        elif sys.platform == "darwin":
            import keyring.backends.macOS  # type: ignore[import-not-found]

            keyring.set_keyring(keyring.backends.macOS.Keyring())


_ensure_backend()


# ---------------------------------------------------------------------------
# GitHub Device Flow
# ---------------------------------------------------------------------------


def request_device_code() -> dict:
    """Step 1: Request a device code from GitHub OAuth Device Flow.

    Returns dict with keys: device_code, user_code, verification_uri,
    expires_in, interval.
    """
    resp = httpx.post(
        DEVICE_CODE_URL,
        data={"client_id": CLIENT_ID, "scope": "repo"},
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


def poll_and_store(device_code: str, interval: int) -> None:
    """Step 2: Poll GitHub until user authorises or flow expires.

    Stores access token in OS keyring via store_github_token on success.
    Handles authorization_pending (continue), slow_down (interval += 5),
    expired_token and access_denied (abort).
    """
    deadline = time.time() + 900
    current_interval = interval

    while time.time() < deadline:
        time.sleep(current_interval)
        resp = httpx.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json"},
        )
        data = resp.json()

        if "access_token" in data:
            store_github_token(data["access_token"])
            return

        error = data.get("error", "")
        if error == "authorization_pending":
            continue
        elif error == "slow_down":
            current_interval += 5
            continue
        elif error in ("expired_token", "access_denied"):
            return
        # unknown error — continue polling
    # deadline reached without success
    return


# ---------------------------------------------------------------------------
# GitHub keyring helpers
# ---------------------------------------------------------------------------


def store_github_token(token: str) -> None:
    """Store a GitHub access token in OS keyring."""
    keyring.set_password(SERVICE_GITHUB, USERNAME_KEY, token)


def get_github_token() -> str | None:
    """Return the stored GitHub access token from OS keyring, or None."""
    return keyring.get_password(SERVICE_GITHUB, USERNAME_KEY)


# ---------------------------------------------------------------------------
# GitLab keyring helpers
# ---------------------------------------------------------------------------


def store_gitlab_token(token: str) -> None:
    """Store a GitLab PAT in OS keyring."""
    keyring.set_password(SERVICE_GITLAB, USERNAME_KEY, token)


def get_gitlab_token() -> str | None:
    """Return the stored GitLab PAT from OS keyring, or None."""
    return keyring.get_password(SERVICE_GITLAB, USERNAME_KEY)


def get_token(provider: str) -> str | None:
    """Return the stored token for the given provider ("github" or "gitlab").

    Convenience dispatcher used by routers that receive provider as a string
    parameter and need a single call site for both GitHub and GitLab tokens.
    """
    if provider == "github":
        return get_github_token()
    return get_gitlab_token()


# ---------------------------------------------------------------------------
# GitLab PAT validation
# ---------------------------------------------------------------------------


def validate_gitlab_token(token: str) -> dict | None:
    """Validate a GitLab PAT via GET /api/v4/user.

    Returns user info dict on success, None if token is invalid.
    """
    resp = httpx.get(
        f"{GITLAB_BASE}/user",
        headers={"PRIVATE-TOKEN": token},
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def validate_and_store_gitlab_token(token: str) -> bool:
    """Validate token against GitLab, store in keyring if valid.

    Returns True on success, False if token is rejected.
    """
    user = validate_gitlab_token(token)
    if user is not None:
        store_gitlab_token(token)
        return True
    return False
