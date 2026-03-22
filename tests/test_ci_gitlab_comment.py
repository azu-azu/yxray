"""
Tests for GitLab CI comment generation + find-or-update logic.

generate_diff_comment.py lives in the alteryx repo (separate from this repo).
We use sys.path insertion to import it without installation — mirrors
test_ci_github_comment.py.
"""

import importlib.util
import os
import sys
from unittest.mock import patch

# Load the GitLab script under an isolated module name to avoid colliding with
# test_ci_github_comment.py, which imports a module with the same name from a
# different path. importlib prevents sys.modules cross-contamination.
_GITLAB_SCRIPT = (
    "/Users/laxmikantmukkawar/alteryx/.gitlab/scripts/generate_diff_comment.py"
)
_spec = importlib.util.spec_from_file_location(
    "gitlab_generate_diff_comment", _GITLAB_SCRIPT
)
generate_diff_comment = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_diff_comment)
sys.modules["gitlab_generate_diff_comment"] = generate_diff_comment

MARKER = "<!-- acd-diff-report -->"


class TestBuildCommentMarker:
    def test_build_comment_includes_marker(self):
        comment = generate_diff_comment.build_comment(
            diffs=[],
            project_path="/tmp/project",
            run_url="https://gitlab.com/example/-/pipelines/1",
        )
        assert comment.startswith(MARKER), (
            f"build_comment() must start with MARKER. Got: {comment[:60]!r}"
        )

    def test_build_no_files_comment_includes_marker(self):
        comment = generate_diff_comment.build_no_files_comment(
            run_url="https://gitlab.com/example/-/pipelines/1",
        )
        assert comment.startswith(MARKER), (
            f"build_no_files_comment() must start with MARKER. Got: {comment[:60]!r}"
        )


class TestPostOrUpdateNote:
    def test_post_or_update_note_calls_put_when_marker_found(self):
        existing_note = {"id": 42, "body": f"{MARKER}\nOld comment content"}
        with (
            patch.dict(
                os.environ,
                {
                    "GITLAB_TOKEN": "test-token",
                    "CI_API_V4_URL": "https://gitlab.com/api/v4",
                    "CI_PROJECT_ID": "123",
                    "CI_MERGE_REQUEST_IID": "1",
                },
            ),
            patch.object(
                generate_diff_comment, "list_notes", return_value=[existing_note]
            ) as mock_list,
            patch.object(generate_diff_comment, "update_note") as mock_update,
            patch.object(generate_diff_comment, "post_note") as mock_post,
        ):
            generate_diff_comment.post_or_update_note(f"{MARKER}\nNew content")
        mock_list.assert_called_once()
        mock_update.assert_called_once_with(42, f"{MARKER}\nNew content")
        mock_post.assert_not_called()

    def test_post_or_update_note_calls_post_when_no_marker_found(self):
        with (
            patch.dict(
                os.environ,
                {
                    "GITLAB_TOKEN": "test-token",
                    "CI_API_V4_URL": "https://gitlab.com/api/v4",
                    "CI_PROJECT_ID": "123",
                    "CI_MERGE_REQUEST_IID": "1",
                },
            ),
            patch.object(
                generate_diff_comment,
                "list_notes",
                return_value=[{"id": 1, "body": "Unrelated comment"}],
            ),
            patch.object(generate_diff_comment, "update_note") as mock_update,
            patch.object(generate_diff_comment, "post_note") as mock_post,
        ):
            generate_diff_comment.post_or_update_note(f"{MARKER}\nNew content")
        mock_post.assert_called_once()
        mock_update.assert_not_called()

    def test_post_or_update_note_skips_when_no_token(self):
        env_without_token = {k: v for k, v in os.environ.items() if k != "GITLAB_TOKEN"}
        with (
            patch.dict(os.environ, env_without_token, clear=True),
            patch.object(generate_diff_comment, "list_notes") as mock_list,
        ):
            generate_diff_comment.post_or_update_note("body")
        mock_list.assert_not_called()
