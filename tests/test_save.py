"""Tests for Phase 13 Save Version.

Covers git_commit_files, git_undo_last_commit, git_discard_files,
and /api/save endpoints.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helper
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
# git_ops unit tests — SAVE-01: git_commit_files
# ---------------------------------------------------------------------------


def test_git_commit_files(tmp_path):
    """SAVE-01: git_commit_files stages specific files and creates a commit."""
    from app.services.git_ops import git_commit_files

    repo = _make_git_repo(tmp_path)
    workflow = repo / "workflow.yxmd"
    workflow.write_text("v2")

    git_commit_files(str(repo), ["workflow.yxmd"], "Second commit")

    log = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert len(log.stdout.strip().splitlines()) == 2

    show = subprocess.run(
        ["git", "-C", str(repo), "show", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "workflow.yxmd" in show.stdout


def test_commit_only_selected_files(tmp_path):
    """SAVE-01: when two files changed, only the selected one appears in the commit."""
    from app.services.git_ops import git_commit_files

    repo = _make_git_repo(tmp_path)
    # Modify first file and create a second new file
    (repo / "workflow.yxmd").write_text("v2")
    (repo / "other.yxmd").write_text("other-v1")

    # Only commit workflow.yxmd
    git_commit_files(str(repo), ["workflow.yxmd"], "Selective commit")

    # other.yxmd should still be untracked (in porcelain output)
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "other.yxmd" in status.stdout


def test_git_commit_files_empty_files_list(tmp_path):
    """SAVE-01: empty files list raises ValueError."""
    from app.services.git_ops import git_commit_files

    repo = _make_git_repo(tmp_path)
    with pytest.raises(ValueError):
        git_commit_files(str(repo), [], "Empty commit")


# ---------------------------------------------------------------------------
# git_ops unit tests — SAVE-02: git_undo_last_commit
# ---------------------------------------------------------------------------


def test_git_undo_last_commit(tmp_path):
    """SAVE-02: after soft reset, commit count decreases by 1."""
    from app.services.git_ops import git_commit_files, git_undo_last_commit

    repo = _make_git_repo(tmp_path)
    (repo / "workflow.yxmd").write_text("v2")
    git_commit_files(str(repo), ["workflow.yxmd"], "Second commit")

    log_before = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert len(log_before.stdout.strip().splitlines()) == 2

    git_undo_last_commit(str(repo))

    log_after = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert len(log_after.stdout.strip().splitlines()) == 1


def test_git_undo_preserves_file_content(tmp_path):
    """SAVE-02: file bytes before undo == file bytes after undo."""
    from app.services.git_ops import git_commit_files, git_undo_last_commit

    repo = _make_git_repo(tmp_path)
    workflow = repo / "workflow.yxmd"
    workflow.write_text("v2-content")
    git_commit_files(str(repo), ["workflow.yxmd"], "Second commit")

    bytes_before = workflow.read_bytes()
    git_undo_last_commit(str(repo))
    bytes_after = workflow.read_bytes()

    assert bytes_before == bytes_after


# ---------------------------------------------------------------------------
# git_ops unit tests — SAVE-03: git_discard_files
# ---------------------------------------------------------------------------


def test_git_discard_files_backup(tmp_path):
    """SAVE-03: before checkout, file appears in .acd-backup/."""
    from app.services.git_ops import git_discard_files

    repo = _make_git_repo(tmp_path)
    workflow = repo / "workflow.yxmd"
    workflow.write_text("modified-content")

    git_discard_files(str(repo), ["workflow.yxmd"])

    backup = repo / ".acd-backup" / "workflow.yxmd"
    assert backup.exists()


def test_git_discard_files_restore(tmp_path):
    """SAVE-03: tracked file restored to HEAD content."""
    from app.services.git_ops import git_discard_files

    repo = _make_git_repo(tmp_path)
    workflow = repo / "workflow.yxmd"
    original_content = "v1"
    workflow.write_text("modified-content")

    git_discard_files(str(repo), ["workflow.yxmd"])

    assert workflow.read_text() == original_content


def test_git_discard_untracked(tmp_path):
    """SAVE-03: untracked file copied to .acd-backup/ then removed from working dir."""
    from app.services.git_ops import git_discard_files

    repo = _make_git_repo(tmp_path)
    new_file = repo / "new.yxmd"
    new_file.write_text("brand-new")

    git_discard_files(str(repo), ["new.yxmd"])

    backup = repo / ".acd-backup" / "new.yxmd"
    assert backup.exists()
    assert not new_file.exists()


# ---------------------------------------------------------------------------
# Endpoint tests — SAVE-01, SAVE-02, SAVE-03
# ---------------------------------------------------------------------------


def test_commit_endpoint(client, tmp_path):
    """SAVE-01: POST /api/save/commit returns 200 {"ok": true}."""
    repo = _make_git_repo(tmp_path)
    (repo / "workflow.yxmd").write_text("v2")

    with (
        patch("app.routers.save.git_ops.git_commit_files") as mock_commit,
        patch("app.routers.save.watcher_manager.clear_count") as mock_clear,
    ):
        mock_commit.return_value = None
        resp = client.post(
            "/api/save/commit",
            json={
                "project_id": "proj-1",
                "folder": str(repo),
                "files": ["workflow.yxmd"],
                "message": "Save",
            },
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_clear.assert_called_once_with("proj-1")


def test_commit_empty_files(client, tmp_path):
    """SAVE-01: POST /api/save/commit with files: [] returns 400."""
    repo = _make_git_repo(tmp_path)

    resp = client.post(
        "/api/save/commit",
        json={
            "project_id": "proj-1",
            "folder": str(repo),
            "files": [],
            "message": "Empty",
        },
    )
    assert resp.status_code == 400


def test_undo_endpoint(client, tmp_path):
    """SAVE-02: POST /api/save/undo returns 200 {"ok": true}."""
    repo = _make_git_repo(tmp_path)

    with (
        patch("app.routers.save.git_ops.git_undo_last_commit") as mock_undo,
        patch("app.routers.save.git_ops.git_has_commits", return_value=False),
    ):
        mock_undo.return_value = None
        resp = client.post(
            "/api/save/undo",
            json={"project_id": "proj-1", "folder": str(repo)},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "has_any_commits" in data


def test_discard_endpoint(client, tmp_path):
    """SAVE-03: POST /api/save/discard returns 200 {"ok": true}."""
    repo = _make_git_repo(tmp_path)

    with (
        patch("app.routers.save.git_ops.git_discard_files") as mock_discard,
        patch("app.routers.save.watcher_manager.clear_count") as mock_clear,
    ):
        mock_discard.return_value = None
        resp = client.post(
            "/api/save/discard",
            json={
                "project_id": "proj-1",
                "folder": str(repo),
                "files": ["workflow.yxmd"],
            },
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_clear.assert_called_once_with("proj-1")
