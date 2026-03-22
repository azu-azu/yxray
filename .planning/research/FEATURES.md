# Feature Research

**Domain:** Desktop companion app — Git-based version control for non-technical Alteryx analysts (local web server, Python FastAPI + React, bundled .exe)
**Researched:** 2026-03-13
**Confidence:** MEDIUM-HIGH (primary sources: official tool docs, GitHub Desktop docs, Tower feature pages, community analysis; research is current but some Alteryx-specific UX data inferred from analogous tools)

---

## Research Basis

Sources consulted:
- GitHub Desktop official docs (commit flow, branch management, auth)
- Tower Git Client feature overview (official)
- GitKraken Launchpad and Workspaces (official docs)
- Sourcetree UX patterns (community + official)
- Figma version history UX analysis (official blog + community)
- Zeplin design version control (official docs)
- Abstract branching models for design tools (Medium)
- DVC (Data Version Control) non-developer UI approaches
- Google Cloud Pipeline versioning UX
- Windows system tray notification patterns (Microsoft Learn)
- PyInstaller + FastAPI desktop app patterns (community)
- Git Credential Manager browser-based auth (GitHub blog)
- UXPin Git for designers analysis
- Quora thread: "Why haven't version control systems targeted non-technical users?"
- Alteryx governance and workflow management patterns (USEReady, community)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features Alteryx analysts expect if the app is positioned as "Git for your workflows." Missing any of these = app feels broken or incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Folder/repo registration ("Add a project folder") | Users expect to point the app at their workflows folder and have it "just work." No understanding of git init required. | LOW | GitHub Desktop and Tower both do this. App must auto-detect if folder is already a git repo or offer to initialize one. |
| File change detection with visual indicator | Users need to see "something changed" without refreshing or polling manually. Dropbox/Google Drive conditioning creates this expectation. | MEDIUM | Use Python `watchdog` (cross-platform `inotify`/`ReadDirectoryChangesW`). Show badge/count on changed files. |
| One-click "Save a version" (commit) flow | The mental model is "save a snapshot." Users should not need to know what staging is. | LOW | GitHub Desktop's checkbox-select-then-commit is the gold standard. Pre-fill commit message with timestamp + filename if user leaves it blank. |
| Descriptive commit message prompt | Every git GUI requires a message. Non-technical users need a prompt/example, not a blank box. | LOW | GitHub Desktop uses "Copilot generate" as an optional assist. For ACD companion, a placeholder like "What changed? (e.g. Fixed customer filter logic)" is sufficient. |
| View change history / timeline | Users expect to see a list of past versions, like Google Docs version history. | LOW | Show commits as a timeline: date, message, author. Tower and GitHub Desktop both do this well. |
| "Push to backup" / sync to remote | Users understand "save to the cloud." The word "push" is acceptable if explained once during onboarding. | MEDIUM | GitHub Desktop uses "Publish branch" and "Push origin." GitKraken uses "Push." For ACD: "Back Up Now" or "Sync" is more accessible. |
| Visual diff of any past version vs current | Users expect to click any history entry and see what changed — powered by the existing ACD diff engine. | MEDIUM | This is the key integration point with v1.0. The diff report (HTML) is embedded in an iframe or opened in a browser tab. |
| Multi-folder/multi-project management | Analytics teams often maintain multiple project folders (by client, department, or use case). | LOW | GitKraken Workspaces and GitHub Desktop's repository switcher are the pattern. Show a left-panel project list. |
| Windows-only .exe installer | Target users are Windows-based Alteryx users. No Python install required. | HIGH | PyInstaller + FastAPI is a validated pattern. Port conflict on startup is the main known risk (default port 7433). |
| Always-visible app status | Users need ambient awareness of "is the app running and watching my files?" | LOW | System tray icon with tooltip state. This is the Dropbox/OneDrive interaction pattern non-technical users already understand. |

### Differentiators (Competitive Advantage)

Features that make this tool genuinely better than GitHub Desktop or Sourcetree for Alteryx analysts specifically.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Embedded diff viewer using existing ACD report | No other Git GUI can show what changed *inside* an Alteryx workflow — only raw XML diffs. This is the only tool that understands .yxmd semantically. | MEDIUM | iframe/webview embedding the existing HTML report. The diff engine is already built; this is the UX integration layer. HIGH confidence this is genuinely differentiated — no competitor does Alteryx-aware diffs. |
| Workflow-aware language throughout ("workflow" not "file", "version" not "commit") | Lowers cognitive friction. Alteryx analysts think in "workflows" and "versions," not "files" and "commits." | LOW | Vocabulary substitution: commit → "Save Version", push → "Back Up", branch → "Workspace Copy", merge → "Combine Changes". Research confirms terminology abstraction is a key non-technical UX strategy (Tower's philosophy, GitKraken's design). |
| Auto-suggested version notes from detected changes | On open of "Save Version" panel, pre-populate the message with the ACD diff summary: "Modified 2 tools, added 1 connection." User edits to add context, or accepts as-is. | HIGH | Requires running a lightweight diff on save. This is the highest-complexity differentiator but also the most likely to generate delight. Similar to Zeplin's "which artboards changed" auto-detection. |
| CI integration: auto-post diff report on GitHub PR / GitLab MR | The v1.0 GitHub Actions integration means that when users push through the app, CI automatically posts a visual diff to the PR. This is invisible to the user but a major governance value. | MEDIUM | CI YAML is already written (v1.0). The companion app needs to: (a) surface that CI is configured, (b) show when a PR has been posted. Link to PR from the app's history view. |
| "Safe" branch creation for experimenting ("Try something out") | Non-technical users fear making mistakes. A "Create a copy to experiment" button (creates a branch) with clear "go back to main" UX makes experimentation feel safe. | MEDIUM | Tower's philosophy: make it hard to lose work. Research confirms undo + safety net is what makes non-technical users trust a git tool. Name the branch based on timestamp + user intent (e.g. `experiment/2026-03-13-test-new-filter`). |
| Undo last "Save Version" with one click | The most powerful onboarding statement: "You can always undo." Tower's single-click undo via Cmd+Z is cited as its philosophy. For non-technical users, this removes fear of the tool. | LOW | `git reset --soft HEAD~1` under the hood. Surface as "Undo Last Save" in the history view. Clear confirmation dialog with preview of what will be undone. |
| Conflict-free push with "someone else changed this" explanation | When push fails due to remote changes, display a clear explanation: "Someone else saved a newer version. Here's what they changed." Offer "View their changes" and "Merge" options. | HIGH | Pull conflict resolution is the #1 place non-technical users abandon git GUIs. This is a known pitfall (see PITFALLS.md). Reduce to a clear 2-option dialog rather than a merge editor. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem natural to request but create more problems than value for this user population.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full Git command passthrough / terminal | Power users want full Git access from within the app | The target users are non-technical. Exposing a terminal undermines the "simple as Dropbox" UX promise and creates support burden when users break things. | Add a "Open in GitHub Desktop" escape hatch for power users who need raw Git access. |
| Automatic commits on every file save | Seems like "auto-backup" — Dropbox mental model | Auto-commits with no message produce useless history ("Auto-save 14:32:01", "Auto-save 14:32:45"). Non-technical users end up with hundreds of undifferentiated history entries and can't find "the version before I broke it." | File watcher detects changes and shows a "You have unsaved changes" badge. User triggers commit intentionally with a message. |
| Three-way merge editor | Users who encounter conflicts want to resolve them | A merge editor for .yxmd XML is meaningless to an Alteryx analyst. They can't read raw XML diffs. | Surface conflicts as: "Both you and [name] changed this file. Here's what each version looks like." Show two ACD diff reports (vs. common ancestor). Let user choose which version to keep. This is conflict resolution without a text editor. |
| Branch visualization graph (commit tree) | GitHub Desktop and GitKraken both show it; users expect it | The commit DAG is incomprehensible to non-developers. It adds visual complexity without value for users who only need "what's my current version" and "what were past versions." | Show a simple flat timeline per workflow file. Branch state shown as a label, not a graph. |
| In-app text/XML editor | Some users want to edit workflow files directly | .yxmd files are binary XML designed to be edited only in Alteryx Designer. Editing them manually risks corruption. | Block direct editing. Surface a "Open in Alteryx Designer" button from any file in the app. |
| Scheduled automatic push | "Back up every night" seems like good governance | Scheduled pushes without user-authored messages produce commit history that fails audit requirements. In regulated industries (banks, insurance), commits must be attributable with intentional messages per ALCOA+ standard. | Offer a daily reminder notification: "You have unsaved changes from today. Save a version before closing?" |
| Full GitHub/GitLab web integration (issues, PRs, review) | GitKraken Launchpad does this; seems natural | Alteryx analysts don't use GitHub for issue tracking or code review workflows. Adding PR review UX adds complexity with near-zero value for this persona. | Show one thing from CI: "A diff report was posted on your PR" with a link. Nothing more. |
| Git LFS for large workflow files | .yxmd files can be large; LFS seems right | LFS requires server-side LFS support and adds configuration complexity. Most Git hosts support it, but setup friction is high. .yxmd files are typically under 1MB for even large workflows. | Only recommend LFS if file sizes consistently exceed 50MB. Document the decision. Default to standard git. |

---

## Feature Dependencies

```
[App Launch / Port Detection]
    └──required by──> [Local Web Server (FastAPI + React)]
                          └──required by──> [All UI features]

[Folder Registration]
    └──required by──> [File Watcher]
                          └──required by──> [Change Detection Badge]
                                                └──required by──> [Save Version Flow]

[Save Version Flow]
    ├──required by──> [History Timeline]
    └──required by──> [Undo Last Save]

[ACD Diff Engine (v1.0)]
    └──required by──> [Embedded Diff Viewer]
                          └──enhanced by──> [Auto-suggested Version Notes]

[Remote Configuration (GitHub/GitLab)]
    └──required by──> [Push / Sync]
                          └──required by──> [CI Integration Link]

[Branch Create ("Experiment")]
    └──required by──> [Merge / Combine Changes]
                          ──conflicts with──> [Conflict-free Guarantee]
                          (conflicts are unavoidable when two people change the same file)

[System Tray Icon]
    └──enhanced by──> [File Watcher]
    └──enhanced by──> [CI Integration Status]

[Onboarding Flow]
    └──required before──> [Folder Registration]
    └──required before──> [Remote Authentication]
```

### Dependency Notes

- **File Watcher requires Folder Registration:** Watchdog cannot watch a path that isn't registered. Registration also runs `git init` if needed — these are the same step.
- **Embedded Diff Viewer requires ACD Diff Engine:** The companion app is a UI layer over the existing v1.0 engine. The engine must be bundled in the .exe via PyInstaller.
- **Auto-suggested Version Notes requires Diff Engine at commit time:** Diffs run synchronously when the "Save Version" panel opens. Must be fast enough to not feel blocking (<1 second for typical .yxmd files).
- **Remote Authentication required before Push:** GitHub OAuth browser flow or GitLab PAT entry must complete before any push is attempted. Auth state must persist across app restarts (OS credential store, not plaintext file).
- **Branch Create and Merge are linked:** Creating an experimental branch is only useful if there's a path back. Both features must ship together.

---

## MVP Definition

### Launch With (v1.1 — companion app MVP)

Minimum viable product — what validates that non-technical users can do intentional version control with no Git knowledge.

- [ ] Single-folder repo management (register one folder, watch for .yxmd changes) — foundation of everything
- [ ] Auto `git init` on first registration if folder is not already a repo — removes the "what is git init" barrier
- [ ] File change detection with badge/count indicator — real-time awareness that mimics Dropbox/OneDrive
- [ ] Save Version flow: select changed files, write message, commit — the core non-technical Git action
- [ ] History timeline with date, message, author per commit — users need to see what they've saved
- [ ] Embedded diff viewer: click any history entry, see ACD diff report in-frame — the key integration with v1.0; this is the "wow" feature
- [ ] Undo Last Save (one-click) — the safety net that makes users trust the tool
- [ ] System tray icon with app status (watching / not running) — ambient presence, Dropbox-style
- [ ] First-run onboarding: what is this app, how to add a project folder — non-technical users need guided entry
- [ ] .exe bundled installer: launch, open browser at localhost:7433 — Windows-only, no Python install required

### Add After Validation (v1.1.x)

Add once core commit/history/diff loop is validated with at least one real user team.

- [ ] Multi-folder project management — trigger: users report managing multiple project folders
- [ ] Remote auth (GitHub OAuth + GitLab PAT) and Push — trigger: users want "backup to cloud" or CI integration
- [ ] CI integration link (show when a diff report was posted on a PR) — trigger: remote push is live
- [ ] Commit message auto-suggestion from diff summary — trigger: user feedback that blank message field is intimidating
- [ ] "Create experiment copy" (branch creation) — trigger: users ask "how do I try something without breaking the main version"

### Future Consideration (v2+)

Defer until product-market fit for the companion app is established.

- [ ] Conflict resolution UX ("someone else changed this") — defer until multi-user push conflicts are observed in real usage
- [ ] Team/collaboration features (see others' commits, blame) — defer; current target is single-analyst workflow
- [ ] GitHub/GitLab web UI deep integration (PR review, issue tracking) — defer; out of scope for Alteryx analyst persona
- [ ] Mobile or web-hosted version — defer; .exe is the deployment model; web requires auth and hosting infrastructure
- [ ] Scheduled version reminders (notification: "You have changes today") — defer; validate core commit flow first

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Folder registration + git init | HIGH | LOW | P1 |
| File watcher (.yxmd change detection) | HIGH | LOW | P1 |
| Save Version flow (commit) | HIGH | LOW | P1 |
| History timeline | HIGH | LOW | P1 |
| Embedded ACD diff viewer | HIGH | MEDIUM | P1 |
| Undo Last Save | HIGH | LOW | P1 |
| System tray icon + app status | HIGH | LOW | P1 |
| First-run onboarding | HIGH | LOW | P1 |
| .exe bundled installer | HIGH | HIGH | P1 |
| Multi-folder management | MEDIUM | LOW | P2 |
| Remote auth + push/sync | HIGH | MEDIUM | P2 |
| CI integration link | MEDIUM | LOW | P2 |
| Commit message auto-suggestion | MEDIUM | HIGH | P2 |
| Branch create ("experiment copy") | MEDIUM | MEDIUM | P2 |
| Conflict resolution UX | HIGH (when needed) | HIGH | P3 |
| Scheduled version reminders | MEDIUM | LOW | P3 |
| Team collaboration / blame | LOW (solo analysts) | HIGH | Defer |
| Full GitHub/GitLab PR review | LOW | HIGH | Defer |

**Priority key:**
- P1: Must have for v1.1 launch
- P2: Should have, add in v1.1.x after validation
- P3: Nice to have, plan for v1.2+
- Defer: Explicitly out of scope; not worth the complexity for target persona

---

## Competitor Feature Analysis

What the best tools in the non-technical Git GUI space do, and what ACD companion app should learn from each.

| Feature Area | GitHub Desktop | Tower | GitKraken | Sourcetree | ACD Companion (our approach) |
|---|---|---|---|---|---|
| Commit flow | Checkbox file selection + message field + "Commit to [branch]" button. Clean, linear. Optional Copilot message generation. | Granular staging (file, hunk, line level). Commit templates. | Drag-and-drop staging. Large commit button. | Standard staging area; more technical feel. | Simplified: auto-select all .yxmd changes. Single message field with placeholder text. |
| Terminology | Uses "push", "pull", "branch" — standard Git terms | Uses "push", "pull", "branch" — does not abstract | Uses "push", "pull" — does not abstract | Uses Git terms throughout | Abstracts: "Save Version", "Back Up", "Experiment Copy". One-time explanation in onboarding. |
| Undo/safety | Discarded changes go to Trash folder (recoverable). No single-click undo for commits. | Cmd+Z undoes virtually all Git operations including deletes, rebase, merge. Safety philosophy is explicit. | Undo available for most operations. | No prominent undo. | Undo Last Save (one-click). Also: "discard changes" moves .yxmd to a .acd-backup folder rather than deleting. |
| Branch management | "Current Branch" dropdown, clear branch list, protected branch warnings. | Full branch management, drag-and-drop merge/cherry-pick. Branches are prominent. | Visual branch tree (can be overwhelming for beginners). | Full branch management with visual graph. | Hide branch complexity. One "Create Experiment Copy" button. Show current branch/workspace as a label not a dropdown. |
| Diff viewer | Line-level text diff with syntax highlighting. No domain-specific understanding. | Integrated side-by-side diff with image diff support. Still text-based. | Inline diff with hunk selection. Text-based. | Text diff. | **Embedded ACD HTML report** — semantic diff with interactive graph. This is the unique value. No competitor can show what changed inside a .yxmd file meaningfully. |
| Auth flow | Browser-based OAuth. "Sign in with GitHub" launches browser, redirects back. Clear success state. | Account setup via preferences. Supports OAuth and PAT. | OAuth via browser. Supports GitHub, GitLab, Bitbucket. | PAT-based; setup involves GitHub.com settings; known friction point for beginners. | GitHub: browser OAuth (same as GitHub Desktop). GitLab: PAT with inline instructions and link to GitLab settings. Passwords never stored in app (OS credential store only). |
| Onboarding | "Let's get started" dialog: clone, create new, or add existing repo. Three clear options. | 150-page guide + in-app checklist. Beginner video series. | Interactive tutorial for first-time users. | Tutorial available but not forced. | Single-screen onboarding: "Point me at your Alteryx workflows folder." One choice, not three. |
| Multi-repo management | Repository list in left panel + switcher. Clean. | Repository list in sidebar. | Workspaces: group repos by team/project. | Sidebar with bookmarks. | Project list in left panel. Each project = one workflows folder. |
| Background awareness | No background process; app must be open. | No background process. | No background process. | No background process. | **System tray icon** — runs as background service. File watcher active when app is "watching". This is a key differentiator vs all listed GUI tools. |

### Key Lessons from Competitor Analysis

**From GitHub Desktop:** The three-option "get started" screen (clone / create / add existing) is too much for non-technical users. ACD companion app should offer one path: "Add a folder."

**From Tower:** The Cmd+Z safety net philosophy is essential for non-technical adoption. Users must feel they cannot lose work. Undo Last Save must be in the MVP.

**From GitKraken:** The Launchpad (unified PR/issue view) is powerful for developers but wrong for Alteryx analysts. Do not import that pattern. Instead, the equivalent for ACD is the history timeline per workflow file — simple and focused.

**From Sourcetree:** PAT authentication is the biggest UX failure point for non-technical users. Multiple community threads document confusion with PATs and OAuth. GitHub Desktop's browser-OAuth flow is superior for this audience.

**From Figma:** Non-technical users adopted version history only through named versions and visual comparisons. Auto-save with unnamed versions creates noise. Named saves (commit messages) with a visual diff are the right model.

**From domain-specific tools (DVC, Google Cloud Pipelines):** Data pipeline versioning is an unsolved non-developer UX problem. Most tools still require CLI knowledge. The companion app has an opportunity to be the first genuinely non-technical version control tool for a data analytics workflow type.

---

## UX Design Patterns to Implement

Specific interaction patterns supported by research that should be incorporated.

### Pattern 1: "You have changes" Badge (File Watcher)
**What:** System tray icon and in-app sidebar show a badge with count of changed .yxmd files since last version save.
**Rationale:** Dropbox and Google Drive conditioned non-technical users to expect ambient change awareness. The badge creates a soft prompt: "you should save a version."
**When to show:** Immediately when a .yxmd file is modified (on file close in Alteryx Designer, watchdog fires).
**Confidence:** HIGH — universal pattern in file sync tools.

### Pattern 2: Guided "Save Version" Panel
**What:** Opening "Save Version" shows a pre-populated list of changed workflows. Each row shows filename, modification time, and a checkbox. A message field has placeholder text: "What changed? (e.g. Fixed top 10 customer filter)". A large "Save Version" button completes the commit.
**Rationale:** GitHub Desktop's commit panel is the closest model. Remove staging area jargon entirely. The message placeholder is actionable — it tells users what kind of message is useful.
**Confidence:** HIGH — based on GitHub Desktop UX docs and general Git GUI best practices.

### Pattern 3: History as Timeline (Not Graph)
**What:** For each registered project, show a flat vertical list of version saves: date/time, message, author (from git config). Clicking any entry opens the ACD diff report comparing that version to the previous one.
**Rationale:** The commit DAG (branch visualization) is incomprehensible to non-developers. GitKraken and Sourcetree both use it; neither is appropriate for Alteryx analysts. A flat timeline matches Google Docs version history — a familiar mental model for this audience.
**Confidence:** HIGH — research on non-technical user behavior with git GUIs consistently identifies the DAG as a barrier.

### Pattern 4: Vocabulary Layer
**What:** The app uses domain vocabulary throughout. Git terms are used internally but never surfaced in UI copy.

| Git Term | App Language |
|----------|-------------|
| commit | Save Version |
| push | Back Up / Sync |
| pull | Get Latest |
| branch | Experiment Copy / Workspace |
| merge | Combine Changes |
| repository | Project |
| staging area | (hidden entirely) |
| remote | Backup location |
| HEAD | Current version |
| diff | What changed |

**Rationale:** Tower, GitHub Desktop, and Sourcetree all use native Git terminology. Research on non-technical user adoption consistently shows terminology is the first barrier. The replacement vocabulary is drawn from how Alteryx analysts already talk about their work.
**Confidence:** MEDIUM — based on design tool research (Figma, Abstract) and general Git accessibility writing. No direct Alteryx user research available.

### Pattern 5: Browser Auto-Open on Launch
**What:** When the .exe launches, it starts the FastAPI server on port 7433 and automatically opens `http://localhost:7433` in the default browser. If the port is already in use, it tries 7434, 7435, up to 7443. Shows a tray notification: "ACD Companion is running."
**Rationale:** PyInstaller + FastAPI apps require browser-open behavior because users cannot be expected to know what a localhost URL is or why they need to type it. This is the standard pattern for local web app tools (Jupyter, Ollama desktop, etc).
**Confidence:** HIGH — validated pattern in PyInstaller + FastAPI community.

### Pattern 6: OAuth Browser Auth for GitHub
**What:** "Back Up to GitHub" triggers a browser-based OAuth flow (opens github.com/login/oauth/authorize in default browser). On success, GitHub redirects to a localhost callback URL that the FastAPI server handles. App shows "Connected as [username]" and stores the token in the OS credential store (Windows Credential Manager via `keyring`).
**Rationale:** GitHub Desktop moved from in-app credentials to browser OAuth precisely because non-technical users cannot manage PATs. The browser-based flow leverages existing GitHub sessions. Sourcetree's PAT-based flow is the worst-practice example to avoid.
**Confidence:** HIGH — GitHub Desktop docs explicitly confirm this evolution. GitHub blog post on Credential Manager confirms browser OAuth as the recommended approach.

### Pattern 7: Undo Last Save with Preview
**What:** In the history timeline, the most recent save shows an "Undo" button. Clicking it shows a confirmation: "This will un-save your last version ('[message]' from [time]). Your file changes will still be there — only the version save will be removed." Two buttons: "Cancel" and "Undo Save."
**Rationale:** Tower's Cmd+Z undo is the gold standard. For a browser-based UI, a confirmation dialog with clear explanation is safer than keyboard shortcuts. The key copy is "Your file changes will still be there" — this is the anxiety non-technical users have.
**Confidence:** HIGH — Tower feature page explicit. GitHub Desktop has a weaker version (discard to Trash). The explicit reassurance copy is inferred from UX writing principles.

### Pattern 8: Conflict Triage (not merge editor)
**What:** When push fails due to remote changes, show: "Someone else saved a newer version of [filename.yxmd]. Here's what they changed." Embed an ACD diff report comparing the remote version to the common ancestor. Offer two buttons: "Keep My Version" and "Use Their Version." No three-way merge editor.
**Rationale:** A merge editor for XML is unusable for non-technical Alteryx users. The binary choice (my version or theirs) is the right level of abstraction for v1. True three-way semantic merge is explicitly deferred (listed in PROJECT.md Out of Scope).
**Confidence:** MEDIUM — inferred from research on non-technical user conflict resolution failure patterns. No direct Alteryx user research available.

---

## What the Milestone Scope May Miss

Based on research, potential gaps not explicit in the milestone description:

1. **Port conflict handling is a launch-blocker risk.** Community reports for PyInstaller + FastAPI apps consistently identify port-already-in-use as the silent failure mode. The app must handle port conflicts gracefully (try fallback ports, show clear error if all fail). This is not a nice-to-have; it is a P1 reliability requirement.

2. **Git user identity setup.** Non-technical users will not have `git config --global user.name` and `user.email` set. If the app tries to commit without these, git silently fails or errors. The app must detect missing identity and prompt with a first-run "Who are you?" step (name + email, pre-filled from OS username).

3. **.yxmd files from Alteryx Server vs. Designer.** Workflows saved by Alteryx Server may have different GUID/timestamp patterns than Designer-saved files. The file watcher should only watch for .yxmd changes; it should not attempt to watch `.yxdb`, `.yxzp`, or macros (`.yxmc`) unless explicitly configured. Scope creep here leads to false-positive change detection.

4. **Large initial commit.** If a user registers a folder that already has 50+ .yxmd files and no git history, the first "Save Version" will be a massive commit. The UI should warn: "This is your first save — it will capture all [N] workflows as the starting point." with a "Continue" confirmation.

5. **Antivirus / Windows Defender false positives.** PyInstaller-bundled .exe files are frequently flagged by Windows Defender as PUA (potentially unwanted applications) or have SmartScreen warnings. This is a known deployment friction for non-technical Windows users at financial institutions. Plan for code signing or explicit user-facing instructions to bypass the warning.

6. **Network drive support.** Many Alteryx teams store workflows on network drives (e.g., `\\server\shared\workflows\`). Python's `watchdog` has known issues with network drives (SMB shares). This must be explicitly tested or explicitly documented as unsupported.

---

## Sources

- [GitHub Desktop: Committing and reviewing changes](https://docs.github.com/en/desktop/contributing-and-collaborating-using-github-desktop/making-changes-in-a-branch/committing-and-reviewing-changes-to-your-project) — HIGH confidence (official docs)
- [Tower Git Client: All Features](https://www.git-tower.com/features/all-features) — HIGH confidence (official product page)
- [GitKraken Launchpad Overview](https://help.gitkraken.com/gitkraken-desktop/gitkraken-launchpad/) — HIGH confidence (official help docs)
- [GitKraken Desktop Workspaces](https://help.gitkraken.com/gitkraken-desktop/workspaces/) — HIGH confidence (official help docs)
- [Sourcetree vs GitKraken — Slant comparison](https://www.slant.co/versus/7569/13489/~sourcetree_vs_gitkraken-client) — MEDIUM confidence (community comparison)
- [Git Credential Manager — GitHub blog](https://github.blog/security/application-security/git-credential-manager-authentication-for-everyone/) — HIGH confidence (official blog)
- [GitHub Desktop authentication via browser flow (Issue #9231)](https://github.com/desktop/desktop/issues/9231) — HIGH confidence (official GitHub issue tracker)
- [Figma Version Control: UX Writer perspective](https://www.figma.com/blog/version-control-how-a-ux-writer-weighs-one-word-against-another/) — MEDIUM confidence (official Figma blog)
- [Figma Version Control for UX writing — 7 methods](https://uxcontent.com/7-ways-ux-writers-manage-version-control-in-figma/) — MEDIUM confidence
- [Zeplin Design Version Control](https://blog.zeplin.io/design-delivery/ux-design-version-control/) — MEDIUM confidence
- [Abstract Branching Models for Design Version Control](https://projekt202.medium.com/branching-models-and-best-practices-for-abstract-design-version-control-cd909a01cc13) — MEDIUM confidence
- [PyInstaller + FastAPI .exe patterns](https://aiechoes.substack.com/p/building-production-ready-desktop) — MEDIUM confidence (community)
- [iancleary/pyinstaller-fastapi](https://github.com/iancleary/pyinstaller-fastapi) — MEDIUM confidence (community reference impl)
- [Windows Notification Area guidelines](https://learn.microsoft.com/en-us/windows/win32/shell/notification-area) — HIGH confidence (Microsoft official)
- [Git Watcher — real-time diff desktop app](https://github.com/demian85/git-watcher) — LOW confidence (community tool, reference only)
- [UXPin: Git for Designers](https://www.uxpin.com/studio/blog/git-for-designers/) — MEDIUM confidence

---

*Feature research for: ACD Companion App — Desktop Git UI for non-technical Alteryx analysts*
*Researched: 2026-03-13*
