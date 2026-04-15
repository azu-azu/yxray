# CI Templates: Automated Alteryx Workflow Diff Reports

Whenever a pull request (GitHub) or merge request (GitLab) modifies a `.yxmd`
or `.yxwz` file, these CI templates automatically post a diff report as a
comment. The report shows which tools were added, removed, or modified — so
reviewers can see exactly what changed in the workflow without opening Alteryx.

For background on the underlying tool, see the
[Alteryx Canvas Diff (acd)](https://github.com/Laxmi884/alteryx_git_companion) repo.

---

## GitHub Actions Setup

### Prerequisites

- A GitHub repository containing your Alteryx workflow files (`.yxmd`,
  `.yxwz`)
- No Python installation required — GitHub Actions handles this automatically

### Step 1: Copy the template files

Copy the following two files from `ci-templates/` into your repository,
maintaining the exact directory structure:

| Source (in this repo) | Destination (in your repo) |
|---|---|
| `ci-templates/.github/workflows/pr-diff-report.yml` | `.github/workflows/pr-diff-report.yml` |
| `ci-templates/.github/scripts/generate_diff_comment.py` | `.github/scripts/generate_diff_comment.py` |

Create the `.github/workflows/` and `.github/scripts/` directories in your
repo if they do not already exist.

### Step 2: Public vs Private repo — what changes

**Public repository:** No extra setup needed. The built-in `GITHUB_TOKEN`
covers everything, and the HTML diff report links are accessible without login.

**Private repository:** `GITHUB_TOKEN` still covers posting comments. However,
installing `acd` from the GitHub source requires a personal access token for
the `alteryx_git_companion` repo. To set this up:

1. Create a fine-grained Personal Access Token (PAT):
   - Go to GitHub → Settings → Developer settings → Personal access tokens →
     Fine-grained tokens
   - Click **Generate new token**
   - Set **Repository access** to `Laxmi884/alteryx_git_companion` only
   - Under **Permissions**, set **Contents** to `Read-only`
   - Click **Generate token** and copy the value immediately

2. Add the PAT as a secret in your repo:
   - Go to your repository → Settings → Secrets and variables → Actions
   - Click **New repository secret**
   - Name: `GH_PAT`, Value: (paste the token)
   - Click **Add secret**

3. Update the install line in `.github/workflows/pr-diff-report.yml`:

   Find this line:
   ```
   pip install --quiet git+https://github.com/Laxmi884/alteryx_git_companion.git
   ```

   Replace it with:
   ```
   pip install --quiet git+https://${{ secrets.GH_PAT }}@github.com/Laxmi884/alteryx_git_companion.git
   ```

### Step 3: GITHUB_TOKEN permissions

`GITHUB_TOKEN` is provided automatically by GitHub Actions — you do not need
to create it or add it anywhere. The workflow already includes the
`pull-requests: write` permission declaration so that it can post comments on
PRs. No manual configuration is required.

### Step 4: Commit and push

Commit both files and push to any branch:

```
git add .github/workflows/pr-diff-report.yml .github/scripts/generate_diff_comment.py
git commit -m "Add Alteryx diff report CI workflow"
git push
```

The workflow triggers automatically on any PR that touches a `.yxmd` or
`.yxwz` file. Open a PR that modifies an Alteryx workflow to test it.

### What you'll see

A comment appears on the PR from the GitHub Actions bot. The comment shows:

- A summary badge: how many tools were added, removed, or modified across all
  changed workflow files
- A per-file table with a link to the Actions run where you can download the
  interactive HTML diff reports
- A collapsible section per file with tool-level details (tool IDs, types, and
  field-by-field changes)

On future pushes to the same PR, the bot **updates the same comment** instead
of posting a new one — so the PR stays clean.

### Troubleshooting (GitHub)

**No comment was posted:**
- Open the **Actions** tab in your repository and find the workflow run.
- Check the logs for the "Post or update diff report PR comment" step.
- Verify that `pull-requests: write` is present in the `permissions:` block in
  the workflow YAML.

**The workflow didn't trigger:**
- Confirm the PR touches at least one `.yxmd` or `.yxwz` file.
- Check the `paths:` filter in the workflow YAML — it must match your file
  extension.

**pip install failed:**
- For private repos, confirm `GH_PAT` is set in your repo Settings → Secrets
  and variables → Actions, and that the token has `Contents: Read` access to
  the `alteryx_git_companion` repository.

---

## GitLab CI Setup

### Prerequisites

- A GitLab project containing your Alteryx workflow files (`.yxmd`, `.yxwz`)
- A GitLab Project Access Token with `api` scope (for posting MR comments)

### Step 1: Create a Project Access Token (GITLAB_TOKEN)

1. Go to your GitLab project → **Settings** → **Access Tokens**
2. Click **Add new token**
3. Fill in the form:
   - **Name:** `acd-ci`
   - **Expiration date:** Set a date (required)
   - **Role:** Developer
   - **Scopes:** Check `api`
4. Click **Create project access token**
5. Copy the token value immediately — GitLab only shows it once

Now add the token to your CI/CD variables:

1. Go to your project → **Settings** → **CI/CD** → **Variables**
2. Click **Add variable**
3. Fill in:
   - **Key:** `GITLAB_TOKEN`
   - **Value:** (paste the token you just copied)
   - **Flags:** Check **Mask variable** (hides the value in job logs)
4. Click **Add variable**

### Step 2: Copy the template files

Copy the following files from `ci-templates/` into your repository:

| Source (in this repo) | Destination (in your repo) |
|---|---|
| `ci-templates/.gitlab-ci.yml` | `.gitlab-ci.yml` (repo root) |
| `ci-templates/.gitlab/scripts/generate_diff_comment.py` | `.gitlab/scripts/generate_diff_comment.py` |

**If your repo already has a `.gitlab-ci.yml`:** Do not overwrite it. Instead,
merge the Alteryx diff job into your existing file:

1. Add `diff` to your `stages:` list
2. Copy the entire `alteryx-diff:` job block from the template into your
   `.gitlab-ci.yml`

### Step 3: How the artifact link works

The template uses GitLab's `expose_as: "Alteryx Diff Report"` feature. When
the pipeline runs, GitLab automatically adds a **"View exposed artifact"**
button to the MR page. Clicking this button opens the HTML diff report
**directly in the browser** — no download, no ZIP, no login required even for
private projects.

This is a built-in GitLab feature and requires no extra configuration beyond
what is already in the template.

### Step 4: Commit and push

Commit both files and push to any branch:

```
git add .gitlab-ci.yml .gitlab/scripts/generate_diff_comment.py
git commit -m "Add Alteryx diff report CI pipeline"
git push
```

Create a merge request that touches a `.yxmd` file to trigger the pipeline and
verify the setup.

### What you'll see

After the pipeline runs:

- A comment is posted on the MR showing the diff summary and tool-level
  changes
- A **"View exposed artifact"** button appears in the MR (added automatically
  by GitLab) — click it to open the interactive HTML diff report in the browser

### Troubleshooting (GitLab)

**No comment was posted:**
- Confirm that `GITLAB_TOKEN` is set in your project's CI/CD Variables
  (Settings → CI/CD → Variables) and that it has `api` scope.
- Check the pipeline job logs for errors in the curl command step.

**The pipeline didn't trigger:**
- Confirm the MR touches at least one `.yxmd` or `.yxwz` file.
- The pipeline rule checks `$CI_PIPELINE_SOURCE == "merge_request_event"` —
  ensure you are creating a proper merge request, not just pushing to a branch.

**"View exposed artifact" gives 404:**
- Verify that `paths: - "diff_reports/"` is present in the `artifacts:` block
  of your `.gitlab-ci.yml`.
- Verify that the Python script ran without errors and wrote files to the
  `diff_reports/` directory (check the job log output).
