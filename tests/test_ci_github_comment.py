"""
test_ci_github_comment.py
─────────────────────────
RED test scaffold for CI-01 and CI-02 behaviours in generate_diff_comment.py.

These tests are written BEFORE the implementation — they will fail until
Plan 02 updates the helper script. Expected failures:
  - AttributeError: module 'generate_diff_comment' has no attribute 'is_private_repo'
  - AttributeError: module 'generate_diff_comment' has no attribute 'build_comment'
    (or AssertionError: marker not found in current build_comment output)

Import path: the script lives in the alteryx repo, not installed as a package,
so we use sys.path insertion.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_GITHUB_SCRIPTS = "/Users/laxmikantmukkawar/alteryx/.github/scripts"
if not os.path.isdir(_GITHUB_SCRIPTS):
    import pytest

    pytest.skip(
        "ci-templates scripts not available (separate repo)",
        allow_module_level=True,
    )

sys.path.insert(0, _GITHUB_SCRIPTS)

import generate_diff_comment as gdc  # noqa: E402

MARKER = "<!-- acd-diff-report -->"


# ─────────────────────────────────────────────────────────────────────────────
# Group 1 — CI-01: marker in comment bodies
# ─────────────────────────────────────────────────────────────────────────────


class TestMarkerInCommentBodies(unittest.TestCase):
    def test_build_comment_includes_marker(self):
        """build_comment() must prepend <!-- acd-diff-report --> as first line."""
        result = gdc.build_comment(
            sections=[],
            files=["Workflow.yxmd"],
            html_count=0,
            short_sha="abc1234",
            timestamp="2026-03-15 12:00 UTC",
            totals={"added": 0, "removed": 0, "modified": 0},
            errors=0,
            run_url="https://github.com/owner/repo/actions/runs/123",
        )
        first_line = result.split("\n")[0]
        self.assertEqual(
            first_line,
            MARKER,
            f"Expected first line to be the marker, got: {first_line!r}",
        )

    def test_build_no_files_comment_includes_marker(self):
        """build_no_files_comment() must prepend the marker as its first line."""
        result = gdc.build_no_files_comment("abc1234", "2026-03-15 12:00 UTC")
        first_line = result.split("\n")[0]
        self.assertEqual(
            first_line,
            MARKER,
            f"Expected first line to be the marker, got: {first_line!r}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 2 — CI-02: is_private_repo
# ─────────────────────────────────────────────────────────────────────────────


class TestIsPrivateRepo(unittest.TestCase):
    def setUp(self):
        # Ensure no stray env vars leak between tests
        self._env_backup = {
            k: os.environ.pop(k, None) for k in ("GITHUB_TOKEN", "GITHUB_REPOSITORY")
        }

    def tearDown(self):
        for k, v in self._env_backup.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    def test_is_private_repo_returns_true_on_missing_env(self):
        """Missing GITHUB_TOKEN/GITHUB_REPOSITORY — default to True (conservative)."""
        result = gdc.is_private_repo()
        self.assertTrue(
            result,
            "Expected is_private_repo() to return True when env vars are missing.",
        )

    def test_is_private_repo_returns_false_for_public(self):
        """urlopen returns {"private": false} — is_private_repo() returns False."""
        os.environ["GITHUB_TOKEN"] = "test-token"
        os.environ["GITHUB_REPOSITORY"] = "owner/repo"

        fake_body = json.dumps({"private": False}).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = fake_body
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = gdc.is_private_repo()

        self.assertFalse(
            result,
            "Expected is_private_repo() to return False for a public repo.",
        )

    def test_is_private_repo_returns_true_on_exception(self):
        """When urlopen raises an exception, is_private_repo() falls back to True."""
        os.environ["GITHUB_TOKEN"] = "test-token"
        os.environ["GITHUB_REPOSITORY"] = "owner/repo"

        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            result = gdc.is_private_repo()

        self.assertTrue(
            result,
            "Expected is_private_repo() to return True when urlopen raises.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 3 — CI-02: per-file report table
# ─────────────────────────────────────────────────────────────────────────────


class TestPerFileReportTable(unittest.TestCase):
    def test_build_comment_contains_report_table_when_html_exists(self):
        """html_count > 0 — build_comment() includes per-file table header."""
        result = gdc.build_comment(
            sections=[],
            files=["Workflow.yxmd"],
            html_count=1,
            short_sha="abc1234",
            timestamp="2026-03-15",
            totals={"added": 0, "removed": 0, "modified": 0},
            errors=0,
            run_url="https://github.com/owner/repo/actions/runs/123",
        )
        self.assertIn(
            "| Workflow File |",
            result,
            "Expected per-file table header '| Workflow File |' when html_count=1.",
        )

    def test_build_comment_has_no_table_when_no_html(self):
        """When html_count == 0, build_comment() must NOT include the per-file table."""
        result = gdc.build_comment(
            sections=[],
            files=["Workflow.yxmd"],
            html_count=0,
            short_sha="abc1234",
            timestamp="2026-03-15",
            totals={"added": 0, "removed": 0, "modified": 0},
            errors=0,
            run_url="https://github.com/owner/repo/actions/runs/123",
        )
        self.assertNotIn(
            "| Workflow File |",
            result,
            "Expected no per-file table in comment when html_count=0.",
        )


if __name__ == "__main__":
    unittest.main()
