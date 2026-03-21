"""Config store service — load/save app configuration using platformdirs + JSON."""

from __future__ import annotations

import json
from pathlib import Path

import platformdirs

APP_NAME = "AlteryxGitCompanion"


def _config_path() -> Path:
    """Return the path to the config JSON file, creating parent dirs as needed."""
    data_dir = Path(platformdirs.user_data_dir(APP_NAME))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "config.json"


def load_config() -> dict:
    """Load config from disk. Returns defaults if file doesn't exist yet."""
    p = _config_path()
    if not p.exists():
        return {"version": 1, "projects": [], "active_project": None}
    return json.loads(p.read_text(encoding="utf-8"))


def save_config(cfg: dict) -> None:
    """Persist config to disk."""
    _config_path().write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_remote_repo(project_id: str, provider: str | None = None) -> dict | str | None:
    """Return the remote repo info dict for project_id.

    Returns {} if no entry exists.
    Shape: {"github_url": "...", "gitlab_url": "..."} (only keys that are set).

    If `provider` is given ("github" or "gitlab"), returns the repo URL string
    for that provider, or None if not configured.
    """
    cfg = load_config()
    info = cfg.get("remote_repos", {}).get(project_id, {})
    if provider is not None:
        return info.get(f"{provider}_url")
    return info


def set_remote_repo(project_id: str, provider: str, url: str) -> None:
    """Store a remote repo URL for the given project and provider.

    Persists under cfg["remote_repos"][project_id]["{provider}_url"].
    Provider should be "github" or "gitlab".
    """
    cfg = load_config()
    if "remote_repos" not in cfg:
        cfg["remote_repos"] = {}
    if project_id not in cfg["remote_repos"]:
        cfg["remote_repos"][project_id] = {}
    cfg["remote_repos"][project_id][f"{provider}_url"] = url
    save_config(cfg)
