---
phase: 22-html-report-redesign
plan: "02"
subsystem: renderers
tags: [css-variables, theming, graph, vis-network, no-inline-styles]
dependency_graph:
  requires: []
  provides: [restyled-graph-fragment-template]
  affects: [src/alteryx_diff/renderers/graph_renderer.py]
tech_stack:
  added: []
  patterns: [css-variable-tokens, class-based-styling, light-dark-theme-via-classlist]
key_files:
  created: []
  modified:
    - src/alteryx_diff/renderers/graph_renderer.py
decisions:
  - "isDark() uses classList.contains('light') to match Plan 01's :root/html.light theme system"
  - "MutationObserver watches class attribute instead of data-theme attribute"
  - "window.matchMedia prefers-color-scheme listener removed — OS preference handled by main template JS"
  - "split-change-empty CSS class replaces inline style JS DOM assignments in buildCenterPanel empty state"
metrics:
  duration_min: 3
  completed_date: "2026-03-28"
  tasks_completed: 1
  files_modified: 1
---

# Phase 22 Plan 02: Graph Fragment CSS Variable Rewrite Summary

Graph fragment rewritten to use CSS variable token system with zero inline style attributes and zero !important overrides, aligned with Plan 01's :root/html.light theme architecture.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite _GRAPH_FRAGMENT_TEMPLATE — remove inline styles and !important, add CSS classes | 5c9d5d0 | src/alteryx_diff/renderers/graph_renderer.py |

## Decisions Made

1. **isDark() via classList**: Changed from `getAttribute('data-theme')` comparison to `!classList.contains('light')` — matches Plan 01's theme system where dark is the default (:root) and light is the override (html.light class).

2. **MutationObserver target**: Changed `attributeFilter: ['data-theme']` to `attributeFilter: ['class']` — consistent with new theme detection mechanism.

3. **Removed prefers-color-scheme media query listener from JS**: The main template (Plan 01) owns OS preference detection and applies/removes the `.light` class accordingly. The graph fragment only needs to react to class changes.

4. **split-change-empty CSS class**: Added `.split-change-empty` class to style sheet and replaced inline style JS DOM assignments (`empty.style.padding`, `empty.style.color`, `empty.style.fontSize`) in `buildCenterPanel()` empty state with `empty.className = 'split-change-empty'`.

## Verification Results

All acceptance criteria satisfied:

- `grep -c 'style="' src/alteryx_diff/renderers/graph_renderer.py` → **0** (zero inline styles in HTML)
- `grep -c '!important' src/alteryx_diff/renderers/graph_renderer.py` → **0** (zero !important overrides)
- `grep -c 'var(--' src/alteryx_diff/renderers/graph_renderer.py` → **42** (CSS variable references, >= 20 required)
- `grep "graph-container"` → matches present
- `grep "diff-panel"` → matches present
- `grep "graph-overlay"` → matches present
- `grep "Escape"` → matches present
- `grep "vis.Network"` → matches present
- `grep "DIFF_DATA"` → matches present
- `grep "classList.contains"` → match present (new isDark check)
- `grep "data-theme"` → **no matches** (old system removed)
- `grep "class GraphRenderer"` → match present (class unchanged)
- `grep "def render"` → match present (method signature unchanged)
- `python -m pytest tests/test_graph_renderer.py -x` → **8/8 passed**

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all CSS variable references (`var(--accent-conn)`, `var(--border)`, `var(--surface)`, `var(--bg)`, `var(--text)`, `var(--text-muted)`, `var(--surface-2)`, `var(--accent-removed-bg)`, `var(--accent-removed)`, `var(--accent-added-bg)`, `var(--accent-added)`, `var(--border-subtle)`) are provided by Plan 01's CSS token system in the main template.

## Self-Check: PASSED

- File modified: `src/alteryx_diff/renderers/graph_renderer.py` — FOUND
- Task commit: `5c9d5d0` — FOUND (verified via git log)
