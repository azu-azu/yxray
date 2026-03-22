# Phase 19: Close Audit Gaps — Branch Verification + APP-04b — Research

**Researched:** 2026-03-22
**Domain:** Documentation-and-verification administrative phase (no new code)
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BRANCH-01 | User can create an experiment copy (branch) with auto-generated name (experiment/YYYY-MM-DD-description) | Implementation confirmed in `app/routers/branch.py` `create_branch` + `_format_branch_name` + `app/services/git_ops.py` `git_create_branch`. All 11 test_branch.py tests GREEN. Human sign-off 2026-03-15 all 8 checks PASSED. |
| BRANCH-02 | User can switch between experiment copies | Implementation confirmed in `app/routers/branch.py` `checkout_branch` + `delete_branch`, `app/services/git_ops.py` `git_checkout` + `git_delete_branch`. Dirty-check guard present. |
| BRANCH-03 | Current workspace shown as a label in the UI (no DAG visualization) | BranchChip.tsx confirmed present in `app/frontend/src/components/`, registered in ChangesPanel.tsx at line 109. AppShell.tsx wires `activeBranch` from Zustand store. |
| APP-04b | User can open the app UI by clicking the system tray icon (opens browser at localhost:PORT) | Implementation confirmed in `app/tray.py` lines 166-167: `on_open` handler with `default=True` on PystrayMenuItem calls `webbrowser.open(f"http://localhost:{self.port}")`. Cannot be automated-tested — requires Windows + pystray + real display. |
</phase_requirements>

---

## Summary

Phase 19 is a pure gap-closure administrative phase. It produces no new application code. The two tasks are: (1) run the gsd-verifier against Phase 17 to produce a formal VERIFICATION.md, and (2) update REQUIREMENTS.md to mark APP-04b as `[x]` with a note about the existing implementation and Windows-only human verification.

The evidence is unambiguous: Phase 17 is fully implemented and human-verified (2026-03-15, all 8 tests PASSED, 141 backend tests GREEN). The gap is purely documentary — gsd-verifier was never run after Phase 17 completed. The v1.1 milestone audit (`v1.1-MILESTONE-AUDIT.md`) explicitly identifies this and names VERIFICATION.md creation as the resolution.

APP-04b was implemented incidentally during Phase 15 as part of the tray menu construction (`on_open` handler with `default=True`). No plan in Phase 15 declared it in its `requirements:` frontmatter, which is why the checkbox was never checked. The implementation is real and correct — it just was never formally acknowledged in REQUIREMENTS.md.

**Primary recommendation:** Phase 19 has one plan: (1) produce Phase 17 VERIFICATION.md by doing a code-level audit of the branch implementation against BRANCH-01/02/03, and (2) update REQUIREMENTS.md APP-04b checkbox to `[x]` with an explanatory note, then update the coverage count from the stale "29" to "31".

---

## Standard Stack

### Core
| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| gsd-verifier format | gsd v1.0 | Produce VERIFICATION.md in standard format | All other phase VERIFICATIONs follow this structure; Phase 18 VERIFICATION.md is the canonical reference |
| pytest | 8.x | Confirm test suite is GREEN before signing off | Already in use throughout all phases; `python -m pytest tests/ -x -q` is the full-suite command |

### No New Dependencies
This phase installs nothing. It is documentation-only.

---

## Architecture Patterns

### Pattern 1: VERIFICATION.md Structure (from Phase 18 reference)
**What:** A structured markdown document with YAML frontmatter + five sections: Goal Achievement (Observable Truths table), Required Artifacts, Key Link Verification, Requirements Coverage, Human Verification Required.
**When to use:** This exact structure, following Phase 18's 18-VERIFICATION.md as the format template.

```
---
phase: 17-branch-management
verified: YYYY-MM-DDT...:00Z
status: passed
score: N/N must-haves verified
re_verification: false
---

# Phase 17: Branch Management Verification Report

**Phase Goal:** ...
**Verified:** ...
**Status:** passed

## Goal Achievement
### Observable Truths
| # | Truth | Status | Evidence |
...

## Required Artifacts
...

## Key Link Verification
...

## Requirements Coverage
...

## Human Verification Required
...
```

### Pattern 2: REQUIREMENTS.md Checkbox Update
**What:** Change `[ ]` to `[x]` on the APP-04b line and add an inline note. The note must be compact — the existing format uses single-line entries.
**When to use:** The exact line to update is line 14 of REQUIREMENTS.md:
```
- [ ] **APP-04b**: User can open the app UI by clicking the system tray icon (opens browser at localhost:PORT)
```
Becomes:
```
- [x] **APP-04b**: User can open the app UI by clicking the system tray icon (opens browser at localhost:PORT) — implemented in app/tray.py (on_open handler, default=True); Windows-only human verification applies
```

### Pattern 3: Coverage Count Update
**What:** REQUIREMENTS.md line 131 currently reads "29 total" — stale since APP-04 was split into APP-04a + APP-04b. The audit confirmed the real count is 31.
**When to use:** Update lines 130-131 of REQUIREMENTS.md:
```markdown
**Coverage:**
- v1.1 requirements: 31 total (APP-04 split into APP-04a + APP-04b)
```
The "29" is the stale value — update to "31". The mapped and unmapped counts follow from that.

### Anti-Patterns to Avoid
- **Writing new code in Phase 19:** This phase touches only `.planning/` files and REQUIREMENTS.md. No `app/` files should be modified.
- **Re-running all phase verifications:** Only Phase 17 needs a VERIFICATION.md. Other phases already have verified VERIFICATIONs.
- **Claiming APP-04b can be automated-tested:** It cannot. pystray requires a Windows display. The note must explicitly call this out and point to the existing Windows-only human verification item in Phase 15 VERIFICATION.md.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Phase 17 VERIFICATION.md format | Custom structure | Follow 18-VERIFICATION.md exactly | Consistency with all 10 existing VERIFICATION files is mandatory |
| Evidence for BRANCH-* | New code analysis | Quote existing code locations directly | All wiring already confirmed by v1.1 audit and integration checker |

---

## Common Pitfalls

### Pitfall 1: Marking BRANCH-01/02/03 as status: partial instead of satisfied
**What goes wrong:** The VERIFICATION.md uses "partial" instead of "satisfied" for the BRANCH requirements.
**Why it happens:** The audit says "partial" for the requirements because VERIFICATION.md was missing — but once VERIFICATION.md exists with code-level evidence, the status becomes "satisfied".
**How to avoid:** In the VERIFICATION.md Requirements Coverage table, mark all three BRANCH requirements as SATISFIED with code-level evidence.

### Pitfall 2: Updating the traceability table phase column for BRANCH-01/02/03
**What goes wrong:** The REQUIREMENTS.md traceability table shows `Phase 19 | Pending` for BRANCH-01/02/03 — these must be updated to `Phase 17 | Complete`.
**Why it happens:** When Phase 19 was added to the roadmap as the verification phase, the traceability table was updated to point to Phase 19. The correct phase of implementation is Phase 17.
**How to avoid:** Update lines 122-124 of REQUIREMENTS.md:
```
| BRANCH-01 | Phase 17 | Complete |
| BRANCH-02 | Phase 17 | Complete |
| BRANCH-03 | Phase 17 | Complete |
```

### Pitfall 3: Stale APP-04b traceability entry
**What goes wrong:** The traceability table shows `APP-04b | Phase 19 | Pending`. After this phase, it should point to Phase 15 (where it was implemented).
**Why it happens:** The roadmap temporarily assigned APP-04b resolution to Phase 19.
**How to avoid:** Update the APP-04b traceability row to `Phase 15 | Complete` since the implementation already exists in `app/tray.py` from Phase 15.

### Pitfall 4: Omitting the "Human Verification Required" section for BRANCH-03
**What goes wrong:** The VERIFICATION.md marks all BRANCH items as fully automated-verifiable.
**Why it happens:** Most branch behaviors are backend-testable, but the UI branch label (BRANCH-03) requires human visual confirmation.
**How to avoid:** The 17-VALIDATION.md already documents two manual-only verifications: "Branch label shown in UI header" and "Switching branches updates UI label". Include these in the VERIFICATION.md's Human Verification Required section, citing the 17-05-SUMMARY.md sign-off as the completion evidence.

---

## Code Examples

### Key implementation locations (pre-verified, no changes needed)

**BRANCH-01: Create experiment copy**
- `app/routers/branch.py` lines 41-46: `_format_branch_name()` produces `experiment/YYYY-MM-DD-slug`
- `app/routers/branch.py` lines 58-66: `create_branch()` endpoint — calls `git_ops.git_create_branch`
- `app/services/git_ops.py` lines 601-611: `git_create_branch()` uses `git checkout -b`
- Frontend: `app/frontend/src/components/BranchChip.tsx` lines 70-82: `handleCreate()` POSTs to `/api/branch/{id}/create`

**BRANCH-02: Switch between copies**
- `app/routers/branch.py` lines 69-79: `checkout_branch()` — pre-checks `git_changed_workflows`, returns error if dirty
- `app/services/git_ops.py` lines 614-627: `git_checkout()` returns `{"success": True/False}`
- `app/routers/branch.py` lines 82-88: `delete_branch()` — guards `main`/`master`
- `app/services/git_ops.py` lines 630-645: `git_delete_branch()` uses `-d`/`-D` flag
- Frontend: `app/frontend/src/components/BranchChip.tsx` lines 54-63: `handleSwitch()` POSTs to `/api/branch/{id}/checkout`
- Frontend: `app/frontend/src/components/BranchChip.tsx` lines 91-107: `handleDelete()` with AlertDialog confirmation

**BRANCH-03: Current workspace label**
- `app/routers/branch.py` lines 49-55: `list_branches()` returns `[{name, is_current}]`
- `app/services/git_ops.py` lines 563-585: `git_list_branches()` parses `%(refname:short)\x1f%(HEAD)`
- Frontend: `app/frontend/src/components/ChangesPanel.tsx` line 17: `import { BranchChip }`, line 109: `<BranchChip`
- Frontend: `app/frontend/src/components/AppShell.tsx` line 19: `activeBranch` from `useProjectStore`, lines 94+: `fetchBranch()`
- `app/server.py` line 64: `app.include_router(branch.router)` — router registered

**APP-04b: Tray icon click opens browser**
- `app/tray.py` lines 166-167: `PystrayMenuItem("Open Alteryx Git Companion", on_open, default=True)`
- `app/tray.py` lines 166-167 `on_open`: `webbrowser.open(f"http://localhost:{self.port}")`
- `default=True` means left-click (the default action) triggers `on_open`
- Phase 15 VERIFICATION.md human item #2: "Left-Click Opens Browser (APP-04b)" — behavior documented as requiring Windows display

---

## What the Plan Must Produce

The single plan for Phase 19 (19-01-PLAN.md) must accomplish exactly three file changes:

1. **Create** `.planning/phases/17-branch-management/17-VERIFICATION.md`
   - Follow Phase 18's 18-VERIFICATION.md as the exact structural template
   - Document all 3 BRANCH requirements as SATISFIED with code-level evidence
   - Include Human Verification section citing 17-05-SUMMARY.md sign-off
   - Observable Truths table should have ~10-12 items covering: router registered, git_ops functions present, branch name format, dirty-check guard, main-deletion guard, BranchChip component present, AppShell wiring, history ?branch= param, compare toggle, GraphView multi-branch
   - Test results: cite "11 passed" (test_branch.py) and "141 passed, 1 xfailed" (full suite at time of Phase 17 completion)

2. **Update** `.planning/REQUIREMENTS.md`
   - Line 14: Change `[ ]` to `[x]` for APP-04b, add implementation note
   - Lines 122-124: Change BRANCH-01/02/03 from `Phase 19 | Pending` to `Phase 17 | Complete`
   - Line 102: Change APP-04b from `Phase 19 | Pending` to `Phase 15 | Complete`
   - Lines 130-131: Update coverage count from "29" to "31"

3. **Update** `.planning/STATE.md`
   - Update `stopped_at` and `last_updated` to reflect Phase 19 completion
   - Change `status` from `planning` to final state if Phase 19 closes the milestone

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_branch.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BRANCH-01 | `git_list_branches`, `git_create_branch`, branch name format, endpoint | unit/integration | `pytest tests/test_branch.py -x -q` | YES (11 tests, all GREEN) |
| BRANCH-02 | `git_checkout`, dirty-check guard, `git_delete_branch`, main-guard | unit/integration | `pytest tests/test_branch.py -x -q` | YES (11 tests, all GREEN) |
| BRANCH-03 | list_branches endpoint, history with branch param | unit/integration | `pytest tests/test_branch.py -x -q` | YES (11 tests, all GREEN) |
| BRANCH-03 | Branch label shown in UI header | manual | — (requires browser) | N/A — human sign-off 2026-03-15 |
| APP-04b | Tray icon click opens browser | manual | — (requires Windows + pystray) | N/A — Windows-only |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_branch.py -x -q` (confirms no regression)
- **Before close:** `python -m pytest tests/ -x -q` (full suite green)

### Wave 0 Gaps
None — existing test infrastructure covers all phase requirements. Phase 19 creates no new test files.

---

## Open Questions

1. **STATE.md milestone status after Phase 19**
   - What we know: STATE.md frontmatter shows `status: planning` and `total_phases: 11, completed_phases: 10`. Phase 19 is the final phase.
   - What's unclear: Whether closing Phase 19 means the v1.1 milestone status should be updated to `complete`.
   - Recommendation: Update `completed_phases` to 11 and `status` to `complete` in STATE.md frontmatter after Phase 19 closes.

---

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `app/routers/branch.py` — all 5 endpoints with full implementation confirmed
- Codebase inspection: `app/services/git_ops.py` lines 563-645 — all 5 branch functions confirmed
- Codebase inspection: `app/frontend/src/components/BranchChip.tsx` — Popover, handleCreate, handleSwitch, handleDelete all present
- Codebase inspection: `app/frontend/src/components/AppShell.tsx` — activeBranch, fetchBranch, mergeBaseSha, allBranchEntries wiring confirmed
- Codebase inspection: `app/frontend/src/components/ChangesPanel.tsx` — BranchChip imported and rendered
- Codebase inspection: `app/server.py` line 64 — `branch.router` registered
- Codebase inspection: `app/tray.py` lines 166-167 — `on_open` handler with `default=True`
- Codebase inspection: `tests/test_branch.py` — 11 tests, verified GREEN via `pytest tests/test_branch.py -x -q` (11 passed in 0.97s)
- Document inspection: `.planning/phases/17-branch-management/17-05-SUMMARY.md` — `requirements_verified: [BRANCH-01, BRANCH-02, BRANCH-03]`, all 8 human checks PASSED
- Document inspection: `.planning/v1.1-MILESTONE-AUDIT.md` — gap analysis, APP-04b orphan evidence, Phase 17 VERIFICATION.md gap confirmed
- Document inspection: `.planning/phases/15-system-tray-and-auto-start/15-VERIFICATION.md` — APP-04b noted as ORPHANED, human item #2 documents expected behavior
- Document inspection: `.planning/phases/18-ci-polish/18-VERIFICATION.md` — canonical VERIFICATION.md format reference
- Document inspection: `.planning/REQUIREMENTS.md` — current checkbox states (APP-04b unchecked, BRANCH-01/02/03 checked), traceability table, coverage count "29" (stale)

### Secondary (MEDIUM confidence)
- None required — all claims are directly verifiable from codebase and existing planning documents

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- What needs to be created/updated: HIGH — v1.1 audit explicitly names both gaps and their resolutions
- Implementation evidence for BRANCH-01/02/03: HIGH — code read directly, tests confirmed GREEN
- Implementation evidence for APP-04b: HIGH — code read directly from app/tray.py
- VERIFICATION.md format: HIGH — Phase 18 VERIFICATION.md is the established template
- REQUIREMENTS.md changes: HIGH — exact line numbers confirmed by reading the file

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (stable — no moving dependencies; everything is already implemented)
