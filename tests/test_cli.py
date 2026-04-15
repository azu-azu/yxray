"""CLI smoke tests for alteryx_git_companion.cli.

Uses CliRunner() — click 8.2+ always separates stdout and stderr streams.
- result.stdout: only typer.echo() without err=True, and --json output
- result.stderr: spinner (cleared), error messages, status summary

Invocation pattern: runner.invoke(app, [str(path_a), str(path_b)])
  The Typer app is a single-command app (`diff` is the default command).
  The CLI entry point `acd diff file_a file_b` maps to `acd [diff_args]`
  when invoked via CliRunner — no "diff" prefix in args list.

Zero subprocess imports — all tests run in-process via CliRunner.
"""

from __future__ import annotations

import json
import pathlib

from typer.testing import CliRunner

from alteryx_git_companion.cli import app
from tests.fixtures.cli import (
    IDENTICAL_YXMD,
    MALFORMED_XML,
    MINIMAL_YXMD_A,
    MINIMAL_YXMD_B,
    POSITION_YXMD_A,
    POSITION_YXMD_B,
)

runner = CliRunner(
    mix_stderr=False
)  # separate stdout and stderr so JSON tests parse cleanly


# ---------------------------------------------------------------------------
# Exit code tests
# ---------------------------------------------------------------------------


def test_diff_identical_files_exit_code_0(tmp_path: pathlib.Path) -> None:
    """Identical files produce exit code 0 (no differences)."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(IDENTICAL_YXMD)
    path_b.write_bytes(IDENTICAL_YXMD)

    result = runner.invoke(app, [str(path_a), str(path_b)])

    assert result.exit_code == 0


def test_diff_json_identical_files_emits_empty_json(tmp_path: pathlib.Path) -> None:
    """--json with identical files: exit code 0 AND valid empty JSON on stdout.

    Locked decision from CONTEXT.md: 'When no differences found and --json is used:
    print empty diff JSON (consistent output, no special-casing for downstream tools)'.
    """
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(IDENTICAL_YXMD)
    path_b.write_bytes(IDENTICAL_YXMD)

    result = runner.invoke(app, [str(path_a), str(path_b), "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["added"] == []
    assert data["removed"] == []
    assert data["modified"] == []
    assert "metadata" in data  # governance metadata always present


def test_diff_different_files_exit_code_1(tmp_path: pathlib.Path) -> None:
    """Different files produce exit code 1 (differences detected)."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)

    result = runner.invoke(app, [str(path_a), str(path_b)])

    assert result.exit_code == 1


def test_diff_missing_file_exit_code_2(tmp_path: pathlib.Path) -> None:
    """Missing file produces exit code 2 with error message on stderr."""
    path_b = tmp_path / "b.yxmd"
    path_b.write_bytes(MINIMAL_YXMD_B)

    result = runner.invoke(app, ["nonexistent.yxmd", str(path_b)])

    assert result.exit_code == 2
    assert "Error" in result.stderr


def test_diff_malformed_xml_exit_code_2(tmp_path: pathlib.Path) -> None:
    """Malformed XML produces exit code 2 with error message on stderr."""
    path_a = tmp_path / "bad.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MALFORMED_XML)
    path_b.write_bytes(MINIMAL_YXMD_B)

    result = runner.invoke(app, [str(path_a), str(path_b)])

    assert result.exit_code == 2
    assert "Error" in result.stderr


# ---------------------------------------------------------------------------
# Output file tests
# ---------------------------------------------------------------------------


def test_diff_writes_html_report_by_default(tmp_path: pathlib.Path) -> None:
    """Default invocation writes diff_report.html to --output path."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)
    output = tmp_path / "diff_report.html"

    result = runner.invoke(app, [str(path_a), str(path_b), "--output", str(output)])

    assert result.exit_code == 1
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content


def test_diff_html_report_contains_governance_metadata(tmp_path: pathlib.Path) -> None:
    """Generated HTML report contains governance footer with sha256 hash of file A."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)
    output = tmp_path / "diff_report.html"

    result = runner.invoke(app, [str(path_a), str(path_b), "--output", str(output)])

    assert result.exit_code == 1
    content = output.read_text(encoding="utf-8")
    assert "governance" in content  # <details id="governance"> block present
    # sha256_a must be a full 64-char hex string embedded in the HTML
    import hashlib

    expected_sha = hashlib.sha256(path_a.read_bytes()).hexdigest()
    assert expected_sha in content, (
        "Full 64-char SHA-256 of file A must appear in HTML report"
    )


def test_diff_output_flag_writes_custom_path(tmp_path: pathlib.Path) -> None:
    """--output flag writes HTML report to the specified custom path."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)
    custom = tmp_path / "custom_report.html"

    result = runner.invoke(app, [str(path_a), str(path_b), "--output", str(custom)])

    assert result.exit_code == 1
    assert custom.exists()


def test_diff_no_file_written_on_clean_diff(tmp_path: pathlib.Path) -> None:
    """When no differences found, no output file is written (exit 0, no file)."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(IDENTICAL_YXMD)
    path_b.write_bytes(IDENTICAL_YXMD)
    output = tmp_path / "diff_report.html"

    result = runner.invoke(app, [str(path_a), str(path_b), "--output", str(output)])

    assert result.exit_code == 0
    assert not output.exists()


# ---------------------------------------------------------------------------
# Flag behavior tests
# ---------------------------------------------------------------------------


def test_diff_json_flag_writes_to_stdout(tmp_path: pathlib.Path) -> None:
    """--json flag writes valid JSON to stdout with required top-level keys."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)

    result = runner.invoke(app, [str(path_a), str(path_b), "--json"])

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert "added" in data
    assert "removed" in data
    assert "modified" in data
    assert "metadata" in data
    assert len(data["metadata"]["sha256_a"]) == 64  # full 64-char SHA-256


def test_diff_quiet_flag_suppresses_stderr(tmp_path: pathlib.Path) -> None:
    """--quiet flag suppresses status summary; exit code still reflects diff status.

    Tests the behavioral guarantee: the 'N changes detected' summary line must not
    appear on stderr when --quiet is set. Uses substring check rather than empty-string
    assertion to avoid flakiness from Rich's TTY-detection behavior in CliRunner context
    (Rich may emit spinner artifacts depending on environment).
    """
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)
    output = tmp_path / "report.html"

    result = runner.invoke(
        app, [str(path_a), str(path_b), "--output", str(output), "--quiet"]
    )

    assert result.exit_code == 1
    # Verify behavioral guarantee: summary line is suppressed (not exact empty string,
    # which can be flaky due to Rich TTY detection in CliRunner)
    assert "changes detected" not in result.stderr


def test_diff_include_positions_detects_position_change(tmp_path: pathlib.Path) -> None:
    """--include-positions flag causes position-only changes to produce exit code 1."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(POSITION_YXMD_A)
    path_b.write_bytes(POSITION_YXMD_B)

    # Without flag: position-only change → exit code 0 (positions excluded by default)
    result_no_flag = runner.invoke(app, [str(path_a), str(path_b)])
    assert result_no_flag.exit_code == 0

    # With flag: position-only change → exit code 1 (positions included)
    result_with_flag = runner.invoke(
        app, [str(path_a), str(path_b), "--include-positions"]
    )
    assert result_with_flag.exit_code == 1
