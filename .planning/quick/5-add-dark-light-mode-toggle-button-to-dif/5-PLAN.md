---
phase: quick-5
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/alteryx_diff/renderers/html_renderer.py
  - src/alteryx_diff/renderers/graph_renderer.py
autonomous: true
requirements: [QUICK-5]

must_haves:
  truths:
    - "A visible toggle button appears in the report header area"
    - "Clicking the button switches the full page between dark and light modes"
    - "The graph container and diff panel also switch themes when toggled"
    - "The chosen mode persists across page refresh via localStorage"
    - "When no localStorage preference exists, the OS prefers-color-scheme is respected"
  artifacts:
    - path: "src/alteryx_diff/renderers/html_renderer.py"
      provides: "Toggle button in header, theme JS, data-theme attribute CSS overrides"
    - path: "src/alteryx_diff/renderers/graph_renderer.py"
      provides: "Graph/panel dark styles respond to [data-theme=dark] instead of only media query"
  key_links:
    - from: "toggle button onclick"
      to: "document.documentElement.dataset.theme"
      via: "setTheme() JS function writing to localStorage and toggling attribute"
    - from: "[data-theme=dark] :root CSS block"
      to: "all --bg, --text, etc. variables"
      via: "attribute selector overriding media query defaults"
---

<objective>
Add a manual dark/light mode toggle button to the diff report that overrides the automatic OS-based dark mode set in quick task 4.

Purpose: Users running the report in a browser whose OS theme differs from their preference need a manual escape hatch. The toggle persists via localStorage so the choice survives refresh.
Output: Modified html_renderer.py and graph_renderer.py with toggle button, JS theme logic, and CSS attribute selectors.
</objective>

<execution_context>
@/Users/laxmikantmukkawar/.claude/get-shit-done/workflows/execute-plan.md
@/Users/laxmikantmukkawar/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/alteryx_diff/renderers/html_renderer.py
@src/alteryx_diff/renderers/graph_renderer.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add theme toggle to html_renderer.py — CSS overrides, button, and JS</name>
  <files>src/alteryx_diff/renderers/html_renderer.py</files>
  <action>
Make three changes to the `_TEMPLATE` string in html_renderer.py:

**1. Add `[data-theme=dark]` CSS override block** immediately after the existing `@media (prefers-color-scheme: dark)` block (keep the media query — it handles the no-preference case). The new block mirrors the exact same variable values:

```css
[data-theme=dark] :root {
  --bg: #0f172a;
  --text: #e2e8f0;
  /* ... same values as in the @media block ... */
}
[data-theme=light] :root {
  --bg: #fff;
  --text: #212529;
  /* ... same values as the :root defaults ... */
}
```

**2. Add toggle button to the `<header>` block** after the two `<p>` tags. Use a button with id `theme-toggle` styled inline (no new class — keep style simple):

```html
<button id="theme-toggle" class="ctrl-btn" style="margin-top:8px;" onclick="toggleTheme()">&#9790; Dark</button>
```

The button label/icon should update dynamically. Use &#9790; (crescent moon) for "Dark mode active" and &#9728; (sun) for "Light mode active".

**3. Add `setTheme()` / `toggleTheme()` JS** before the closing `</script>` tag (can be at the top of the existing `<script>` block). The logic:

```javascript
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('alteryx-diff-theme', theme);
    var btn = document.getElementById('theme-toggle');
    if (btn) {
        btn.textContent = theme === 'dark' ? '\u2600 Light' : '\u263e Dark';
    }
}

function toggleTheme() {
    var current = document.documentElement.getAttribute('data-theme');
    setTheme(current === 'dark' ? 'light' : 'dark');
}

// On load: restore from localStorage, else detect OS preference
(function() {
    var saved = localStorage.getItem('alteryx-diff-theme');
    if (saved) {
        setTheme(saved);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        setTheme('dark');
    }
    // No else: leave data-theme unset so @media query applies naturally
})();
```

Place the IIFE at the very top of the `<script>` block so theme is applied before first paint (prevents flash). The `setTheme` and `toggleTheme` functions must be defined before the IIFE.

Note: The existing `@media (prefers-color-scheme: dark)` block stays unchanged — it handles initial render when no localStorage preference exists.
  </action>
  <verify>
    <automated>cd /Users/laxmikantmukkawar/Documents/Projects/alteryx_diff && python -c "from alteryx_diff.renderers.html_renderer import HTMLRenderer; h = HTMLRenderer(); from alteryx_diff.models.diff import DiffResult; r = DiffResult(added_nodes=(), removed_nodes=(), modified_nodes=(), edge_diffs=()); html = h.render(r); assert 'theme-toggle' in html; assert 'setTheme' in html; assert 'toggleTheme' in html; assert 'alteryx-diff-theme' in html; assert 'data-theme=dark' in html; print('OK')"</automated>
  </verify>
  <done>Generated HTML contains theme-toggle button, setTheme/toggleTheme JS functions, localStorage key, and [data-theme=dark] CSS block. All existing tests still pass.</done>
</task>

<task type="auto">
  <name>Task 2: Update graph_renderer.py dark styles to respond to data-theme attribute</name>
  <files>src/alteryx_diff/renderers/graph_renderer.py</files>
  <action>
The graph fragment's inline `<style>` block currently only responds to `@media (prefers-color-scheme: dark)`. Add matching `[data-theme=dark]` attribute selectors so the toggle applies to graph elements too.

In the `<style>` block inside `_GRAPH_FRAGMENT_TEMPLATE`, after the existing `@media (prefers-color-scheme: dark)` block, add:

```css
[data-theme=dark] #graph-section:fullscreen { background: #0f172a; }
[data-theme=dark] #graph-container { background: #0f172a !important; border-color: #334155 !important; }
[data-theme=dark] #diff-panel { background: #1e293b !important; border-color: #334155 !important; color: #e2e8f0 !important; }
[data-theme=dark] .panel-title { border-color: #334155 !important; color: #e2e8f0; }
[data-theme=dark] .panel-field-name { color: #94a3b8 !important; }
[data-theme=dark] .panel-before { background: #2d1518 !important; }
[data-theme=dark] .panel-after { background: #132318 !important; }
[data-theme=dark] .value-mono { color: #e2e8f0; }
[data-theme=light] #graph-container { background: #f8fafc !important; border-color: #dee2e6 !important; }
[data-theme=light] #diff-panel { background: #fff !important; border-color: #dee2e6 !important; color: inherit !important; }
```

Keep the existing `@media (prefers-color-scheme: dark)` block unchanged — it handles the OS-only case.

The legend color dot spans inside `#graph-controls` use hardcoded inline `background:` hex values for the status colors (added/removed/modified/connection/unchanged). These are graph semantic colors, not theme-dependent — do not change them.
  </action>
  <verify>
    <automated>cd /Users/laxmikantmukkawar/Documents/Projects/alteryx_diff && python -c "from alteryx_diff.renderers.graph_renderer import _GRAPH_FRAGMENT_TEMPLATE; assert 'data-theme=dark' in _GRAPH_FRAGMENT_TEMPLATE; assert 'data-theme=light' in _GRAPH_FRAGMENT_TEMPLATE; print('OK')"</automated>
  </verify>
  <done>[data-theme=dark] and [data-theme=light] CSS selectors present in graph fragment template. Graph container and diff panel respond to manual theme toggle.</done>
</task>

<task type="auto">
  <name>Task 3: Run full test suite to confirm no regressions</name>
  <files></files>
  <action>
Run the full pytest suite. No test changes are needed — the toggle is pure template/JS/CSS. Confirm all 105 tests pass.

If any test fails due to HTML content assertions (e.g., checking for specific HTML structure), inspect and fix the template changes — do not modify tests.
  </action>
  <verify>
    <automated>cd /Users/laxmikantmukkawar/Documents/Projects/alteryx_diff && python -m pytest --tb=short -q 2>&1 | tail -5</automated>
  </verify>
  <done>All 105 tests pass with exit code 0.</done>
</task>

</tasks>

<verification>
After all tasks complete:
1. `python -m pytest -q` exits 0 with 105 tests passing
2. Regenerate diff_report.html: `python -m alteryx_diff workflow.yxmd workflow2.yxmd -o diff_report.html` (if .yxmd files available)
3. Open diff_report.html in browser — toggle button visible in header
4. Click toggle: full page switches mode including graph background and diff panel
5. Refresh page: chosen mode persists
6. In a private/incognito window (no localStorage): OS theme applies automatically
</verification>

<success_criteria>
- Toggle button renders in the report header with sun/moon icon that updates on click
- Clicking switches all CSS variables for body, graph container, and diff panel
- localStorage key `alteryx-diff-theme` is written and read correctly
- OS-based dark mode still works when no localStorage preference is set (no regression)
- All 105 existing tests pass
</success_criteria>

<output>
After completion, create `.planning/quick/5-add-dark-light-mode-toggle-button-to-dif/5-SUMMARY.md`
</output>
