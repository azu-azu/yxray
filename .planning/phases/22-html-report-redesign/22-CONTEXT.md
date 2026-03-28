# Phase 22: HTML Report Redesign - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning
**Source:** PRD Express Path (docs/superpowers/specs/2026-03-27-html-report-redesign-design.md)

<domain>
## Phase Boundary

Rewrite the two embedded Jinja2 template strings in the Python renderers to produce a visually modern, dark-first HTML diff report. This is a **pure CSS/HTML change** — no Python class signatures, no Jinja2 variable names, no JavaScript graph logic, and no CDN references change. Both `_TEMPLATE` (html_renderer.py) and `_GRAPH_FRAGMENT_TEMPLATE` (graph_renderer.py) are rewritten in full.

</domain>

<decisions>
## Implementation Decisions

### Architecture
- Files changed: `src/alteryx_diff/renderers/html_renderer.py` and `src/alteryx_diff/renderers/graph_renderer.py` only
- Python class signatures (`HTMLRenderer`, `GraphRenderer`) are **frozen** — no changes
- Jinja2 variable names are **frozen**: `{{ timestamp }}`, `{{ file_a }}`, `{{ file_b }}`, `{{ summary.added }}`, `{{ summary.removed }}`, `{{ summary.modified }}`, `{{ summary.connections }}`, `{{ diff_data | tojson }}`, `{{ graph_html | safe }}`, `{{ metadata }}`
- vis-network JS logic (`applyThemeColors()`, `LIGHT_COLORS`, `DARK_COLORS`, split/overlay views, click handlers) is **frozen**
- Zero CDN constraint: all CSS, JS, and fonts remain inline — no external dependencies
- Dark/light toggle behaviour and `localStorage` persistence (`alteryx-diff-theme` key) are **frozen**

### Default Theme
- Dark mode is the **default** theme (not light)
- On load: restore saved `localStorage` preference, else check OS preference, else fall back to **dark**
- Light is the secondary toggle state

### Color Tokens (CSS custom properties)
All tokens defined on `:root` with dark values as default. `.light` class overrides to light values.

| Token | Dark | Light |
|---|---|---|
| `--bg` | `#0f172a` | `#ffffff` |
| `--surface` | `#1e293b` | `#f8f9fb` |
| `--surface-2` | `#131f31` | `#f1f5f9` |
| `--border` | `#1e3a5f` | `#e2e8f0` |
| `--border-subtle` | `#334155` | `#f1f5f9` |
| `--text` | `#e2e8f0` | `#0f172a` |
| `--text-muted` | `#64748b` | `#64748b` |
| `--accent-added` | `#57ef92` | `#16a34a` |
| `--accent-added-bg` | `#052e16` | `#f0fdf4` |
| `--accent-added-border` | `#166534` | `#bbf7d0` |
| `--accent-removed` | `#f87171` | `#dc2626` |
| `--accent-removed-bg` | `#2d1515` | `#fef2f2` |
| `--accent-removed-border` | `#7f1d1d` | `#fecaca` |
| `--accent-modified` | `#fbbf24` | `#d97706` |
| `--accent-modified-bg` | `#1c1506` | `#fffbeb` |
| `--accent-modified-border` | `#78350f` | `#fde68a` |
| `--accent-conn` | `#60a5fa` | `#2563eb` |
| `--accent-conn-bg` | `#0c1a3a` | `#eff6ff` |
| `--accent-conn-border` | `#1e3a5f` | `#bfdbfe` |

### Typography
- UI text: `Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- Code/values/diffs: `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`
- Base font size: `14px`
- Muted labels: `11px`, uppercase, `1px` letter-spacing
- Title: `18px`, weight `600` (Semi Bold)
- Stat count: `32px`, weight `700` (Bold)

### Spacing & Shape
- Container max-width: `960px`, centered
- Horizontal padding: `32px`
- Section gaps: `24px`
- Row gaps: `8px`
- Card/row border radius: `8px`
- Transition: `0.15s ease` on hover/expand

### Header Component
- Full-width `--bg` bar, bottom border `--border`
- Left: 8px green pulse dot + title (18px Semi Bold, `--text`) + meta line (`file_a → file_b · timestamp`, `--text-muted`, 12px)
- Right: theme toggle pill — moon icon + "Dark" label, ghost style with `--surface` bg and `--border` stroke

### Summary Stat Cards (replaces flat badge row)
- 4 equal-width cards in `display:flex` row, `12px` gap
- Each card: `--accent-*-bg` fill, `1px --accent-*-border` border, `8px` radius, `16px` padding
- Top row: uppercase label (11px, 1px letter-spacing, `--accent-*` at 70% opacity) + small colored dot (right-aligned, 6px)
- Count: 32px Bold, `--accent-*` color
- Click behaviour unchanged — jumps to section and expands all rows

### Section Headers
- `3px` left accent bar (color = section accent), section name (14px Semi Bold, `--text`), count pill (`--accent-*-bg` + border)
- Right: `Expand All` / `Collapse All` ghost buttons — `--surface` bg, `--border` stroke, `--text-muted` label, `6px` radius
- Bottom border `--border-subtle`

### Tool Rows (collapsed)
- `--surface` bg, `1px --border` border, `8px` radius, `8px` vertical margin
- Left: `▶` chevron (rotates 90° when expanded) + tool type name + ID pill
- Right: field-count badge for modified ("3 fields"), change-type badge for added/removed/connections
- Hover: background `#273449`

### Expanded Detail Panel (modified tools)
- `--surface-2` bg, top border removed, bottom radius only (visually attached to row above)
- Each changed field:
  - Field label: 11px uppercase `--text-muted`
  - Before row: `3px --accent-removed` left border, `--accent-removed-bg` fill, "Before:" label + monospace value
  - After row: `3px --accent-added` left border, `--accent-added-bg` fill, "After:" label + monospace value

### Added / Removed Tool Detail Panel
- Same structure as expanded panel but single-column: field name + monospace value (no before/after split)

### Connection Detail Panel
- Single line: `src_tool:src_anchor → dst_tool:dst_anchor (change_type)` in monospace

### Graph Section
- Section header matches all other section headers (accent bar + title + count + buttons)
- View toggle: `Split View` / `Overlay View` as ghost pill buttons; active state: `--accent-conn` bg, white text
- Graph containers: `--surface` bg, `--border` border, `8px` radius
- **Remove all inline `style=""` attributes and `!important` overrides** from `_GRAPH_FRAGMENT_TEMPLATE`
- Replace removed inline styles with CSS variable references
- vis-network JS logic and node color palettes (`LIGHT_COLORS`, `DARK_COLORS`) are **unchanged**

### Governance Footer
- `<details>` element, `--surface` bg, `--border` top edge, `12px` padding
- `<summary>` label: 12px, `--text-muted`
- Metadata rows: monospace 12px, `--text-muted`, `1.8` line-height

### Behaviour (unchanged)
- Theme toggle persists to `localStorage` key `alteryx-diff-theme`; on load restores saved preference or falls back to OS preference
- Default theme when no saved preference and no OS preference: **dark**
- Tool detail panels lazy-built on first expand (existing `buildDetail()` JS)
- `expandAll()` / `collapseAll()` per section
- Summary card click → scroll to section + expand all rows
- Print: `@media print` hides buttons, forces all details open
- Governance `<details>` open/close is native browser behaviour

### Out of Scope
- Changes to Python class interfaces or method signatures
- Changes to vis-network JS graph logic or node colour computation
- Adding new data fields to the diff output
- CDN references of any kind

### Claude's Discretion
- Exact HTML structure of minor sub-elements not explicitly specified in the spec (e.g. exact div nesting, aria attributes)
- Whether to use a single `<style>` block or multiple (single preferred for readability)
- Exact animation keyframes for the green pulse dot
- Order of CSS property declarations within rules

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Spec (source of truth for all visual decisions)
- `docs/superpowers/specs/2026-03-27-html-report-redesign-design.md` — Full approved design spec with color tokens, typography, spacing, and all component specifications

### Files to Rewrite
- `src/alteryx_diff/renderers/html_renderer.py` — Contains `_TEMPLATE` (the main Jinja2 HTML string) and `HTMLRenderer` class
- `src/alteryx_diff/renderers/graph_renderer.py` — Contains `_GRAPH_FRAGMENT_TEMPLATE` and `GraphRenderer` class

### Reference Output
- `examples/diff_report.html` — Existing rendered report; used to verify the template renders without errors

### Tests
- `tests/test_html_renderer.py` — Existing tests that must continue to pass
- `tests/test_graph_renderer.py` — Existing tests that must continue to pass (if present)

</canonical_refs>

<specifics>
## Specific Ideas

- The green pulse dot in the header should use a CSS keyframe animation (`@keyframes pulse`)
- The `▶` chevron rotation on expand uses `transform: rotate(90deg)` with `transition: 0.15s ease`
- Stat cards use `cursor: pointer` and the existing JS click handler (`scrollToSection`)
- The ID pill on tool rows uses a monospace font at smaller size with `--surface-2` bg
- For the graph `_GRAPH_FRAGMENT_TEMPLATE`: the current `!important` overrides on dark-mode graph elements should be replaced with CSS variables that inherit from the `:root` / `.light` token system
- The template must produce valid HTML that renders correctly when opened as a standalone `.html` file (no server required)

</specifics>

<deferred>
## Deferred Ideas

- Adding syntax highlighting to diff values (e.g. XML-aware coloring)
- Print-specific stylesheet beyond hiding buttons and forcing details open
- Animated transitions between theme states (beyond the 0.15s hover transitions)
- Mobile/responsive layout (current spec targets 960px desktop width)

</deferred>

---

*Phase: 22-html-report-redesign*
*Context gathered: 2026-03-27 via PRD Express Path (docs/superpowers/specs/2026-03-27-html-report-redesign-design.md)*
