#!/usr/bin/env python3
"""
generate_diff_comment.py  (GitLab CI version)
─────────────────────────────────────────────
Same logic as the GitHub Actions version, adapted for GitLab CI/CD env vars.

Responsibilities
  1. Discover changed .yxmd / .yxwz files via `git diff`
  2. Retrieve the base-branch version of each file with `git show`
  3. Run `acd --json --quiet`  → structured data for the Markdown comment
  4. Run `acd --output <name>.html` → self-contained interactive HTML report
     (served directly via GitLab CI artifacts + expose_as — one-click open)
  5. Write  diff_comment.md  in the working directory

GitLab CI environment variables used (set automatically):
  CI_MERGE_REQUEST_TARGET_BRANCH_NAME  – base branch (e.g. "main")
  CI_COMMIT_SHA                        – full commit SHA of the MR head
  CI_JOB_ID                            – job ID (for artifact URL)
  CI_PROJECT_ID                        – project numeric ID (for API calls)
  CI_SERVER_URL                        – e.g. "https://gitlab.com"
  CI_PROJECT_PATH                      – "namespace/project"

Passed explicitly via the job `variables:` block:
  BASE_REF   – alias for CI_MERGE_REQUEST_TARGET_BRANCH_NAME
  HEAD_SHA   – alias for CI_COMMIT_SHA
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Shell helpers
# ─────────────────────────────────────────────────────────────────────────────


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, **kwargs)


def git_changed_files(base_ref: str) -> list[str]:
    result = run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMRD",
            f"origin/{base_ref}...HEAD",
            "--",
            "*.yxmd",
            "*.yxwz",
        ],
        capture_output=True,
        text=True,
    )
    return [f for f in result.stdout.splitlines() if f.strip()]


def git_base_bytes(filepath: str, base_ref: str) -> bytes | None:
    result = run(
        ["git", "show", f"origin/{base_ref}:{filepath}"],
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


# ─────────────────────────────────────────────────────────────────────────────
# acd runners
# ─────────────────────────────────────────────────────────────────────────────


def run_acd_json(base_path: str, head_path: str) -> tuple[dict | None, int, str]:
    result = run(
        ["acd", base_path, head_path, "--json", "--quiet"],
        capture_output=True,
        text=True,
    )
    raw = (result.stdout or "") + (result.stderr or "")
    parsed: dict | None = None
    if result.returncode in (0, 1) and result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            print(f"    WARNING: JSON parse error — {exc}", flush=True)
    return parsed, result.returncode, raw


def run_acd_html(base_path: str, head_path: str, output_path: str) -> bool:
    result = run(
        ["acd", base_path, head_path, "--output", output_path],
        capture_output=True,
        text=True,
    )
    ok = result.returncode in (0, 1) and Path(output_path).exists()
    if ok:
        print(f"    HTML → {output_path}", flush=True)
    else:
        print(
            f"    HTML failed (exit {result.returncode}): {result.stderr[:200]}",
            flush=True,
        )
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# GitLab artifact URL builder
# ─────────────────────────────────────────────────────────────────────────────


def artifact_url(html_filename: str) -> str:
    """
    Build the direct GitLab job artifact URL for an HTML file.
    This URL opens the file directly in the browser (no ZIP download).

    Shape: <server>/<project_path>/-/jobs/<job_id>/artifacts/file/<filename>
    """
    server = os.environ.get("CI_SERVER_URL", "https://gitlab.com").rstrip("/")
    project_path = os.environ.get("CI_PROJECT_PATH", "")
    job_id = os.environ.get("CI_JOB_ID", "")
    if server and project_path and job_id:
        return f"{server}/{project_path}/-/jobs/{job_id}/artifacts/file/diff_reports/{html_filename}"  # noqa: E501
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Markdown formatters
# ─────────────────────────────────────────────────────────────────────────────


def _trunc(value: object, max_len: int = 80) -> str:
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def _tool_short(full_type: str) -> str:
    return full_type.split(".")[-1] if "." in full_type else full_type


def _tool_table(tools: list[dict]) -> list[str]:
    rows = [
        "| Tool ID | Type | Config snapshot |",
        "|--------:|------|-----------------|",
    ]
    for t in tools:
        cfg = _trunc(json.dumps(t.get("config", {}), separators=(",", ":")))
        rows.append(
            f"| `{t['tool_id']}` | `{_tool_short(t.get('tool_type', ''))}` | `{cfg}` |"
        )
    return rows


def format_diff_section(filename: str, diff: dict, html_url: str | None) -> str:
    added = diff.get("added", [])
    removed = diff.get("removed", [])
    modified = diff.get("modified", [])

    badge = (
        f"🟢 **{len(added)}** added &nbsp;·&nbsp; "
        f"🔴 **{len(removed)}** removed &nbsp;·&nbsp; "
        f"🟡 **{len(modified)}** modified"
    )

    # Use <a href> inside <summary> — GitLab also renders HTML anchor tags there
    preview_a = (
        f' &nbsp;<a href="{html_url}">🌐 Open interactive report ↗</a>'
        if html_url
        else ""
    )

    lines: list[str] = [
        "<details>",
        f"<summary><b>🔄 <code>{filename}</code></b> &nbsp;—&nbsp; {badge}{preview_a}</summary>",  # noqa: E501
        "",
    ]

    if added:
        lines += ["**➕ Added Tools**", ""] + _tool_table(added) + [""]
    if removed:
        lines += ["**➖ Removed Tools**", ""] + _tool_table(removed) + [""]
    if modified:
        lines += ["**✏️ Modified Tools**", ""]
        for t in modified:
            lines.append(
                f"- **Tool `{t['tool_id']}`** (`{_tool_short(t.get('tool_type', ''))}`)"
            )
            for fd in t.get("field_diffs", []):
                b = _trunc(fd.get("before", ""), 60)
                a = _trunc(fd.get("after", ""), 60)
                lines.append(f"  - `{fd['field']}`: `{b}` → `{a}`")
        lines.append("")

    lines += ["</details>", ""]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Comment assembly
# ─────────────────────────────────────────────────────────────────────────────


def build_comment(
    sections: list[str],
    files: list[str],
    report_links: list[tuple[str, str]],  # [(display_name, direct_url), …]
    short_sha: str,
    timestamp: str,
    totals: dict[str, int],
    errors: int,
) -> str:
    parts: list[str] = []
    if totals["added"]:
        parts.append(f"🟢 **{totals['added']}** tool(s) added")
    if totals["removed"]:
        parts.append(f"🔴 **{totals['removed']}** tool(s) removed")
    if totals["modified"]:
        parts.append(f"🟡 **{totals['modified']}** tool(s) modified")
    if errors:
        parts.append(f"❌ **{errors}** file(s) errored")
    summary = (
        " &nbsp;·&nbsp; ".join(parts) if parts else "No tool-level changes detected."
    )

    # ── HTML report callout ──────────────────────────────────────────────────
    # On GitLab, artifact URLs open directly in the browser (no ZIP needed).
    # GitLab also adds an "Artifacts" button in the MR via `expose_as`.
    html_block: list[str] = []
    if report_links:
        html_block = [
            "> ### 🌐 Interactive HTML Reports",
            ">",
            "> Click a link below to open the diff report **directly in your browser**",
            "> — no download or ZIP required (GitLab serves job artifacts inline).",
            ">",
        ]
        for fname, url in report_links:
            html_block.append(f"> - 📄 [{fname}]({url})")
        html_block += [
            ">",
            "> *(Interactive workflow graph · per-tool field diffs · ALCOA+ footer)*",
            "",
        ]

    lines = [
        "## 🔍 Alteryx Workflow Diff Report",
        "",
        f"> 🤖 **Automated report** &nbsp;|&nbsp; Commit: `{short_sha}` &nbsp;|&nbsp; {timestamp}",  # noqa: E501
        "",
        f"**{len(files)} Alteryx file(s) analysed** &nbsp;—&nbsp; {summary}",
        "",
        *html_block,
        "---",
        "",
        *sections,
        "---",
        "",
        "_Generated by [Alteryx Canvas Diff (acd)](https://github.com/Laxmi884/alteryx_git_companion) via GitLab CI._",  # noqa: E501
    ]
    return "\n".join(lines)


def build_no_files_comment(short_sha: str, timestamp: str) -> str:
    return "\n".join(
        [
            "## 🔍 Alteryx Workflow Diff Report",
            "",
            f"> 🤖 **Automated report** &nbsp;|&nbsp; Commit: `{short_sha}` &nbsp;|&nbsp; {timestamp}",  # noqa: E501
            "",
            "No Alteryx workflow files (`.yxmd` / `.yxwz`) were modified in this merge request.",  # noqa: E501
            "",
            "---",
            "_Generated by [Alteryx Canvas Diff (acd)](https://github.com/Laxmi884/alteryx_git_companion) via GitLab CI._",  # noqa: E501
        ]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    base_ref = os.environ.get("BASE_REF", "main")
    head_sha = os.environ.get("HEAD_SHA", "unknown")
    short_sha = head_sha[:7]
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    # GitLab CI clones with a shallow depth by default. Fetch base branch.
    run(["git", "fetch", "origin", base_ref])

    files = git_changed_files(base_ref)
    if not files:
        print("No Alteryx files changed — writing minimal comment.", flush=True)
        Path("diff_comment.md").write_text(
            build_no_files_comment(short_sha, timestamp), encoding="utf-8"
        )
        return 0

    print(f"\n🔍 Processing {len(files)} Alteryx file(s)…\n", flush=True)

    sections: list[str] = []
    report_links: list[tuple[str, str]] = []
    totals = {"added": 0, "removed": 0, "modified": 0}
    error_count = 0

    reports_dir = Path("diff_reports")
    reports_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        for filepath in files:
            filename = Path(filepath).name
            stem = Path(filepath).stem.replace(" ", "_")
            safe_name = filename.replace(" ", "_")
            html_name = f"diff_{stem}.html"
            html_out_path = str(reports_dir / html_name)
            print(f"▸ {filename}", flush=True)

            # ── Base-branch version ───────────────────────────────────────────
            base_bytes = git_base_bytes(filepath, base_ref)
            if base_bytes is None:
                print("    → New file (no baseline)", flush=True)
                sections.append(
                    f"### 🆕 `{filename}` — New file (no baseline to compare)\n"
                )
                continue

            base_tmp = Path(tmpdir) / f"base_{safe_name}"
            base_tmp.write_bytes(base_bytes)

            # ── Head-branch version ───────────────────────────────────────────
            head_path = Path(filepath)
            if not head_path.exists():
                print("    → Deleted in this MR", flush=True)
                sections.append(f"### 🗑️ `{filename}` — Deleted in this MR\n")
                continue

            # ── HTML report (direct artifact URL — opens in browser on GitLab) ─
            html_ok = run_acd_html(str(base_tmp), str(head_path), html_out_path)
            html_url: str | None = None
            if html_ok:
                html_url = artifact_url(html_name)
                if html_url:
                    report_links.append((filename, html_url))

            # ── JSON diff ────────────────────────────────────────────────────
            diff, exit_code, raw = run_acd_json(str(base_tmp), str(head_path))

            if exit_code == 0:
                print("    → No differences", flush=True)
                sections.append(f"### ✅ `{filename}` — No differences found\n")

            elif exit_code == 1 and diff is not None:
                a = len(diff.get("added", []))
                r = len(diff.get("removed", []))
                m = len(diff.get("modified", []))
                print(f"    → Diff: +{a} -{r} ~{m}", flush=True)
                totals["added"] += a
                totals["removed"] += r
                totals["modified"] += m
                sections.append(format_diff_section(filename, diff, html_url))

            else:
                error_count += 1
                snippet = raw[:400] + ("…" if len(raw) > 400 else "")
                print(f"    → Error (exit {exit_code})", flush=True)
                sections.append(
                    f"### ❌ `{filename}` — Error (exit code `{exit_code}`)\n"
                    f"```\n{snippet}\n```\n"
                )

    print(f"\n📄 HTML reports: {len(report_links)}", flush=True)
    comment = build_comment(
        sections, files, report_links, short_sha, timestamp, totals, error_count
    )
    Path("diff_comment.md").write_text(comment, encoding="utf-8")
    print(f"✅ diff_comment.md written ({len(sections)} section(s))\n", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
