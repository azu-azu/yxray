# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from jinja2 import Environment

from yxray.models import DiffResult, NodeDiff
from yxray.models.diff import EdgeDiff
from yxray.models.workflow import AlteryxNode
from yxray.renderers._companion_window import COMPANION_WINDOW_JS
from yxray.renderers._report_assets import REPORT_BASE_CSS, STEP_DETAIL_JS

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Alteryx Workflow Diff Report</title>
<style>
{{ report_base_css | safe }}
/* ---- Summary stat cards ---- */
.stat-cards { display: flex; gap: 12px; margin-bottom: 24px; }
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
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; }
/* ---- Section headers ---- */
.section-wrap { margin-bottom: 24px; }
.section-header {
  display: flex; align-items: center; gap: 8px;
  border-bottom: 1px solid var(--border-subtle);
  padding: 10px 0 10px 12px; margin-bottom: 8px;
}
.section-header-added { border-left: 3px solid var(--accent-added); }
.section-header-removed { border-left: 3px solid var(--accent-removed); }
.section-header-modified { border-left: 3px solid var(--accent-modified); }
.section-header-conn { border-left: 3px solid var(--accent-conn); }
.section-header-summary { border-left: 3px solid var(--text-muted); cursor: pointer; user-select: none; }
.section-header-summary:hover { opacity: 0.85; }
.summary-chevron { display: inline-block; transition: transform 0.2s ease; margin-left: auto; font-style: normal; flex-shrink: 0; }
.summary-chevron.open { transform: rotate(90deg); }
#summary-steps-wrap { overflow: hidden; transition: max-height 0.25s ease; max-height: 4000px; }
#summary-steps-wrap.collapsed { max-height: 0; }
/* ---- Workflow summary: shared classes live in REPORT_BASE_CSS ---- */
.count-pill-summary { background: var(--surface-2); border-color: var(--border); color: var(--text-muted); }
.section-title { font-size: 14px; font-weight: 600; color: var(--text); margin: 0; }
.count-pill {
  border-radius: 9999px; padding: 2px 10px; font-size: 12px; border: 1px solid;
}
.count-pill-added { background: var(--accent-added-bg); border-color: var(--accent-added-border); color: var(--accent-added); }
.count-pill-removed { background: var(--accent-removed-bg); border-color: var(--accent-removed-border); color: var(--accent-removed); }
.count-pill-modified { background: var(--accent-modified-bg); border-color: var(--accent-modified-border); color: var(--accent-modified); }
.count-pill-conn { background: var(--accent-conn-bg); border-color: var(--accent-conn-border); color: var(--accent-conn); }
.section-actions { margin-left: auto; display: flex; gap: 6px; }
.ctrl-btn {
  background: var(--surface); border: 1px solid var(--border); color: var(--text-muted);
  border-radius: 6px; padding: 4px 10px; font-size: 12px; cursor: pointer;
  font-family: inherit; transition: background 0.15s ease;
}
.ctrl-btn:hover { background: var(--surface-2); }
/* ---- Tool rows ---- */
.tool-row {
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  margin: 8px 0; padding: 10px 14px; cursor: pointer;
  display: flex; align-items: center; user-select: none;
  transition: background 0.15s ease;
}
.tool-row:hover { background: #273449; }
html.light .tool-row:hover { background: #f1f5f9; }
.chevron {
  display: inline-block; transition: transform 0.15s ease;
  margin-right: 8px; font-style: normal; flex-shrink: 0;
}
.tool-row.expanded .chevron { transform: rotate(90deg); }
.tool-type-name { color: var(--text); }
.tool-id-pill {
  background: var(--surface-2); border-radius: 4px; padding: 2px 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px; margin-left: 8px; color: var(--text-muted);
}
.tool-row-right { margin-left: auto; }
.change-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; border: 1px solid;
}
.change-badge-added { background: var(--accent-added-bg); border-color: var(--accent-added-border); color: var(--accent-added); }
.change-badge-removed { background: var(--accent-removed-bg); border-color: var(--accent-removed-border); color: var(--accent-removed); }
.change-badge-modified { background: var(--accent-modified-bg); border-color: var(--accent-modified-border); color: var(--accent-modified); }
.change-badge-conn { background: var(--accent-conn-bg); border-color: var(--accent-conn-border); color: var(--accent-conn); }
/* ---- Expanded detail panel ---- */
.tool-detail {
  background: var(--surface-2); border: 1px solid var(--border); border-top: none;
  border-radius: 0 0 8px 8px; padding: 12px 16px 12px 40px; cursor: pointer;
}
.field-row { margin: 6px 0; }
.field-name {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
  color: var(--text-muted); margin-bottom: 4px; font-weight: 600;
}
.before-row {
  border-left: 3px solid var(--accent-removed); background: var(--accent-removed-bg);
  padding: 6px 10px; margin: 4px 0; display: flex; align-items: baseline;
}
.after-row {
  border-left: 3px solid var(--accent-added); background: var(--accent-added-bg);
  padding: 6px 10px; margin: 4px 0; display: flex; align-items: baseline;
}
.before-label { font-weight: 600; color: var(--accent-removed); flex-shrink: 0; width: 54px; }
.after-label { font-weight: 600; color: var(--accent-added); flex-shrink: 0; width: 54px; }
.value-block {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  white-space: pre-wrap; word-break: break-all; font-size: 13px; color: var(--text);
}
.diff-del { background: var(--accent-removed); color: var(--accent-removed-text); border-radius: 2px; padding: 0 1px; }
.diff-ins { background: var(--accent-added);   color: var(--accent-added-text);   border-radius: 2px; padding: 0 1px; }
.diff-unified {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px; border-radius: 4px; overflow: hidden; margin: 4px 0;
  border: 1px solid var(--border);
}
.diff-line { display: flex; line-height: 1.5; }
.diff-line-del { background: var(--accent-removed-bg); }
.diff-line-ins { background: var(--accent-added-bg); }
.diff-line-ctx { color: var(--text-muted); }
.diff-gutter {
  width: 18px; flex-shrink: 0; text-align: center; font-weight: 700; padding: 0 2px;
  user-select: none;
}
.diff-line-del .diff-gutter { color: var(--accent-removed); }
.diff-line-ins .diff-gutter { color: var(--accent-added); }
.diff-text { flex: 1; white-space: pre-wrap; word-break: break-all; padding: 0 6px; color: var(--text); }
.diff-line-ctx .diff-text { color: var(--text-muted); }
.empty { color: var(--text-muted); font-style: italic; }
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
  <div class="header-inner">
    <div class="header-left">
      <div class="header-title-row">
        <span class="pulse-dot"></span>
        <h1 class="header-title">Alteryx Workflow Diff Report</h1>
      </div>
      <p class="header-meta"><span class="header-meta-label">Before:</span> {{ file_a }}</p>
      <p class="header-meta"><span class="header-meta-label">After:</span> {{ file_b }}</p>
      <p class="header-meta header-meta-generated">Generated: {{ timestamp }}</p>
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
{% if workflow_steps %}
<div class="section-wrap">
  <div class="section-header section-header-summary" onclick="toggleSummarySection()">
    <span class="section-title">Workflow Summary</span>
    <span class="count-pill count-pill-summary">{{ workflow_steps | length }} steps</span>
    <span class="summary-chevron open" id="summary-chevron">&#9654;</span>
  </div>
  <div id="summary-steps-wrap">
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
        <div class="step-detail" data-config="{{ step.config | tojson }}">
          <div class="step-detail-inner"></div>
        </div>
      </li>
      {% endfor %}
    </ol>
  </div>
</div>
{% endif %}
<section id="summary">
  <div class="stat-cards">
    <a href="#heading-added" onclick="expandSection('added'); return true;" class="stat-card stat-card-added">
      <div class="stat-card-top">
        <span class="stat-label">Added</span>
        <span class="stat-dot"></span>
      </div>
      <div class="stat-count">{{ summary.added }}</div>
      <span class="sr-only">Added: {{ summary.added }}</span>
    </a>
    <a href="#heading-modified" onclick="expandSection('modified'); return true;" class="stat-card stat-card-modified">
      <div class="stat-card-top">
        <span class="stat-label">Modified</span>
        <span class="stat-dot"></span>
      </div>
      <div class="stat-count">{{ summary.modified }}</div>
      <span class="sr-only">Modified: {{ summary.modified }}</span>
    </a>
    <a href="#heading-removed" onclick="expandSection('removed'); return true;" class="stat-card stat-card-removed">
      <div class="stat-card-top">
        <span class="stat-label">Removed</span>
        <span class="stat-dot"></span>
      </div>
      <div class="stat-count">{{ summary.removed }}</div>
      <span class="sr-only">Removed: {{ summary.removed }}</span>
    </a>
    <a href="#heading-connections" onclick="expandSection('connections'); return true;" class="stat-card stat-card-conn">
      <div class="stat-card-top">
        <span class="stat-label">Connections</span>
        <span class="stat-dot"></span>
      </div>
      <div class="stat-count">{{ summary.connections }}</div>
      <span class="sr-only">Connections: {{ summary.connections }}</span>
    </a>
  </div>
</section>
<div class="section-wrap">
  <div class="section-header section-header-added" id="heading-added">
    <span class="section-title">Added Tools</span>
    <span class="count-pill count-pill-added">{{ summary.added }}</span>
    <div class="section-actions">
      <button class="ctrl-btn" onclick="expandAll('section-added')">Expand All</button>
      <button class="ctrl-btn" onclick="collapseAll('section-added')">Collapse All</button>
    </div>
  </div>
  <div id="section-added">
  {% for tool in diff_data.added %}
  <div class="tool-row" id="row-added-{{ tool.tool_id }}"
       onclick="toggleTool({{ tool.tool_id }}, 'added')">
    <span class="chevron">&#9654;</span>
    <span class="tool-type-name">{{ tool.tool_type }}</span>
    <span class="tool-id-pill">ID: {{ tool.tool_id }}</span>
    <span class="tool-row-right"><span class="change-badge change-badge-added">added</span></span>
  </div>
  <div class="tool-detail" id="detail-added-{{ tool.tool_id }}" onclick="toggleTool({{ tool.tool_id }}, 'added')" hidden></div>
  {% else %}
  <p class="empty">No added tools.</p>
  {% endfor %}
  </div>
</div>
<div class="section-wrap">
  <div class="section-header section-header-modified" id="heading-modified">
    <span class="section-title">Modified Tools</span>
    <span class="count-pill count-pill-modified">{{ summary.modified }}</span>
    <div class="section-actions">
      <button class="ctrl-btn" onclick="expandAll('section-modified')">Expand All</button>
      <button class="ctrl-btn" onclick="collapseAll('section-modified')">Collapse All</button>
    </div>
  </div>
  <div id="section-modified">
  {% for tool in diff_data.modified %}
  <div class="tool-row" id="row-modified-{{ tool.tool_id }}"
       onclick="toggleTool({{ tool.tool_id }}, 'modified')">
    <span class="chevron">&#9654;</span>
    <span class="tool-type-name">{{ tool.tool_type }}</span>
    <span class="tool-id-pill">ID: {{ tool.tool_id }}</span>
    <span class="tool-row-right"><span class="change-badge change-badge-modified">{{ tool.field_diffs | length }} fields</span></span>
  </div>
  <div class="tool-detail" id="detail-modified-{{ tool.tool_id }}" onclick="toggleTool({{ tool.tool_id }}, 'modified')" hidden></div>
  {% else %}
  <p class="empty">No modified tools.</p>
  {% endfor %}
  </div>
</div>
<div class="section-wrap">
  <div class="section-header section-header-removed" id="heading-removed">
    <span class="section-title">Removed Tools</span>
    <span class="count-pill count-pill-removed">{{ summary.removed }}</span>
    <div class="section-actions">
      <button class="ctrl-btn" onclick="expandAll('section-removed')">Expand All</button>
      <button class="ctrl-btn" onclick="collapseAll('section-removed')">Collapse All</button>
    </div>
  </div>
  <div id="section-removed">
  {% for tool in diff_data.removed %}
  <div class="tool-row" id="row-removed-{{ tool.tool_id }}"
       onclick="toggleTool({{ tool.tool_id }}, 'removed')">
    <span class="chevron">&#9654;</span>
    <span class="tool-type-name">{{ tool.tool_type }}</span>
    <span class="tool-id-pill">ID: {{ tool.tool_id }}</span>
    <span class="tool-row-right"><span class="change-badge change-badge-removed">removed</span></span>
  </div>
  <div class="tool-detail" id="detail-removed-{{ tool.tool_id }}" onclick="toggleTool({{ tool.tool_id }}, 'removed')" hidden></div>
  {% else %}
  <p class="empty">No removed tools.</p>
  {% endfor %}
  </div>
</div>
<div class="section-wrap">
  <div class="section-header section-header-conn" id="heading-connections">
    <span class="section-title">Connection Changes</span>
    <span class="count-pill count-pill-conn">{{ summary.connections }}</span>
    <div class="section-actions">
      <button class="ctrl-btn" onclick="expandAll('section-connections')">Expand All</button>
      <button class="ctrl-btn" onclick="collapseAll('section-connections')">Collapse All</button>
    </div>
  </div>
  <div id="section-connections">
  {% for e in diff_data.connections %}
  <div class="tool-row" id="row-connections-{{ loop.index }}"
       onclick="toggleTool({{ loop.index }}, 'connections')">
    <span class="chevron">&#9654;</span>
    <span class="tool-type-name">{{ e.src_tool }}:{{ e.src_anchor }} to {{ e.dst_tool }}:{{ e.dst_anchor }}</span>
    <span class="tool-row-right"><span class="change-badge change-badge-conn">{{ e.change_type }}</span></span>
  </div>
  <div class="tool-detail" id="detail-connections-{{ loop.index }}" onclick="toggleTool({{ loop.index }}, 'connections')" hidden></div>
  {% else %}
  <p class="empty">No connection changes.</p>
  {% endfor %}
  </div>
</div>
<script type="application/json" id="diff-data">{{ diff_data | tojson }}</script>
{{ graph_html | safe }}
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

var DIFF_DATA = JSON.parse(document.getElementById('diff-data').textContent);

function expandSection(sectionId) {
    var container = document.getElementById('section-' + sectionId);
    if (!container) return;
    var heading = document.getElementById('heading-' + sectionId);
    if (heading) heading.scrollIntoView({behavior: 'smooth'});
    var rows = container.querySelectorAll('.tool-row');
    for (var i = 0; i < rows.length; i++) {
        if (!rows[i].classList.contains('expanded')) rows[i].click();
    }
}

function toggleTool(toolId, section) {
    var detailEl = document.getElementById('detail-' + section + '-' + toolId);
    var rowEl = document.getElementById('row-' + section + '-' + toolId);
    if (!detailEl || !rowEl) return;
    var isExpanded = rowEl.classList.contains('expanded');
    if (isExpanded) {
        detailEl.hidden = true;
        rowEl.classList.remove('expanded');
    } else {
        if (!detailEl.dataset.built) {
            buildDetail(toolId, section, detailEl);
            detailEl.dataset.built = 'true';
        }
        detailEl.hidden = false;
        rowEl.classList.add('expanded');
    }
}

function buildDetail(toolId, section, container) {
    var sectionData = DIFF_DATA[section];
    var tool = null;
    for (var i = 0; i < sectionData.length; i++) {
        if (sectionData[i].tool_id === toolId) { tool = sectionData[i]; break; }
    }
    if (!tool) return;
    var frag = document.createDocumentFragment();
    if (section === 'modified') {
        tool.field_diffs.forEach(function(fd) {
            var row = document.createElement('div');
            row.className = 'field-row';
            var nameEl = document.createElement('div');
            nameEl.className = 'field-name';
            nameEl.textContent = fd.field;
            var aStr = formatVal(fd.before), bStr = formatVal(fd.after);
            row.appendChild(nameEl);
            if (aStr.includes('\\n') || bStr.includes('\\n')) {
                row.appendChild(buildUnifiedDiff(aStr, bStr));
            } else {
                var beforeRow = document.createElement('div');
                beforeRow.className = 'before-row';
                var beforeLabel = document.createElement('span');
                beforeLabel.className = 'before-label';
                beforeLabel.textContent = 'Before: ';
                var beforeVal = document.createElement('span');
                beforeVal.className = 'value-block';
                beforeRow.appendChild(beforeLabel);
                beforeRow.appendChild(beforeVal);
                var afterRow = document.createElement('div');
                afterRow.className = 'after-row';
                var afterLabel = document.createElement('span');
                afterLabel.className = 'after-label';
                afterLabel.textContent = 'After: ';
                var afterVal = document.createElement('span');
                afterVal.className = 'value-block';
                var runs = diffChars(aStr, bStr);
                if (runs) {
                    fillDiffSpans(beforeVal, runs, 'delete');
                    fillDiffSpans(afterVal, runs, 'insert');
                } else {
                    beforeVal.textContent = aStr;
                    afterVal.textContent = bStr;
                }
                afterRow.appendChild(afterLabel);
                afterRow.appendChild(afterVal);
                row.appendChild(beforeRow);
                row.appendChild(afterRow);
            }
            frag.appendChild(row);
        });
    } else if (section === 'added' || section === 'removed') {
        var config = tool.config;
        Object.keys(config).forEach(function(k) {
            var row = document.createElement('div');
            row.className = 'field-row';
            var nameEl = document.createElement('div');
            nameEl.className = 'field-name';
            nameEl.textContent = k;
            var valEl = document.createElement('div');
            valEl.className = 'value-block';
            valEl.textContent = formatVal(config[k]);
            row.appendChild(nameEl);
            row.appendChild(valEl);
            frag.appendChild(row);
        });
    } else if (section === 'connections') {
        var row = document.createElement('div');
        row.className = 'field-row';
        var valEl = document.createElement('span');
        valEl.className = 'value-block';
        valEl.textContent = tool.src_tool + ':' + tool.src_anchor + ' -> ' + tool.dst_tool + ':' + tool.dst_anchor + ' (' + tool.change_type + ')';
        row.appendChild(valEl);
        frag.appendChild(row);
    }
    container.appendChild(frag);
}

function formatVal(v) {
    if (v === null || v === undefined) return 'null';
    if (typeof v === 'object') return JSON.stringify(v, null, 2);
    return String(v);
}

// Shared LCS core: operates on arbitrary arrays.
// Returns [{type:'equal'|'delete'|'insert', val:element}, ...].
function lcsOps(arr, brr) {
    var m = arr.length, n = brr.length;
    var dp = new Array(m + 1);
    var i, j;
    for (i = 0; i <= m; i++) { dp[i] = new Array(n + 1).fill(0); }
    for (i = 1; i <= m; i++) {
        for (j = 1; j <= n; j++) {
            dp[i][j] = arr[i-1] === brr[j-1] ? dp[i-1][j-1] + 1 : Math.max(dp[i-1][j], dp[i][j-1]);
        }
    }
    var ops = [];
    i = m; j = n;
    while (i > 0 || j > 0) {
        if (i > 0 && j > 0 && arr[i-1] === brr[j-1]) {
            ops.push({type: 'equal',  val: arr[i-1]}); i--; j--;
        } else if (j > 0 && (i === 0 || dp[i][j-1] >= dp[i-1][j])) {
            ops.push({type: 'insert', val: brr[j-1]}); j--;
        } else {
            ops.push({type: 'delete', val: arr[i-1]}); i--;
        }
    }
    ops.reverse();
    return ops;
}

// Char-level diff. Returns [{type, text}] runs, or null if too long.
function diffChars(a, b) {
    if (a.length + b.length > 2000) return null;
    var runs = [];
    lcsOps(a.split(''), b.split('')).forEach(function(op) {
        if (runs.length && runs[runs.length-1].type === op.type) {
            runs[runs.length-1].text += op.val;
        } else {
            runs.push({type: op.type, text: op.val});
        }
    });
    return runs;
}

// Populate `container` with inline-diff spans.
// showType: 'delete' for the before side, 'insert' for the after side.
function fillDiffSpans(container, runs, showType) {
    runs.forEach(function(run) {
        if (run.type !== 'equal' && run.type !== showType) return; // skip the other side's changes
        var span = document.createElement('span');
        span.textContent = run.text;
        if (run.type === showType) {
            span.className = showType === 'delete' ? 'diff-del' : 'diff-ins';
        }
        container.appendChild(span);
    });
}

// Line-level diff. Returns [{type, text}] per line.
// Falls back to full delete+insert when too many lines (avoids O(m×n) lag).
function diffLines(a, b) {
    var aLines = a.split('\\n'), bLines = b.split('\\n');
    if (aLines.length + bLines.length > 500) {
        return aLines.map(function(l) { return {type: 'delete', text: l}; })
               .concat(bLines.map(function(l) { return {type: 'insert', text: l}; }));
    }
    return lcsOps(aLines, bLines).map(function(op) { return {type: op.type, text: op.val}; });
}

function buildUnifiedDiff(a, b) {
    var wrap = document.createElement('div');
    wrap.className = 'diff-unified';
    diffLines(a, b).forEach(function(op) {
        var lineEl = document.createElement('div');
        var cls = op.type === 'equal' ? 'ctx' : op.type === 'delete' ? 'del' : 'ins';
        lineEl.className = 'diff-line diff-line-' + cls;
        var gutter = document.createElement('span');
        gutter.className = 'diff-gutter';
        gutter.textContent = op.type === 'equal' ? ' ' : op.type === 'delete' ? '-' : '+';
        var text = document.createElement('span');
        text.className = 'diff-text';
        text.textContent = op.text;
        lineEl.appendChild(gutter);
        lineEl.appendChild(text);
        wrap.appendChild(lineEl);
    });
    return wrap;
}

function expandAll(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var rows = container.querySelectorAll('.tool-row');
    for (var i = 0; i < rows.length; i++) {
        if (!rows[i].classList.contains('expanded')) rows[i].click();
    }
}

function collapseAll(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var rows = container.querySelectorAll('.tool-row.expanded');
    for (var i = 0; i < rows.length; i++) { rows[i].click(); }
}

function toggleSummarySection() {
    var wrap = document.getElementById('summary-steps-wrap');
    var chevron = document.getElementById('summary-chevron');
    if (!wrap) return;
    wrap.classList.toggle('collapsed');
    if (chevron) chevron.classList.toggle('open');
}

{{ step_detail_js | safe }}
</script>
</div>
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
    ) -> str:
        """Render result to a self-contained HTML string.

        Args:
            result: The diff output to render.
            file_a: Display name for the baseline workflow file.
            file_b: Display name for the changed workflow file.
            graph_html: Optional HTML fragment from GraphRenderer to embed in the
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
        return template.render(
            timestamp=datetime.now(UTC).isoformat(),
            file_a=file_a,
            file_b=file_b,
            summary={
                "added": len(result.added_nodes),
                "removed": len(result.removed_nodes),
                "modified": len(result.modified_nodes),
                "connections": len(result.edge_diffs),
            },
            diff_data=self._build_diff_data(result),
            graph_html=graph_html,
            metadata=metadata,
            report_base_css=REPORT_BASE_CSS,
            companion_window_js=COMPANION_WINDOW_JS,
            step_detail_js=STEP_DETAIL_JS,
            workflow_steps=[s.to_dict(include_change=True) for s in workflow_steps]
            if workflow_steps
            else None,
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
            "config": dict(node.config),
        }

    def _node_diff_to_dict(self, nd: NodeDiff) -> dict[str, Any]:
        return {
            "tool_id": int(nd.tool_id),
            "tool_type": nd.old_node.tool_type,
            "field_diffs": [
                {"field": k, "before": v[0], "after": v[1]}
                for k, v in nd.field_diffs.items()
            ],
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
