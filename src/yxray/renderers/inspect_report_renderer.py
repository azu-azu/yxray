# ruff: noqa: E501
"""Standalone HTML report renderer for a single Alteryx workflow (inspect command).

InspectReportRenderer.render(doc) produces a full standalone HTML document
containing the workflow steps list.  No graph is embedded here — the graph
lives in the companion _graph.html file produced by SingleGraphRenderer.
"""

from __future__ import annotations

import pathlib
from typing import Any

from jinja2 import Environment

from yxray.models.workflow import WorkflowDoc
from yxray.renderers._companion_window import COMPANION_WINDOW_JS
from yxray.renderers._report_assets import REPORT_BASE_CSS, STEP_DETAIL_JS

_INSPECT_REPORT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }}</title>
  <style>
{{ report_base_css | safe }}
/* ---- Section headers ---- */
.section-wrap { margin-bottom: 24px; }
.section-header {
  display: flex; align-items: center; gap: 8px;
  border-bottom: 1px solid var(--border-subtle);
  padding: 10px 0 10px 12px; margin-bottom: 8px;
}
.section-header-summary { border-left: 3px solid var(--text-muted); cursor: pointer; user-select: none; }
.section-header-summary:hover { opacity: 0.85; }
.summary-chevron { display: inline-block; transition: transform 0.2s ease; margin-left: auto; font-style: normal; flex-shrink: 0; }
.summary-chevron.open { transform: rotate(90deg); }
#summary-steps-wrap { overflow: hidden; transition: max-height 0.25s ease; max-height: 4000px; }
#summary-steps-wrap.collapsed { max-height: 0; }
.section-title { font-size: 14px; font-weight: 600; color: var(--text); margin: 0; }
.count-pill {
  border-radius: 9999px; padding: 2px 10px; font-size: 12px; border: 1px solid;
}
.count-pill-summary { background: var(--surface-2); border-color: var(--border); color: var(--text-muted); }
/* ---- Workflow summary steps: shared classes live in REPORT_BASE_CSS ---- */
.change-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; border: 1px solid; }
.change-badge-added { background: var(--accent-added-bg); border-color: var(--accent-added-border); color: var(--accent-added); }
.change-badge-removed { background: var(--accent-removed-bg); border-color: var(--accent-removed-border); color: var(--accent-removed); }
.change-badge-modified { background: var(--accent-modified-bg); border-color: var(--accent-modified-border); color: var(--accent-modified); }
.empty { color: var(--text-muted); font-style: italic; }
  </style>
</head>
<body>
<header class="site-header">
  <div class="header-inner">
    <div class="header-left">
      <h1 class="header-title">{{ title }}</h1>
      <p class="header-meta">{{ node_count }} nodes &middot; {{ edge_count }} connections</p>
    </div>
    <div style="display:flex;gap:8px;align-items:center;">
      <button class="theme-toggle" onclick="openGraph()" aria-label="Open graph">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
        Graph
      </button>
      <button id="theme-toggle" class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle dark/light mode">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        <span id="theme-label">Dark</span>
      </button>
    </div>
  </div>
</header>
<div class="container">
  <div class="section-wrap">
    <div class="section-header section-header-summary" onclick="toggleSummarySection()">
      <span class="section-title">Workflow Steps</span>
      {% if workflow_steps %}
      <span class="count-pill count-pill-summary">{{ workflow_steps | length }} steps</span>
      {% endif %}
      <span class="summary-chevron open" id="summary-chevron">&#9654;</span>
    </div>
    <div id="summary-steps-wrap">
      {% if workflow_steps %}
      <ol class="summary-steps">
        {% for step in workflow_steps %}
        <li class="summary-step summary-step-{{ step.category }}{% if step.change %} summary-step-{{ step.change }}{% endif %}"
            onclick="toggleStepDetail(this)">
          <div class="step-row">
            <span class="step-num">{{ loop.index }}.</span>
            <span class="step-badge step-badge-{{ step.category }}">{{ step.short_type }}</span>
            {% if step.description %}<span class="step-desc">{{ step.description }}</span>{% endif %}
            {% if step.change %}<span class="change-badge change-badge-{{ step.change }}">{{ step.change }}</span>{% endif %}
            <span class="step-expand-arrow">&#9654;</span>
          </div>
          <div class="step-detail" data-config='{{ step.config | tojson }}'>
            <div class="step-detail-inner"></div>
          </div>
        </li>
        {% endfor %}
      </ol>
      {% else %}
      <p class="empty">No workflow steps available.</p>
      {% endif %}
    </div>
  </div>
</div>
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

{{ companion_window_js | safe }}

function openGraph() {
    openCompanionFile(window.location.href.replace(/_report(\\.[^./?#]+)([?#].*)?$/, '_graph$1$2'));
}

(function() {
    var saved = localStorage.getItem('alteryx-diff-theme');
    if (saved) { setTheme(saved); return; }
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    setTheme(prefersDark !== false ? 'dark' : 'light');
})();

function toggleSummarySection() {
    var wrap = document.getElementById('summary-steps-wrap');
    var chevron = document.getElementById('summary-chevron');
    if (!wrap) return;
    wrap.classList.toggle('collapsed');
    if (chevron) chevron.classList.toggle('open');
}

{{ step_detail_js | safe }}
</script>
</body>
</html>
"""


class InspectReportRenderer:
    """Render a single WorkflowDoc as a standalone HTML report page.

    Produces a full HTML document (not a fragment) containing the workflow
    steps list.  No graph is embedded — the graph lives in the companion
    _graph.html file produced by SingleGraphRenderer.
    """

    def render(
        self, doc: WorkflowDoc, *, workflow_steps: list[Any] | None = None
    ) -> str:
        """WorkflowDoc → standalone HTML report string.

        Args:
            doc: The parsed workflow document.
            workflow_steps: Optional list of WorkflowStep objects (or dicts with
                ``short_type``, ``category``, ``description``, ``change`` keys).
                When None or empty, a "No workflow steps available." message is shown.

        Returns:
            A self-contained HTML string.
        """
        title = pathlib.Path(doc.filepath).name
        data_node_count = sum(
            1 for n in doc.nodes if "ToolContainer" not in n.tool_type
        )

        steps_dicts: list[Any] | None = None
        if workflow_steps:
            steps_dicts = [
                s.to_dict(include_change=True) if hasattr(s, "to_dict") else s
                for s in workflow_steps
            ]

        env = Environment(autoescape=True)  # noqa: S701
        env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}
        template = env.from_string(_INSPECT_REPORT_TEMPLATE)
        return template.render(
            title=title,
            node_count=data_node_count,
            edge_count=len(doc.connections),
            workflow_steps=steps_dicts,
            report_base_css=REPORT_BASE_CSS,
            companion_window_js=COMPANION_WINDOW_JS,
            step_detail_js=STEP_DETAIL_JS,
        )
