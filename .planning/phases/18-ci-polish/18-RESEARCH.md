# Phase 18: CI Polish - Research

**Researched:** 2026-03-15
**Domain:** GitHub Actions YAML + Python CI scripting, GitLab CI YAML, CI template packaging
**Confidence:** HIGH

## Summary

Phase 18 is a targeted polish pass on existing CI integration templates — not a greenfield build. Every file
already exists in `/alteryx/` (the live example Alteryx workflow repo). The work is:

1. Rewrite the "Post comment" step in `pr-diff-report.yml` to find-or-update instead of always-create.
2. Rewrite `generate_diff_comment.py` (GitHub version) to detect public/private repo visibility and build the
   appropriate HTML report link (htmlpreview URL vs ZIP artifact link).
3. Delete `test-job` and the `test` stage from `.gitlab-ci.yml` (one line of cleanup).
4. Create `ci-templates/` in the `alteryx_diff` repo, mirror all CI files there, and write `README.md` for
   non-technical Alteryx analysts.

The find-or-update comment pattern is well-established in the GitHub Actions ecosystem. The marker technique
(`<!-- acd-diff-report -->`) embedded as a hidden HTML comment is the canonical approach — it keeps the comment
invisible to human reviewers while providing a reliable search key.

**Primary recommendation:** Implement find-or-update using `actions/github-script@v7` directly (already present
in the workflow) with `github.rest.issues.listComments` + `.find()` + `updateComment`/`createComment`. No third-
party action needed. Detect repo visibility via `github.rest.repos.get()` inside the same script step, using the
`private` boolean from the response.

## User Constraints

<user_constraints>
### Locked Decisions

#### Comment Update Logic (CI-01)
- Marker: `<!-- acd-diff-report -->` embedded as first line of every comment body
- Pattern: list PR comments → find one with marker → `updateComment` if found, `createComment` if not
- Always post/update even when no Alteryx files changed (keeps marker alive for future pushes)
- Retain commit SHA + UTC timestamp in comment header
- GitLab CI: one comment per push is acceptable — find-or-update NOT required for GitLab

#### HTML Report Delivery (CI-02)
- No PNG embedding — interactive HTML report is the deliverable; PNG was dropped
- Public repos: embed `htmlpreview.github.io` direct link in PR comment
- Private repos: provide prominent one-click ZIP download link per file
- Python helper auto-detects public vs private via GitHub API and builds appropriate link type
- Comment shows per-file table: filename column + download/preview link column
- GitLab: existing `expose_as` artifact approach already gives one-click browser open — no changes needed

#### GitLab CI Cleanup (CI-03)
- Remove `test-job` stage and its placeholder `echo` script entirely
- Remove the now-unused `test` stage from the `stages:` list
- Keep the `diff` stage and `alteryx-diff` job as-is

#### ci-templates/ Directory Structure
- `ci-templates/` lives in the `alteryx_diff` repo — canonical distributable location
- Full mirrored directory structure:
  ```
  ci-templates/
  ├── .github/
  │   ├── workflows/
  │   │   └── pr-diff-report.yml
  │   └── scripts/
  │       └── generate_diff_comment.py
  ├── .gitlab-ci.yml
  ├── .gitlab/
  │   └── scripts/
  │       └── generate_diff_comment.py
  └── README.md
  ```
- `/alteryx/` workflow repo keeps its own CI config as live working example — both exist independently

#### README Scope (CI-04)
- Primary audience: non-technical Alteryx analysts (no assumed GitHub/GitLab CI expertise)
- Step-by-step with exact copy-paste instructions
- GitHub section covers: prerequisites, public vs private repo path, GITHUB_TOKEN (automatic) vs GH_PAT (private), troubleshooting
- GitLab section covers (equal depth): GITLAB_TOKEN setup, Project Access Token creation, `expose_as` artifact feature, troubleshooting

### Claude's Discretion
- Exact markdown formatting and section ordering in README
- Whether to add a "Quick Start" summary at the top of README or jump straight into steps
- Specific wording of copy-paste instructions
- Whether to split GitHub and GitLab README into separate files or keep as one README with sections

### Deferred Ideas (OUT OF SCOPE)
- GitLab find-or-update comment pattern
- Automated release process publishing `ci-templates/` as a versioned download
- GitHub Pages deployment option for private repos
</user_constraints>

## Phase Requirements

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CI-01 | GitHub Actions workflow updates the existing PR comment on each push instead of posting a new one | find-or-update via `github.rest.issues.listComments` + marker pattern; confirmed works with `actions/github-script@v7` already present in workflow |
| CI-02 | GitHub Actions embeds workflow graph diff as inline HTML report link — no ZIP attachment required | htmlpreview.github.io URL for public repos; artifact run URL for private repos; visibility detected via `github.rest.repos.get()` returning `private` boolean |
| CI-03 | GitLab CI config removes the placeholder test-job step | Single edit: remove `test-job` block + `test` from `stages:` list |
| CI-04 | ci-templates/README.md provides complete step-by-step setup for both GitHub Actions and GitLab CI | Non-technical audience; copy-paste instructions; public/private paths; token setup for both platforms |
</phase_requirements>

## Standard Stack

### Core
| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| `actions/github-script` | v7 | JavaScript wrapper over Octokit REST API inside workflow YAML | Already in workflow; covers listComments, updateComment, createComment, repos.get — no extra dependency |
| `actions/checkout` | v4 | Repo checkout with full history | Already in workflow |
| `actions/setup-python` | v5 | Python 3.11 runtime | Already in workflow |
| `actions/upload-artifact` | v4 | Upload HTML reports as downloadable ZIP artifact | Already in workflow |
| Python 3.11 stdlib (`os`, `subprocess`, `json`, `pathlib`, `tempfile`, `urllib.request`) | 3.11 | Helper script runtime — no pip extras needed | Scripts already use stdlib only |

### No New Dependencies
The existing workflow already pins all required actions. The Python helper uses only stdlib. No `pip install` changes are needed for CI-01 or CI-02.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom `github-script` inline JS | `peter-evans/find-comment` + `peter-evans/create-or-update-comment` actions | Third-party actions add supply-chain surface; inline JS uses already-trusted `actions/github-script@v7` |
| `urllib.request` for visibility check inside Python | `requests` library | stdlib avoids pip dependency; `urllib.request` is sufficient for a single unauthenticated GET |

## Architecture Patterns

### Pattern 1: Find-or-Update Comment via Marker (CI-01)

**What:** Embed `<!-- acd-diff-report -->` as the first line of every generated comment. On each push, list all PR
comments, find the one whose body contains the marker, update it; if not found, create a new comment.

**When to use:** Any CI bot that should maintain exactly one comment per PR regardless of push count.

**Implementation location:** Step 5 of `.github/workflows/pr-diff-report.yml` (the existing "Post diff report as
PR comment" step) — rewrite from `createComment` only to find-or-update.

**Example (inline `github-script` JS):**
```javascript
// Source: GitHub Actions community pattern, verified against Octokit REST API docs
const marker = '<!-- acd-diff-report -->';
const fs = require('fs');
const commentFile = require('path').join(process.env.GITHUB_WORKSPACE, 'diff_comment.md');
const sha = context.payload.pull_request.head.sha.substring(0, 7);
const ts  = new Date().toUTCString();

let body;
if (fs.existsSync(commentFile)) {
  body = marker + '\n' + fs.readFileSync(commentFile, 'utf8');
} else {
  body = marker + '\n## Alteryx Workflow Diff Report\n\n> Could not generate diff report.\n\nCommit: `' + sha + '` | ' + ts;
}

const { data: comments } = await github.rest.issues.listComments({
  owner:        context.repo.owner,
  repo:         context.repo.repo,
  issue_number: context.issue.number,
});

const existing = comments.find(c => c.body && c.body.includes(marker));

if (existing) {
  await github.rest.issues.updateComment({
    owner:      context.repo.owner,
    repo:       context.repo.repo,
    comment_id: existing.id,
    body,
  });
  core.info('Comment updated: ' + existing.html_url);
} else {
  const result = await github.rest.issues.createComment({
    owner:        context.repo.owner,
    repo:         context.repo.repo,
    issue_number: context.issue.number,
    body,
  });
  core.info('Comment created: ' + result.data.html_url);
}
```

**Octokit methods used (all part of `actions/github-script@v7`):**
- `github.rest.issues.listComments({ owner, repo, issue_number })`
- `github.rest.issues.updateComment({ owner, repo, comment_id, body })`
- `github.rest.issues.createComment({ owner, repo, issue_number, body })`

### Pattern 2: Repo Visibility Detection (CI-02)

**What:** Determine whether the workflow repo is public or private. Use `github.rest.repos.get()` in the same
`github-script` step, OR use a GitHub API call from within the Python helper via `GITHUB_TOKEN` environment
variable.

**Decision from CONTEXT.md:** The Python helper (`generate_diff_comment.py`) auto-detects public vs private.

**Implementation approach in Python helper:**
```python
# Source: GitHub REST API docs — GET /repos/{owner}/{repo} returns `private: bool`
import urllib.request, json, os

def is_private_repo() -> bool:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo  = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        return True  # safe default: treat as private if unknown
    url = f"https://api.github.com/repos/{repo}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            return data.get("private", True)
    except Exception:
        return True  # safe default
```

The `GITHUB_TOKEN` env var must be passed from the workflow step:
```yaml
- name: Generate diff comment
  run: python3 .github/scripts/generate_diff_comment.py
  env:
    BASE_REF:     ${{ github.base_ref }}
    HEAD_SHA:     ${{ github.event.pull_request.head.sha }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Note:** The existing workflow already sets `GITHUB_TOKEN` implicitly for `github-script` steps, but the Python
subprocess step needs it passed explicitly via `env:`.

### Pattern 3: htmlpreview.github.io URL Construction (CI-02, public repos)

**URL format (verified):**
```
https://htmlpreview.github.io/?https://github.com/{owner}/{repo}/blob/{branch}/{path_to_html}
```

**Challenge:** The HTML diff reports are uploaded as workflow artifacts — they are NOT committed to the repo branch.
`htmlpreview.github.io` requires a committed file on a branch, not a workflow artifact. Therefore:

- **Public repos:** The htmlpreview approach works only if the HTML file is committed to the repo.
  Since reports are artifacts (not committed), the correct public-repo link is the artifact download
  link from the Actions run (same as private repos) — but presented more prominently.

**Revised understanding (HIGH confidence):**

The CONTEXT.md states "For public repos: embed a direct `htmlpreview.github.io` link". However, workflow
artifacts are not repo blobs — htmlpreview.github.io cannot serve them. The feasible distinction is:

| Repo type | Link type | How |
|-----------|-----------|-----|
| Public | Direct link to Actions run (artifact ZIP) | `GITHUB_SERVER_URL/{repo}/actions/runs/{run_id}` |
| Private | Direct link to Actions run (artifact ZIP) | Same URL format |

The user-visible difference can be in _presentation_ (more prominent link, per-file table) rather than in the
URL scheme. The Python helper builds the link type per the `is_private_repo()` result.

**Alternative if HTML must be previewed without download:** Upload the HTML as a GitHub Pages artifact (requires
`pages: write` permission and a separate deployment job) — this is listed as deferred in CONTEXT.md and is OUT OF
SCOPE.

**Practical implementation for CI-02:** The Python helper builds a per-file table in the comment markdown showing
each changed Alteryx file with a link to its HTML report. For public repos the link can optionally note that no
download is needed (direct run URL); for private repos, note the download step. The key deliverable is a
_per-file table_ rather than a single bulk artifact link.

### Pattern 4: ci-templates/ Directory as Distributable Package

**What:** New top-level directory in `alteryx_diff` repo. Pure file addition — no code connection to existing
app. Contents are copies/adaptations of `/alteryx/` CI files.

**Copy order:**
1. Update `/alteryx/` files first (CI-01, CI-02, CI-03 changes)
2. Copy updated files to `ci-templates/` (parameterize repo URLs as instructions)
3. Write `ci-templates/README.md` (CI-04)

**Parameterization:** The `pr-diff-report.yml` in `ci-templates/` should use placeholder comments like
`# Replace with your repo: github.com/YOUR-ORG/YOUR-REPO` wherever the live example has hardcoded references.
The `generate_diff_comment.py` scripts are environment-variable-driven and need no changes for redistribution.

### Anti-Patterns to Avoid

- **Always-create comment:** The original `createComment`-only pattern in the current workflow creates one comment
  per push. Replace it entirely.
- **PNG embedding:** Decision has been made to drop PNG — do not re-introduce any `acd --png` call or image
  upload step.
- **htmlpreview for artifacts:** Workflow artifacts are not repo blobs; htmlpreview.github.io cannot serve them.
  Do not construct `htmlpreview.github.io/?...artifact_url...` links.
- **Hardcoded repo names in ci-templates/:** Template files must be repo-agnostic. The Python scripts already use
  env vars; the YAML files should use `${{ github.repository }}` / GitLab auto-vars wherever the alteryx live-
  example has a specific org/repo name.
- **Keeping `test-job` in GitLab CI:** A placeholder `echo` job that does nothing creates pipeline noise and
  wastes runner minutes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Find-or-update comment | Custom REST wrapper | `github.rest.issues.listComments` + `.find()` in `github-script@v7` | Octokit methods already available; no extra action needed |
| Repo visibility check | Complex heuristic | `github.rest.repos.get()` → `.data.private` | One API call; reliable; already authenticated |
| Artifact URL construction | Opaque artifact ID lookup | Existing `actions_run_url()` function in Python helper | Already implemented and correct |
| GitLab MR comment posting | New curl pattern | Existing `curl` + `GITLAB_TOKEN` block in `.gitlab-ci.yml` | Already working; no changes for CI-03 |

## Common Pitfalls

### Pitfall 1: listComments Pagination
**What goes wrong:** `listComments` returns a maximum of 30 comments by default. On long PRs with many bot
comments, the marker comment may not appear in the first page.
**Why it happens:** GitHub REST API paginates list endpoints.
**How to avoid:** Pass `per_page: 100` to `listComments`. For typical PRs this covers all comments. If PRs ever
exceed 100 comments, add `octokit.paginate` — but this is unnecessary for this use case.
**Warning signs:** Comment gets duplicated after 30+ comments on a PR.

```javascript
const { data: comments } = await github.rest.issues.listComments({
  owner:        context.repo.owner,
  repo:         context.repo.repo,
  issue_number: context.issue.number,
  per_page:     100,
});
```

### Pitfall 2: GITHUB_TOKEN Scope for repos.get
**What goes wrong:** Python subprocess cannot call GitHub API — `GITHUB_TOKEN` not available in environment.
**Why it happens:** The `GITHUB_TOKEN` is only automatically available to `github-script` steps and explicitly
injected steps. Python `run:` steps don't inherit it by default.
**How to avoid:** Add `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}` to the `env:` block of the "Generate diff
comment" step. The existing workflow does not currently pass this variable to the Python step.
**Warning signs:** `is_private_repo()` returns `True` (safe default) even for public repos — links never use
htmlpreview.

### Pitfall 3: Marker in Comment Body vs File
**What goes wrong:** Marker is written to `diff_comment.md` file, but the JS step prepends the marker when
reading the file — resulting in double markers or missing markers.
**Why it happens:** The Python helper writes `diff_comment.md`; the JS step reads it and builds the final body.
If both add the marker, it appears twice.
**How to avoid:** Single ownership — either the Python helper writes the marker as the first line of
`diff_comment.md`, OR the JS step prepends it. Not both. Recommend: JS step prepends the marker when reading the
file content. Python helper generates content without the marker.

### Pitfall 4: GitLab `expose_as` and `paths` Mismatch
**What goes wrong:** GitLab `expose_as` requires `paths:` to include the file/directory — if `paths:` doesn't
match the actual output, the "View exposed artifact" button appears but links to a 404.
**Why it happens:** The existing `.gitlab-ci.yml` already has `paths: - "diff_reports/"` matching the Python
helper's `reports_dir = Path("diff_reports")`. This is already correct.
**How to avoid:** When copying to `ci-templates/`, preserve the `paths: - "diff_reports/"` in `.gitlab-ci.yml`.
**Warning signs:** "View exposed artifact" button shows in GitLab MR but clicking it gives 404.

### Pitfall 5: ci-templates/ Hardcoded References
**What goes wrong:** User copies `ci-templates/.github/workflows/pr-diff-report.yml` but the file has
`Laxmi884/alteryx_diff.git` hardcoded as the `pip install` source.
**Why it happens:** The live workflow has a hardcoded PyPI/GitHub install path.
**How to avoid:** The `ci-templates/` copy should use a generic placeholder or the PyPI package name (if acd is
published on PyPI). Add a `# TODO: replace with PyPI install once published: pip install alteryx-canvas-diff`
comment or use the public GitHub URL without org-specific hardcoding.

### Pitfall 6: README Scope Creep
**What goes wrong:** README tries to explain git, GitHub, pull requests — becomes a git tutorial.
**Why it happens:** "Non-technical Alteryx analyst" audience tempts over-explanation.
**How to avoid:** Assume the user knows how to open a file and copy-paste text. Assume they have a GitHub/GitLab
account. Explain only CI-specific concepts: what a workflow file is, where to put it, what secrets/tokens to
create.

## Code Examples

### Find-or-Update Comment Step (complete workflow step)

```yaml
# Source: GitHub Actions Octokit REST API — issues.listComments / updateComment / createComment
- name: Post or update diff report PR comment
  uses: actions/github-script@v7
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    script: |
      const fs   = require('fs');
      const path = require('path');

      const MARKER      = '<!-- acd-diff-report -->';
      const commentFile = path.join(process.env.GITHUB_WORKSPACE, 'diff_comment.md');
      const sha         = context.payload.pull_request.head.sha.substring(0, 7);
      const ts          = new Date().toUTCString();

      let content;
      if (fs.existsSync(commentFile)) {
        content = fs.readFileSync(commentFile, 'utf8');
      } else {
        content = [
          '## Alteryx Workflow Diff Report',
          '',
          '> Could not generate diff report. Check the Actions log for details.',
          '',
          'Commit: `' + sha + '` | ' + ts,
        ].join('\n');
      }

      const body = MARKER + '\n' + content;

      const { data: comments } = await github.rest.issues.listComments({
        owner:        context.repo.owner,
        repo:         context.repo.repo,
        issue_number: context.issue.number,
        per_page:     100,
      });

      const existing = comments.find(c => c.body && c.body.includes(MARKER));

      if (existing) {
        await github.rest.issues.updateComment({
          owner:      context.repo.owner,
          repo:       context.repo.repo,
          comment_id: existing.id,
          body,
        });
        core.info('Updated existing comment: ' + existing.html_url);
      } else {
        const result = await github.rest.issues.createComment({
          owner:        context.repo.owner,
          repo:         context.repo.repo,
          issue_number: context.issue.number,
          body,
        });
        core.info('Created new comment: ' + result.data.html_url);
      }
```

### Repo Visibility Detection in Python Helper

```python
# Source: GitHub REST API docs — GET /repos/{owner}/{repo}
import urllib.request, json, os

def is_private_repo() -> bool:
    """Returns True if the workflow repository is private, False if public."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo  = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        return True  # conservative default
    url = f"https://api.github.com/repos/{repo}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return bool(data.get("private", True))
    except Exception as exc:
        print(f"    WARNING: visibility check failed ({exc}) — defaulting to private", flush=True)
        return True
```

### Per-File HTML Report Table in Comment Markdown

```python
# Generated markdown table for the comment body (public repo path)
def html_report_block_public(report_links: list[tuple[str, str]]) -> list[str]:
    """report_links: [(display_name, artifact_run_url), ...]"""
    lines = [
        "> ### 📄 Interactive HTML Reports",
        ">",
        "> | Workflow File | Report |",
        "> |--------------|--------|",
    ]
    for fname, url in report_links:
        lines.append(f"> | `{fname}` | [Open report ↗]({url}) |")
    lines += [">", "> *(Interactive workflow graph · per-tool field diffs)*", ""]
    return lines
```

### GitLab CI Cleanup (what the diff looks like)

Before:
```yaml
stages:
  - test
  - diff

test-job:
  stage: test
  script:
    - echo "Pipeline triggered successfully."
```

After:
```yaml
stages:
  - diff
```

(Remove `test-job` block entirely and remove `test` from `stages:` list.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `createComment` always | `listComments` + find-or-update | Community pattern, stable 2022+ | One comment per PR instead of N |
| Single bulk artifact link | Per-file table with individual links | This phase | Reviewers see which file changed |
| `test-job` placeholder in GitLab CI | Removed | This phase | Cleaner pipeline, no wasted runner minutes |

**No deprecated APIs in scope.** `actions/github-script@v7` and `actions/upload-artifact@v4` are current
(upload-artifact v3 is deprecated as of 2024-11-30).

## Open Questions

1. **htmlpreview.github.io vs artifact URL for public repos**
   - What we know: htmlpreview.github.io requires the HTML file to be committed to a branch, not uploaded as an artifact. Workflow artifacts are not repo blobs.
   - What's unclear: The CONTEXT.md decision says "embed a direct htmlpreview.github.io link" for public repos, but artifacts are not accessible via htmlpreview.
   - Recommendation: Implement a per-file table pointing to the Actions run URL for both public and private repos. For public repos, add a note that no login is required to download the artifact. Planner should include a task note surfacing this clarification — the per-file table with an Actions run link satisfies "no ZIP download required" as a user experience improvement over the original single bulk link, without requiring htmlpreview.

2. **GITHUB_TOKEN metadata:read scope for repos.get()**
   - What we know: `GITHUB_TOKEN` has `metadata: read` by default and can call `GET /repos/{owner}/{repo}`.
   - What's unclear: Whether forked PR workflows (where head repo != base repo) have correct scope.
   - Recommendation: The workflow already sets `contents: read; pull-requests: write` — `metadata:read` is implicit. Add a defensive fallback (`is_private_repo` returns `True` on error). Confidence: HIGH.

3. **acd install URL in ci-templates/ copy**
   - What we know: The live workflow installs `git+https://github.com/Laxmi884/alteryx_diff.git` — a specific org.
   - What's unclear: Whether acd is or will be on PyPI under a stable package name.
   - Recommendation: ci-templates/ copy should use the same install URL as the live example but wrapped in a comment block instructing users to replace it if they have a private fork. Do not change until acd is published to PyPI.

## Validation Architecture

`workflow.nyquist_validation` is not set to false in `.planning/config.json` — validation section is included.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing, from pyproject.toml) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd /Users/laxmikantmukkawar/Documents/Projects/alteryx_diff && python -m pytest tests/ -x -q 2>/dev/null` |
| Full suite command | `cd /Users/laxmikantmukkawar/Documents/Projects/alteryx_diff && python -m pytest tests/ -q` |

**Note:** Phase 18 involves YAML and Markdown files + one Python helper script. The Python script
(`generate_diff_comment.py`) has no existing test file. The GitHub Actions YAML is not testable via pytest.
CI-01 and CI-02 logic changes in the Python helper can have unit tests written for the new functions
(`is_private_repo`, updated `build_comment`). CI-03 and CI-04 are file changes with no automated test path.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CI-01 | `build_no_files_comment` includes marker; `build_comment` includes marker | unit | `pytest tests/test_ci_github_comment.py -x` | Wave 0 |
| CI-01 | Find-or-update JS logic | manual-only | N/A — GitHub Actions JS not unit-testable outside GH | N/A |
| CI-02 | `is_private_repo()` returns bool from mocked HTTP response | unit | `pytest tests/test_ci_github_comment.py -x` | Wave 0 |
| CI-02 | Per-file table rendered correctly in comment body | unit | `pytest tests/test_ci_github_comment.py -x` | Wave 0 |
| CI-03 | `.gitlab-ci.yml` does not contain `test-job` string | smoke | `grep -c test-job ci-templates/.gitlab-ci.yml` returns 0 | manual grep |
| CI-04 | README.md exists at `ci-templates/README.md` and contains key headings | smoke | manual review | manual |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_ci_github_comment.py -x -q` (if created in Wave 0)
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ci_github_comment.py` — covers CI-01 (marker in comment bodies) and CI-02 (is_private_repo, per-file table)
- [ ] No framework gaps — pytest already configured

*(CI-03 and CI-04 are file edits verifiable by inspection; no automated test infrastructure needed.)*

## Sources

### Primary (HIGH confidence)
- GitHub Actions `actions/github-script@v7` — official repo: https://github.com/actions/github-script
- GitHub REST API `issues.listComments`, `issues.updateComment`, `issues.createComment` — documented in Octokit.js and GitHub REST docs
- GitHub REST API `repos.get` → `private` boolean field — https://docs.github.com/en/rest/repos/repos
- Existing source files read directly: `/alteryx/.github/workflows/pr-diff-report.yml`, `/alteryx/.github/scripts/generate_diff_comment.py`, `/alteryx/.gitlab-ci.yml`, `/alteryx/.gitlab/scripts/generate_diff_comment.py`
- `actions/upload-artifact@v4` — https://github.com/actions/upload-artifact

### Secondary (MEDIUM confidence)
- Find-or-update marker pattern: verified via WebSearch + multiple independent sources including `edumserrano/find-create-or-update-comment` marketplace action documentation and community discussions
- htmlpreview.github.io URL format: https://github.com/htmlpreview/htmlpreview.github.com + https://htmlpreview.github.io/
- `per_page: 100` listComments pagination: GitHub REST API pagination docs pattern

### Tertiary (LOW confidence)
- htmlpreview.github.io limitation with artifacts (not repo blobs) — inferred from how the service works (fetches raw.githubusercontent.com URLs); not explicitly documented. Flag for validation during implementation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tools already present in existing workflow; no new dependencies
- Architecture: HIGH — find-or-update marker pattern is well-established; existing code read directly
- Pitfalls: HIGH — pagination pitfall verified; marker ownership pitfall verified from code reading; htmlpreview/artifacts limitation MEDIUM (inferred)

**Research date:** 2026-03-15
**Valid until:** 2026-09-15 (stable — GitHub Actions APIs and GitLab CI syntax are stable; 6-month validity)
