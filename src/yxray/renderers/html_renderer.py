# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from jinja2 import Environment

from yxray.models import DiffResult, NodeDiff
from yxray.models.diff import EdgeDiff
from yxray.models.workflow import AlteryxNode
from yxray.renderers._report_assets import REPORT_BASE_CSS, STEP_DETAIL_JS
from yxray.summarizer import _classify

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Alteryx Workflow Diff Report</title>
<style>
{{ report_base_css | safe }}
.site-header { position: sticky; top: 0; z-index: 100; }
.theme-toggle { line-height: 1; }
.theme-toggle svg { display: block; }
/* ---- Summary stat cards ---- */
#summary { max-width: 960px; margin: 0 auto; padding: 16px 32px 0; }
.stat-cards { display: flex; gap: 12px; margin-bottom: 0; align-items: stretch; }
.stat-card-group {
  display: flex; gap: 8px;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
}
.stat-card {
  flex: 1; border-radius: 8px; padding: 16px; cursor: pointer;
  border: 1px solid; transition: opacity 0.15s ease; text-decoration: none;
}
.stat-card:hover { opacity: 0.85; }
.stat-card-added { background: var(--accent-added-bg); border-color: var(--accent-added-border); }
.stat-card-removed { background: var(--accent-removed-bg); border-color: var(--accent-removed-border); }
.stat-card-modified { background: var(--accent-modified-bg); border-color: var(--accent-modified-border); }
.stat-card-conn { background: var(--accent-conn-bg); border-color: var(--accent-conn-border); }
.stat-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.stat-label {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;
}
.stat-card-added .stat-label { color: var(--accent-added); opacity: 0.8; }
.stat-card-removed .stat-label { color: var(--accent-removed); opacity: 0.8; }
.stat-card-modified .stat-label { color: var(--accent-modified); opacity: 0.8; }
.stat-card-conn .stat-label { color: var(--accent-conn); opacity: 0.8; }
.stat-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.stat-card-added .stat-dot { background: var(--accent-added); }
.stat-card-removed .stat-dot { background: var(--accent-removed); }
.stat-card-modified .stat-dot { background: var(--accent-modified); }
.stat-card-conn .stat-dot { background: var(--accent-conn); }
.stat-count { font-size: 32px; font-weight: 700; line-height: 1; }
.stat-card-added .stat-count { color: var(--accent-added); }
.stat-card-removed .stat-count { color: var(--accent-removed); }
.stat-card-modified .stat-count { color: var(--accent-modified); }
.stat-card-conn .stat-count { color: var(--accent-conn); }
/* Input/Output/Join stat card variants */
:root { --accent-join: #c4b5fd; --accent-join-bg: #1e0937; --accent-join-border: #4c1d95; }
html.light { --accent-join: #7c3aed; --accent-join-bg: #f5f3ff; --accent-join-border: #ddd6fe; }
button.stat-card { font: inherit; text-align: left; cursor: pointer; }
.stat-card-input  { background: var(--accent-conn-bg);  border-color: var(--accent-conn-border); }
.stat-card-output { background: var(--accent-added-bg); border-color: var(--accent-added-border); }
.stat-card-join   { background: var(--accent-join-bg);  border-color: var(--accent-join-border); }
.stat-card-input  .stat-label { color: var(--accent-conn);  opacity: 0.8; }
.stat-card-output .stat-label { color: var(--accent-added); opacity: 0.8; }
.stat-card-join   .stat-label { color: var(--accent-join);  opacity: 0.8; }
.stat-card-input  .stat-dot   { background: var(--accent-conn); }
.stat-card-output .stat-dot   { background: var(--accent-added); }
.stat-card-join   .stat-dot   { background: var(--accent-join); }
.stat-card-input  .stat-count { color: var(--accent-conn); }
.stat-card-output .stat-count { color: var(--accent-added); }
.stat-card-join   .stat-count { color: var(--accent-join); }
/* Insights panel (input/output/join list) */
#insights-panel {
  position: fixed; top: 0; left: 0;
  width: 360px; height: 100%;
  background: var(--surface);
  border-right: 1px solid var(--border);
  box-shadow: 2px 0 12px rgba(0,0,0,0.2);
  display: flex; flex-direction: column;
  overflow: hidden;
  transform: translateX(-100%);
  transition: transform 0.2s ease;
  z-index: 1002;
  border-radius: 0 8px 8px 0;
}
#insights-panel.open { transform: translateX(0); }
#insights-panel-drag-handle {
  position: absolute; top: 0; right: 0;
  width: 6px; height: 100%;
  cursor: col-resize; z-index: 10; user-select: none;
}
#insights-panel-drag-handle:hover, #insights-panel-drag-handle.dragging {
  background: rgba(148,163,184,0.18);
}
#insights-panel-header {
  padding: 12px 16px 10px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}
#insights-panel-title { font-size: 14px; font-weight: 600; color: var(--text); }
#insights-panel-body { padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; flex: 1; overflow-y: auto; direction: rtl; min-height: 0; }
#insights-panel-body > * { direction: ltr; }
#insights-panel .panel-close {
  cursor: pointer; color: var(--text-muted);
  font-size: 18px; line-height: 1; background: none; border: none;
}
#insights-panel .panel-close:hover { color: var(--text); }
.ki-row { display: flex; align-items: baseline; gap: 6px; cursor: pointer; border-radius: 4px; padding: 4px 8px; }
.ki-row:hover { background: rgba(148,163,184,0.12); }
.ki-row.focused { background: rgba(245,158,11,0.18); outline: 1px solid #f59e0b; }
.ki-badge { font-size: 10px; font-weight: 700; border-radius: 3px; padding: 1px 5px; flex-shrink: 0; text-transform: uppercase; letter-spacing: 0.03em; border: 1px solid; }
.ki-badge-input  { background: var(--badge-input-bg);  color: var(--badge-input-text);  border-color: var(--badge-input-border); }
.ki-badge-output { background: var(--badge-output-bg); color: var(--badge-output-text); border-color: var(--badge-output-border); }
.ki-badge-join   { background: var(--badge-join-bg);   color: var(--badge-join-text);   border-color: var(--badge-join-border); }
.ki-desc { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; color: var(--text); white-space: nowrap; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; }
.ctrl-btn {
  background: var(--surface); border: 1px solid var(--border); color: var(--text-muted);
  border-radius: 6px; padding: 4px 10px; font-size: 12px; cursor: pointer;
  font-family: inherit; transition: background 0.15s ease;
}
.ctrl-btn:hover { background: var(--surface-2); }
.change-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; border: 1px solid;
}
.change-badge-added { background: var(--accent-added-bg); border-color: var(--accent-added-border); color: var(--accent-added); }
.change-badge-removed { background: var(--accent-removed-bg); border-color: var(--accent-removed-border); color: var(--accent-removed); }
.change-badge-modified { background: var(--accent-modified-bg); border-color: var(--accent-modified-border); color: var(--accent-modified); }
.change-badge-conn { background: var(--accent-conn-bg); border-color: var(--accent-conn-border); color: var(--accent-conn); }
/* ---- Governance footer ---- */
#governance {
  background: var(--surface); border-top: 1px solid var(--border);
  padding: 12px; margin-top: 32px;
}
#governance summary {
  font-size: 12px; color: var(--text-muted); cursor: pointer; user-select: none;
}
.gov-content {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px; color: var(--text-muted); line-height: 1.8; padding: 8px 0;
}
/* ---- Workflow summary step badge focus ---- */
.step-badge.focused { background: #92400e !important; border-color: #f59e0b !important; color: #fef3c7 !important; box-shadow: 0 0 0 2px rgba(245,158,11,0.5); }
/* ---- Left summary panel ---- */
#summary-panel {
  position: fixed; top: 0; left: 0;
  width: 640px; height: 100%;
  background: var(--surface);
  border-right: 1px solid var(--border);
  box-shadow: 2px 0 12px rgba(0,0,0,0.2);
  display: flex; flex-direction: column;
  overflow: hidden;
  transform: translateX(-100%);
  transition: transform 0.2s ease;
  z-index: 1001;
  border-radius: 0 8px 8px 0;
}
#summary-panel.open { transform: translateX(0); }
#summary-panel-drag-handle {
  position: absolute; top: 0; right: 0;
  width: 6px; height: 100%;
  cursor: col-resize; z-index: 10; user-select: none;
}
#summary-panel-drag-handle:hover, #summary-panel-drag-handle.dragging {
  background: rgba(148,163,184,0.18);
}
#summary-panel-header {
  padding: 12px 16px 10px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}
#summary-panel-title { font-size: 14px; font-weight: 600; color: var(--text); }
#summary-panel-body { padding: 10px 12px; flex: 1; overflow-y: auto; direction: rtl; min-height: 0; }
#summary-panel-body > * { direction: ltr; }
#summary-panel-body .change-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; border: 1px solid; }
#summary-panel .panel-close {
  float: none; cursor: pointer; color: var(--text-muted);
  font-size: 18px; line-height: 1; background: none; border: none;
}
#summary-panel .panel-close:hover { color: var(--text); }
/* ---- Print ---- */
@media print {
  .ctrl-btn, .theme-toggle { display: none; }
  .tool-detail { display: block !important; }
  details[id="governance"] { display: block; }
  details[id="governance"] > * { display: block; }
}
</style>
</head>
<body>
<header class="site-header">
  <div class="header-inner" style="flex-direction:column;gap:6px;align-items:stretch;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <div class="header-title-row">
        <span class="pulse-dot"></span>
        <h1 class="header-title">Alteryx Workflow Diff Report</h1>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-shrink:0;">
        {% if workflow_steps %}<button class="theme-toggle" id="summary-btn" onclick="openSummaryPanel()">Summary</button>{% endif %}
        <button class="theme-toggle" onclick="openGraph()" aria-label="Scroll to graph">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
          Graph
        </button>
        <button id="theme-toggle" class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle dark/light mode">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          <span id="theme-label">Dark</span>
        </button>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;gap:2px;">
      <p class="header-meta"><span class="header-meta-label">Before:</span> {{ file_a }}</p>
      <p class="header-meta"><span class="header-meta-label">After:</span> {{ file_b }}</p>
      <p class="header-meta header-meta-generated">Generated: {{ timestamp }}</p>
    </div>
  </div>
</header>
<section id="summary">
  <div class="stat-cards">
    <div class="stat-card stat-card-added">
      <div class="stat-card-top">
        <span class="stat-label">Added</span>
        <span class="stat-dot"></span>
      </div>
      <div class="stat-count">{{ summary.added }}</div>
    </div>
    <div class="stat-card stat-card-modified">
      <div class="stat-card-top">
        <span class="stat-label">Modified</span>
        <span class="stat-dot"></span>
      </div>
      <div class="stat-count">{{ summary.modified }}</div>
    </div>
    <div class="stat-card stat-card-removed">
      <div class="stat-card-top">
        <span class="stat-label">Removed</span>
        <span class="stat-dot"></span>
      </div>
      <div class="stat-count">{{ summary.removed }}</div>
    </div>
    {% if summary.inputs or summary.outputs or summary.joins %}
    <div class="stat-card-group">
      {% if summary.inputs %}<button onclick="openInsightsPanel('input')" class="stat-card stat-card-input">
        <div class="stat-card-top"><span class="stat-label">Input</span><span class="stat-dot"></span></div>
        <div class="stat-count">{{ summary.inputs }}</div>
      </button>{% endif %}
      {% if summary.outputs %}<button onclick="openInsightsPanel('output')" class="stat-card stat-card-output">
        <div class="stat-card-top"><span class="stat-label">Output</span><span class="stat-dot"></span></div>
        <div class="stat-count">{{ summary.outputs }}</div>
      </button>{% endif %}
      {% if summary.joins %}<button onclick="openInsightsPanel('join')" class="stat-card stat-card-join">
        <div class="stat-card-top"><span class="stat-label">Join</span><span class="stat-dot"></span></div>
        <div class="stat-count">{{ summary.joins }}</div>
      </button>{% endif %}
    </div>
    {% endif %}
  </div>
</section>
<script type="application/json" id="diff-data">{{ diff_data | tojson }}</script>
{% if key_insights %}
<script type="application/json" id="insights-data">{{ key_insights | tojson }}</script>
{% endif %}
{% if metadata %}
<details id="governance">
  <summary>Governance Metadata (ALCOA+)</summary>
  <div class="gov-content">
    <div><strong>File A:</strong> {{ metadata.file_a }}</div>
    <div><strong>SHA-256 A:</strong> {{ metadata.sha256_a }}</div>
    <div><strong>File B:</strong> {{ metadata.file_b }}</div>
    <div><strong>SHA-256 B:</strong> {{ metadata.sha256_b }}</div>
    <div><strong>Generated:</strong> {{ metadata.generated_at }}</div>
  </div>
</details>
{% endif %}
<script>
function setTheme(theme) {
    if (theme === 'light') {
        document.documentElement.classList.add('light');
    } else {
        document.documentElement.classList.remove('light');
    }
    localStorage.setItem('alteryx-diff-theme', theme);
    var toggle = document.getElementById('theme-toggle');
    if (toggle) {
        toggle.textContent = theme === 'dark' ? '\u263d Dark' : '\u2600 Light';
    }
}

function toggleTheme() {
    var isLight = document.documentElement.classList.contains('light');
    setTheme(isLight ? 'dark' : 'light');
}

function openGraph() {
    var section = document.getElementById('graph-section');
    if (section) section.scrollIntoView({behavior: 'smooth'});
}

(function() {
    var saved = localStorage.getItem('alteryx-diff-theme');
    if (saved) { setTheme(saved); return; }
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    setTheme(prefersDark !== false ? 'dark' : 'light');
})();

function openSummaryPanel() {
    var sp = document.getElementById('summary-panel');
    var ip = document.getElementById('insights-panel');
    if (!sp) return;
    if (sp.classList.contains('open')) { sp.classList.remove('open'); return; }
    if (ip) { ip.classList.remove('open'); _insightsPanelRole = null; }
    sp.classList.add('open');
}
function closeSummaryPanel() {
    var sp = document.getElementById('summary-panel');
    if (sp) sp.classList.remove('open');
}
// ── Insights panel (input/output/join list) ───────────────────────────────
var _insightsData = (function() {
  var el = document.getElementById('insights-data');
  return el ? JSON.parse(el.textContent) : [];
})();
var _insightsPanelRole = null;
function openInsightsPanel(role) {
  var panel = document.getElementById('insights-panel');
  var sp = document.getElementById('summary-panel');
  if (!panel) return;
  if (panel.classList.contains('open') && _insightsPanelRole === role) {
    panel.classList.remove('open');
    _insightsPanelRole = null;
    return;
  }
  if (sp) sp.classList.remove('open');
  _insightsPanelRole = role;
  var items = _insightsData.filter(function(d) { return d.role === role; });
  var titleEl = document.getElementById('insights-panel-title');
  if (titleEl) titleEl.textContent = role.charAt(0).toUpperCase() + role.slice(1) + 's (' + items.length + ')';
  var body = document.getElementById('insights-panel-body');
  if (body) {
    body.innerHTML = '';
    items.forEach(function(d) {
      var row = document.createElement('div');
      row.className = 'ki-row';
      var badge = document.createElement('span');
      badge.className = 'ki-badge ki-badge-' + d.role;
      badge.textContent = d.short_type;
      var desc = document.createElement('span');
      desc.className = 'ki-desc';
      desc.textContent = d.description || d.short_type;
      row.appendChild(badge);
      row.appendChild(desc);
      (function(toolId, rowEl) {
        rowEl.addEventListener('click', function() { focusNode(toolId, rowEl); });
      })(d.tool_id, row);
      body.appendChild(row);
    });
  }
  panel.classList.add('open');
}
function closeInsightsPanel() {
  var panel = document.getElementById('insights-panel');
  if (panel) { panel.classList.remove('open'); _insightsPanelRole = null; }
}

var _focusPanelEl = null;
function focusNode(toolId, clickedEl) {
    if (_focusPanelEl) { _focusPanelEl.classList.remove('focused'); _focusPanelEl = null; }
    if (typeof window.graphFocusNode === 'function') window.graphFocusNode(toolId);
    var section = document.getElementById('graph-section');
    if (section) section.scrollIntoView({behavior: 'smooth', block: 'start'});
    if (clickedEl) { clickedEl.classList.add('focused'); _focusPanelEl = clickedEl; }
}

{{ step_detail_js | safe }}
</script>
{{ graph_html | safe }}
{% if key_insights %}
<div id="insights-panel">
  <div id="insights-panel-drag-handle"></div>
  <div id="insights-panel-header">
    <span id="insights-panel-title"></span>
    <button class="panel-close" onclick="closeInsightsPanel()">&times;</button>
  </div>
  <div id="insights-panel-body"></div>
</div>
{% endif %}
{% if workflow_steps %}
<div id="summary-panel">
  <div id="summary-panel-drag-handle"></div>
  <div id="summary-panel-header">
    <span id="summary-panel-title">Workflow Summary ({{ workflow_steps | length }} steps)</span>
    <button class="panel-close" onclick="closeSummaryPanel()">&times;</button>
  </div>
  <div id="summary-panel-body">
    <ol class="summary-steps">
      {% for step in workflow_steps %}
      <li class="summary-step summary-step-{{ step.category }}{% if step.change %} summary-step-{{ step.change }}{% endif %}"
          onclick="toggleStepDetail(this)">
        <div class="step-row">
          <span class="step-num">{{ loop.index }}.</span>
          <span class="step-badge step-badge-{{ step.category }}" onclick="event.stopPropagation(); focusNode({{ step.tool_id }}, this)">{{ step.short_type }}</span>
          {% if step.description %}<span class="step-desc">{{ step.description }}</span>{% endif %}
          {% if step.change %}<span class="change-badge change-badge-{{ step.change }}">{{ step.change }}</span>{% endif %}
          <span class="step-expand-arrow">&#9654;</span>
        </div>
        <div class="step-detail" data-config="{{ step.config | tojson | forceescape }}">
          <div class="step-detail-inner"></div>
        </div>
      </li>
      {% endfor %}
    </ol>
  </div>
</div>
{% endif %}
<script>
// ── Panel drag-resize (runs after panels are in the DOM) ──────────────────
(function() {
  var panel = document.getElementById('insights-panel');
  var handle = document.getElementById('insights-panel-drag-handle');
  if (!handle || !panel) return;
  var startX, startW;
  handle.addEventListener('mousedown', function(e) {
    e.preventDefault(); e.stopPropagation();
    startX = e.clientX; startW = panel.offsetWidth;
    handle.classList.add('dragging');
    document.addEventListener('mousemove', onMoveIP);
    document.addEventListener('mouseup', onUpIP);
  });
  function onMoveIP(e) {
    var dx = e.clientX - startX;
    var newW = Math.max(220, Math.min(Math.floor(window.innerWidth * 0.85), startW + dx));
    panel.style.width = newW + 'px';
  }
  function onUpIP() {
    handle.classList.remove('dragging');
    document.removeEventListener('mousemove', onMoveIP);
    document.removeEventListener('mouseup', onUpIP);
  }
})();
(function() {
  var panel = document.getElementById('summary-panel');
  var handle = document.getElementById('summary-panel-drag-handle');
  if (!handle || !panel) return;
  var startX, startW;
  handle.addEventListener('mousedown', function(e) {
    e.preventDefault(); e.stopPropagation();
    startX = e.clientX; startW = panel.offsetWidth;
    handle.classList.add('dragging');
    document.addEventListener('mousemove', onMoveSP);
    document.addEventListener('mouseup', onUpSP);
  });
  function onMoveSP(e) {
    var dx = e.clientX - startX;
    var newW = Math.max(220, Math.min(Math.floor(window.innerWidth * 0.85), startW + dx));
    panel.style.width = newW + 'px';
  }
  function onUpSP() {
    handle.classList.remove('dragging');
    document.removeEventListener('mousemove', onMoveSP);
    document.removeEventListener('mouseup', onUpSP);
  }
})();
</script>
</body>
</html>
"""


class HTMLRenderer:
    """Render a DiffResult to a self-contained HTML string.

    All CSS and JavaScript are embedded inline — no CDN references.
    Tool detail is lazy-loaded from DIFF_DATA JSON in script tag.
    Follows the renderer pattern established by JSONRenderer.
    """

    def render(
        self,
        result: DiffResult,
        file_a: str = "workflow_a.yxmd",
        file_b: str = "workflow_b.yxmd",
        *,
        graph_html: str = "",
        metadata: dict[str, Any] | None = None,
        workflow_steps: list[Any] | None = None,
        key_insights: list[Any] | None = None,
    ) -> str:
        """Render result to a self-contained HTML string.

        Args:
            result: The diff output to render.
            file_a: Display name for the baseline workflow file.
            file_b: Display name for the changed workflow file.
            graph_html: Optional HTML fragment from DiffGraphRenderer to embed in the
                report. When non-empty, the interactive vis-network graph section
                is inserted before the closing container div. Defaults to "".
            metadata: Optional governance metadata dict for ALCOA+ compliance footer.
                When provided, a collapsible ``<details id="governance">`` section is
                appended with file paths, SHA-256 digests, and generation timestamp.
                When ``None`` (default), the footer is omitted — zero regression risk
                for existing callers.

        Returns:
            A self-contained HTML string with all CSS and JavaScript inline.
        """
        # autoescape=True required — avoids ruff B701
        env = Environment(autoescape=True)
        env.policies["json.dumps_kwargs"] = {"ensure_ascii": False, "sort_keys": True}
        template = env.from_string(_TEMPLATE)

        def _role(ki: Any) -> str:
            return ki.role if hasattr(ki, "role") else ki.get("role", "")

        input_count = sum(1 for ki in key_insights if _role(ki) == "input") if key_insights else 0
        output_count = sum(1 for ki in key_insights if _role(ki) == "output") if key_insights else 0
        join_count = sum(1 for ki in key_insights if _role(ki) == "join") if key_insights else 0
        insights_list = (
            [ki.to_dict() if hasattr(ki, "to_dict") else ki for ki in key_insights if _role(ki) != "summary"]
            if key_insights
            else None
        )

        return template.render(
            timestamp=datetime.now(UTC).isoformat(),
            file_a=file_a,
            file_b=file_b,
            summary={
                "added": len(result.added_nodes),
                "removed": len(result.removed_nodes),
                "modified": len(result.modified_nodes),
                "connections": len(result.edge_diffs),
                "inputs": input_count,
                "outputs": output_count,
                "joins": join_count,
            },
            diff_data=self._build_diff_data(result),
            graph_html=graph_html,
            metadata=metadata,
            report_base_css=REPORT_BASE_CSS,
            step_detail_js=STEP_DETAIL_JS,
            workflow_steps=[s.to_dict(include_change=True) for s in workflow_steps]
            if workflow_steps
            else None,
            key_insights=insights_list,
        )

    def _build_diff_data(self, result: DiffResult) -> dict[str, Any]:
        return {
            "added": [self._node_to_dict(n) for n in result.added_nodes],
            "removed": [self._node_to_dict(n) for n in result.removed_nodes],
            "modified": [self._node_diff_to_dict(nd) for nd in result.modified_nodes],
            "connections": [
                self._edge_to_dict(e, i + 1) for i, e in enumerate(result.edge_diffs)
            ],
        }

    def _node_to_dict(self, node: AlteryxNode) -> dict[str, Any]:
        return {
            "tool_id": int(node.tool_id),
            "tool_type": node.tool_type,
            "short_type": _classify(node.tool_type)[0],
            "config": dict(node.config),
        }

    def _node_diff_to_dict(self, nd: NodeDiff) -> dict[str, Any]:
        return {
            "tool_id": int(nd.tool_id),
            "tool_type": nd.old_node.tool_type,
            "short_type": _classify(nd.old_node.tool_type)[0],
            "field_diffs": [
                {"field": k, "before": v[0], "after": v[1]}
                for k, v in nd.field_diffs.items()
            ],
            "old_config": dict(nd.old_node.config),
            "new_config": dict(nd.new_node.config),
        }

    def _edge_to_dict(self, e: EdgeDiff, index: int) -> dict[str, Any]:
        return {
            "tool_id": index,
            "src_tool": int(e.src_tool),
            "src_anchor": str(e.src_anchor),
            "dst_tool": int(e.dst_tool),
            "dst_anchor": str(e.dst_anchor),
            "change_type": e.change_type,
        }
