# Phase 18: CI Polish - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Polish and package CI integration templates — GitHub Actions and GitLab CI — so they are production-ready and redistributable. Templates live in `ci-templates/` inside the `alteryx_diff` repo. Users copy the directory into their own Alteryx workflow repos. The `/alteryx/` workflow repo remains a live working example; `ci-templates/` is the canonical distributable source.

Out of scope: new CI platforms, automated publishing/release of templates, changes to the core `acd` CLI.

</domain>

<decisions>
## Implementation Decisions

### Comment Update Logic (CI-01)

- Use an HTML marker tag `<!-- acd-diff-report -->` embedded in every comment body to identify the ACD comment
- Script pattern: list PR comments → find one containing the marker → `updateComment` if found, `createComment` if not
- Always post/update a comment even when no Alteryx files changed — keeps the marker present so future pushes update the same comment rather than creating a new one
- Retain the existing commit SHA + UTC timestamp stamp in the comment header (`🤖 Automated report | Commit: abc1234 | 2026-03-15 14:32 UTC`) so reviewers know the report is current
- GitLab CI: one comment per push is acceptable for now — find-or-update pattern not required for GitLab

### HTML Report Delivery (CI-02)

- No PNG embedding — the interactive HTML report is more valuable; PNG was reconsidered and dropped
- For **public repos**: embed a direct `htmlpreview.github.io` link in the PR comment so reviewers open the report in-browser with one click (no download)
- For **private repos**: provide a prominent one-click ZIP download link per file in the PR comment (current artifact upload approach, improved presentation)
- Python helper script auto-detects public vs private via GitHub API and builds the appropriate link type
- Comment shows a per-file table: filename → download/preview link
- GitLab: existing `expose_as` artifact approach already gives one-click browser open — no changes needed

### GitLab CI Cleanup (CI-03)

- Remove the `test-job` stage and its placeholder `echo` script entirely
- Remove the now-unused `test` stage from the `stages:` list
- Keep the `diff` stage and `alteryx-diff` job as-is (cleaned up)

### ci-templates/ Directory Structure

- `ci-templates/` lives in the `alteryx_diff` repo — canonical distributable location, versioned with the tool
- Full mirrored directory structure so users can copy the whole thing without surgery:
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
- `/alteryx/` workflow repo keeps its own CI config as a live working example — both exist independently

### README Scope (CI-04)

- Primary audience: non-technical Alteryx analysts (no assumed GitHub/GitLab CI expertise)
- Step-by-step with exact copy-paste instructions, no assumed prior knowledge
- **GitHub section covers:**
  - Prerequisites checklist (GitHub repo, no Python install needed, acd auto-installed)
  - Public vs private repo path (htmlpreview direct link vs ZIP download)
  - Required permissions and secrets (GITHUB_TOKEN is automatic; when and how to create GH_PAT for private repos)
  - Troubleshooting: no comment posted, ZIP empty, workflow not triggering
- **GitLab section covers (equal depth):**
  - GITLAB_TOKEN setup — where to create a Project Access Token, where to add it in CI/CD Variables
  - The `expose_as` artifact feature — how reviewers click "View exposed artifact" directly in the MR
  - Equivalent troubleshooting for GitLab

### Claude's Discretion

- Exact markdown formatting and section ordering in README
- Whether to add a "Quick Start" summary at the top of README or jump straight into steps
- Specific wording of copy-paste instructions
- Whether to split GitHub and GitLab README into separate files or keep as one README with sections

</decisions>

<specifics>
## Specific Ideas

- The current `pr-diff-report.yml` and both `generate_diff_comment.py` scripts are the starting point — polish them, don't rewrite from scratch
- The comment table format for download links (from the discussion preview): filename column + download/preview link column
- Comment marker: `<!-- acd-diff-report -->` — embed as the first line of every generated comment body

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets

- `/alteryx/.github/workflows/pr-diff-report.yml`: existing GitHub Actions workflow — step 5 (Post comment) needs the find-or-update rewrite using `actions/github-script@v7`
- `/alteryx/.github/scripts/generate_diff_comment.py`: existing Python helper — needs `actions_run_url()` replaced with public/private detection + appropriate link builder
- `/alteryx/.gitlab-ci.yml`: existing GitLab CI — only change is removing `test-job` and `test` stage
- `/alteryx/.gitlab/scripts/generate_diff_comment.py`: existing GitLab Python helper — already has `artifact_url()` for direct browser links; no changes needed

### Established Patterns

- GitHub Actions workflow already uses `actions/github-script@v7` for comment posting — same action handles update
- Python helper already detects `GITHUB_RUN_ID` + `GITHUB_REPOSITORY` for artifact URL — extend with visibility check
- GitLab already uses `expose_as: "Alteryx Diff Report"` for one-click artifact viewing — this is already correct

### Integration Points

- `ci-templates/` is a new top-level directory in `alteryx_diff` — no existing code connection, pure file addition
- The `/alteryx/` repo's CI files will be updated in place (same paths), then copied/adapted into `ci-templates/`

</code_context>

<deferred>
## Deferred Ideas

- GitLab find-or-update comment pattern — future polish pass
- Automated release process that publishes `ci-templates/` as a versioned download — future phase
- GitHub Pages deployment option for private repos — future enhancement if ZIP download UX proves insufficient

</deferred>

---

*Phase: 18-ci-polish*
*Context gathered: 2026-03-15*
