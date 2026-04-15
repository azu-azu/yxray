#!/usr/bin/env python3
"""
generate_diff_comment.py
────────────────────────
Full-pipeline helper called by the pr-diff-report GitHub Actions workflow.

Responsibilities
  1. Discover changed .yxmd / .yxwz files via `git diff`
  2. Retrieve the base-branch version of each file with `git show`
  3. Run `acd --json --quiet`  → structured data for the Markdown comment
  4. Run `acd --output <name>.html` → self-contained interactive HTML report
     (uploaded as a workflow artifact by the YAML step that follows)
  5. Write  diff_comment.md  in the working directory

Environment variables (set by the workflow):
  BASE_REF            – base branch name, e.g. "main"
  HEAD_SHA            – full commit SHA of the PR head commit
  GITHUB_RUN_ID       – Actions run ID  (for the artifact download link)
  GITHUB_SERVER_URL   – usually "https://github.com"
  GITHUB_REPOSITORY   – "owner/repo"
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
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
    """Run `acd --json --quiet`. Returns (parsed_dict, exit_code, raw_text)."""
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
    """Run `acd --output <path>`. Returns True if HTML was written."""
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
# URL helpers
# ─────────────────────────────────────────────────────────────────────────────


def actions_run_url() -> str:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if run_id and repo:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return ""


def is_private_repo() -> bool:
    """Returns True if the workflow repository is private, False if public.
    Defaults to True (conservative) on any error."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        return True
    url = f"https://api.github.com/repos/{repo}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return bool(data.get("private", True))
    except Exception as exc:
        print(
            f"    WARNING: visibility check failed ({exc}) — defaulting to private",
            flush=True,
        )
        return True


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


def format_diff_section(filename: str, diff: dict) -> str:
    """Build a collapsible <details> block for one changed file."""
    added = diff.get("added", [])
    removed = diff.get("removed", [])
    modified = diff.get("modified", [])

    badge = (
        f"🟢 **{len(added)}** added &nbsp;·&nbsp; "
        f"🔴 **{len(removed)}** removed &nbsp;·&nbsp; "
        f"🟡 **{len(modified)}** modified"
    )

    lines: list[str] = [
        "<details>",
        f"<summary><b>🔄 <code>{filename}</code></b> &nbsp;—&nbsp; {badge}</summary>",
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
    html_count: int,
    short_sha: str,
    timestamp: str,
    totals: dict[str, int],
    errors: int,
    run_url: str = "",
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

    # HTML report table — only shown when HTML reports were generated.
    # Uses per-file table with visibility-appropriate note.
    html_block: list[str] = []
    if html_count > 0 and run_url:
        private = is_private_repo()
        note = "Login required to download" if private else "No login required"
        html_block = [
            "> ### 📄 Interactive HTML Reports",
            ">",
            "> | Workflow File | Report |",
            "> |--------------|--------|",
        ]
        for fname in files:
            html_block.append(f"> | `{fname}` | [View report ↗]({run_url}) |")
        html_block += [
            ">",
            f"> *({note} · Interactive workflow graph · per-tool field diffs)*",
            "",
        ]

    lines = [
        "<!-- acd-diff-report -->",
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
        "_Generated by [Alteryx Canvas Diff (acd)](https://github.com/Laxmi884/alteryx_git_companion) via GitHub Actions._",  # noqa: E501
    ]
    return "\n".join(lines)


def build_no_files_comment(short_sha: str, timestamp: str) -> str:
    return "\n".join(
        [
            "<!-- acd-diff-report -->",
            "## 🔍 Alteryx Workflow Diff Report",
            "",
            f"> 🤖 **Automated report** &nbsp;|&nbsp; Commit: `{short_sha}` &nbsp;|&nbsp; {timestamp}",  # noqa: E501
            "",
            "No Alteryx workflow files (`.yxmd` / `.yxwz`) were modified in this pull request.",  # noqa: E501
            "",
            "---",
            "_Generated by [Alteryx Canvas Diff (acd)](https://github.com/Laxmi884/alteryx_git_companion) via GitHub Actions._",  # noqa: E501
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
    workspace = Path(os.environ.get("GITHUB_WORKSPACE", "."))

    run(["git", "fetch", "--quiet", "origin", base_ref])

    files = git_changed_files(base_ref)
    if not files:
        print("No Alteryx files changed — writing minimal comment.", flush=True)
        Path("diff_comment.md").write_text(
            build_no_files_comment(short_sha, timestamp), encoding="utf-8"
        )
        return 0

    print(f"\n🔍 Processing {len(files)} Alteryx file(s)…\n", flush=True)

    sections: list[str] = []
    html_count = 0
    totals = {"added": 0, "removed": 0, "modified": 0}
    error_count = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        for filepath in files:
            filename = Path(filepath).name
            stem = Path(filepath).stem.replace(" ", "_")
            safe_name = filename.replace(" ", "_")
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
                print("    → Deleted in this PR", flush=True)
                sections.append(f"### 🗑️ `{filename}` — Deleted in this PR\n")
                continue

            # ── HTML report ───────────────────────────────────────────────────
            html_out = str(workspace / f"diff_{stem}.html")
            if run_acd_html(str(base_tmp), str(head_path), html_out):
                html_count += 1

            # ── JSON diff (for Markdown comment body) ─────────────────────────
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
                sections.append(format_diff_section(filename, diff))

            else:
                error_count += 1
                snippet = raw[:400] + ("…" if len(raw) > 400 else "")
                print(f"    → Error (exit {exit_code})", flush=True)
                sections.append(
                    f"### ❌ `{filename}` — Error (exit code `{exit_code}`)\n"
                    f"```\n{snippet}\n```\n"
                )

    print(f"\n📄 HTML reports generated: {html_count}", flush=True)

    comment = build_comment(
        sections,
        files,
        html_count,
        short_sha,
        timestamp,
        totals,
        error_count,
        run_url=actions_run_url(),
    )
    Path("diff_comment.md").write_text(comment, encoding="utf-8")
    print(f"✅ diff_comment.md written ({len(sections)} section(s))\n", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
