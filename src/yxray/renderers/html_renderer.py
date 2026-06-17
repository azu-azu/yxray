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
/* ---- Diff details collapsible ---- */
#diff-details-toggle {
  max-width: 960px; margin: 0 auto; padding: 7px 32px;
  display: flex; align-items: center; gap: 7px;
  cursor: pointer; user-select: none;
  font-size: 12px; color: var(--text-muted);
  border-bottom: 1px solid var(--border-subtle);
}
#diff-details-toggle:hover { color: var(--text); }
.diff-chevron { font-style: normal; transition: transform 0.2s ease; display: inline-block; font-size: 10px; }
.diff-chevron.closed { transform: rotate(-90deg); }
#diff-details-wrap { overflow: hidden; transition: max-height 0.25s ease; }
#diff-details-wrap.collapsed { max-height: 0 !important; }
/* ---- Summary stat cards ---- */
#summary { max-width: 960px; margin: 0 auto; padding: 16px 32px 0; }
.stat-cards { display: flex; gap: 12px; margin-bottom: 0; }
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
.ki-badge-input  { background: #d1fae5; color: #065f46; border-color: #6ee7b7; }
.ki-badge-output { background: #dbeafe; color: #1e40af; border-color: #93c5fd; }
.ki-badge-join   { background: #ede9fe; color: #5b21b6; border-color: #c4b5fd; }
.ki-desc { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; color: var(--text); white-space: nowrap; }
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
.tool-row.focused { background: rgba(245,158,11,0.15) !important; outline: 1px solid #f59e0b; }
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
.diff-line-skip { justify-content: center; padding: 2px 0; }
.diff-skip-text { color: var(--text-muted); font-style: italic; font-size: 11px; }
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
/* ---- Report search ---- */
.report-search-wrap { position: relative; display: flex; align-items: center; }
.report-search-input {
  width: 180px; padding: 6px 28px 6px 12px;
  border: 1px solid var(--border); border-radius: 9999px;
  background: var(--surface); color: var(--text);
  font-size: 13px; outline: none; font-family: inherit;
  transition: border-color 0.15s, width 0.2s;
}
.report-search-input:focus { border-color: var(--accent-modified); width: 230px; }
.report-search-input::placeholder { color: var(--text-muted); }
.report-search-clear {
  position: absolute; right: 9px;
  background: none; border: none;
  color: var(--text-muted); cursor: pointer;
  font-size: 14px; line-height: 1; display: none; padding: 0;
}
.report-search-clear:hover { color: var(--text); }
.report-search-count {
  font-size: 11px; color: var(--text-muted); white-space: nowrap;
  min-width: 48px; text-align: right;
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
        <div class="report-search-wrap">
          <input type="text" id="report-search-input" class="report-search-input" placeholder="Search tools…" autocomplete="off" spellcheck="false" oninput="doReportSearch(this.value.trim())" />
          <button class="report-search-clear" id="report-search-clear" aria-label="Clear" onclick="document.getElementById('report-search-input').value='';doReportSearch('');">&times;</button>
        </div>
        <span class="report-search-count" id="report-search-count"></span>
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
</section>
<div id="diff-details-toggle" onclick="toggleDiffDetails()">
  <span class="diff-chevron closed" id="diff-chevron">&#9660;</span>
  Diff Details
</div>
<div id="diff-details-wrap" class="collapsed" style="max-height:0">
<div class="container">
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
    <span class="tool-type-name">{{ tool.short_type }}</span>
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
    <span class="tool-type-name">{{ tool.short_type }}</span>
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
    <span class="tool-type-name">{{ tool.short_type }}</span>
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

function doReportSearch(q) {
    var clearBtn = document.getElementById('report-search-clear');
    var countEl = document.getElementById('report-search-count');
    q = q.toLowerCase();
    if (clearBtn) clearBtn.style.display = q ? 'block' : 'none';
    var secNames = ['added', 'modified', 'removed', 'connections'];
    var totalMatch = 0;
    for (var s = 0; s < secNames.length; s++) {
        var sec = secNames[s];
        var container = document.getElementById('section-' + sec);
        if (!container) continue;
        var rows = container.querySelectorAll('.tool-row');
        var visibleCount = 0;
        for (var r = 0; r < rows.length; r++) {
            var row = rows[r];
            var nameEl = row.querySelector('.tool-type-name');
            var idEl = row.querySelector('.tool-id-pill');
            var text = (nameEl ? nameEl.textContent : '') + ' ' + (idEl ? idEl.textContent : '');
            var match = !q || text.toLowerCase().indexOf(q) !== -1;
            row.style.display = match ? '' : 'none';
            if (!match && row.classList.contains('expanded')) {
                var detailId = row.id.replace('row-', 'detail-');
                var detail = document.getElementById(detailId);
                if (detail) detail.hidden = true;
                row.classList.remove('expanded');
            }
            if (match) visibleCount++;
        }
        totalMatch += visibleCount;
        // Update section count pill
        var pill = document.querySelector('#heading-' + sec + ' .count-pill');
        if (pill) {
            if (q) {
                pill.dataset.origText = pill.dataset.origText || pill.textContent;
                pill.textContent = visibleCount + ' / ' + rows.length;
            } else if (pill.dataset.origText) {
                pill.textContent = pill.dataset.origText;
            }
        }
        var noResultEl = document.getElementById('no-results-' + sec);
        if (q && visibleCount === 0 && rows.length > 0) {
            if (!noResultEl) {
                noResultEl = document.createElement('p');
                noResultEl.id = 'no-results-' + sec;
                noResultEl.className = 'empty';
                noResultEl.textContent = 'No matches.';
                container.appendChild(noResultEl);
            }
            noResultEl.style.display = '';
        } else if (noResultEl) {
            noResultEl.style.display = 'none';
        }
    }
    if (countEl) countEl.textContent = q ? totalMatch + ' hit' + (totalMatch !== 1 ? 's' : '') : '';
    // Scroll to first visible match
    if (q) {
        var scrolled = false;
        for (var s2 = 0; s2 < secNames.length && !scrolled; s2++) {
            var c2 = document.getElementById('section-' + secNames[s2]);
            if (!c2) continue;
            var allRows = c2.querySelectorAll('.tool-row');
            for (var r2 = 0; r2 < allRows.length; r2++) {
                if (allRows[r2].style.display !== 'none') {
                    allRows[r2].scrollIntoView({behavior: 'smooth', block: 'center'});
                    scrolled = true;
                    break;
                }
            }
        }
    }
}

(function() {
    var saved = localStorage.getItem('alteryx-diff-theme');
    if (saved) { setTheme(saved); return; }
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    setTheme(prefersDark !== false ? 'dark' : 'light');
})();

var DIFF_DATA = JSON.parse(document.getElementById('diff-data').textContent);

function expandSection(sectionId) {
    var wrap = document.getElementById('diff-details-wrap');
    var chevron = document.getElementById('diff-chevron');
    if (wrap && wrap.classList.contains('collapsed')) {
        wrap.classList.remove('collapsed');
        wrap.style.maxHeight = wrap.scrollHeight + 'px';
        wrap.addEventListener('transitionend', function onEnd() {
            wrap.style.maxHeight = '';
            wrap.removeEventListener('transitionend', onEnd);
        });
        if (chevron) chevron.classList.remove('closed');
    }
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
    // Apply amber focus to the clicked row and highlight in graph.
    if (_focusPanelEl) { _focusPanelEl.classList.remove('focused'); _focusPanelEl = null; }
    rowEl.classList.add('focused');
    _focusPanelEl = rowEl;
    if (typeof window.graphFocusNode === 'function') window.graphFocusNode(toolId);
}

function flattenConfig(obj, prefix) {
    if (prefix === undefined) prefix = '';
    if (obj === null || obj === undefined) return [prefix + ': null'];
    if (typeof obj !== 'object') return [prefix + ': ' + obj];
    if (Array.isArray(obj)) {
        var out = [];
        obj.forEach(function(item, i) {
            var k = prefix ? prefix + '[' + i + ']' : '[' + i + ']';
            flattenConfig(item, k).forEach(function(l) { out.push(l); });
        });
        return out;
    }
    var out = [];
    Object.keys(obj).forEach(function(k) {
        var sub = prefix ? prefix + '.' + k : k;
        flattenConfig(obj[k], sub).forEach(function(l) { out.push(l); });
    });
    return out;
}

function buildConfigDiff(oldCfg, newCfg) {
    var CONTEXT = 2;
    var oldLines = flattenConfig(oldCfg, '');
    var newLines = flattenConfig(newCfg, '');
    var ops = lcsOps(oldLines, newLines);
    var near = new Array(ops.length).fill(false);
    for (var i = 0; i < ops.length; i++) {
        if (ops[i].type !== 'equal') {
            for (var j = Math.max(0, i - CONTEXT); j <= Math.min(ops.length - 1, i + CONTEXT); j++) near[j] = true;
        }
    }
    var wrap = document.createElement('div');
    wrap.className = 'diff-unified';
    var skip = 0;
    function flushSkip() {
        if (!skip) return;
        var skipEl = document.createElement('div');
        skipEl.className = 'diff-line diff-line-skip';
        var t = document.createElement('span');
        t.className = 'diff-skip-text';
        t.textContent = '⋯ ' + skip + ' unchanged line' + (skip === 1 ? '' : 's') + ' ⋯';
        skipEl.appendChild(t);
        wrap.appendChild(skipEl);
        skip = 0;
    }
    ops.forEach(function(op, idx) {
        if (op.type === 'equal' && !near[idx]) { skip++; return; }
        flushSkip();
        var lineEl = document.createElement('div');
        var cls = op.type === 'equal' ? 'ctx' : op.type === 'delete' ? 'del' : 'ins';
        lineEl.className = 'diff-line diff-line-' + cls;
        var gutter = document.createElement('span');
        gutter.className = 'diff-gutter';
        gutter.textContent = op.type === 'equal' ? ' ' : op.type === 'delete' ? '-' : '+';
        var text = document.createElement('span');
        text.className = 'diff-text';
        text.textContent = op.val;
        lineEl.appendChild(gutter);
        lineEl.appendChild(text);
        wrap.appendChild(lineEl);
    });
    flushSkip();
    return wrap;
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
        frag.appendChild(buildConfigDiff(tool.old_config, tool.new_config));
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

function toggleDiffDetails() {
    var wrap = document.getElementById('diff-details-wrap');
    var chevron = document.getElementById('diff-chevron');
    if (!wrap) return;
    var isOpen = !wrap.classList.contains('collapsed');
    if (isOpen) {
        wrap.style.maxHeight = wrap.scrollHeight + 'px';
        requestAnimationFrame(function() {
            wrap.style.maxHeight = '0';
            wrap.classList.add('collapsed');
        });
    } else {
        wrap.classList.remove('collapsed');
        wrap.style.maxHeight = wrap.scrollHeight + 'px';
        wrap.addEventListener('transitionend', function onEnd() {
            wrap.style.maxHeight = '';
            wrap.removeEventListener('transitionend', onEnd);
        });
    }
    if (chevron) chevron.classList.toggle('closed', isOpen);
}

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
// ── Insights panel drag-resize ────────────────────────────────────────────
(function() {
  var panel = document.getElementById('insights-panel');
  var handle = document.getElementById('insights-panel-drag-handle');
  if (!handle || !panel) return;
  var startX, startW;
  handle.addEventListener('mousedown', function(e) {
    e.preventDefault(); e.stopPropagation();
    startX = e.clientX; startW = panel.offsetWidth;
    handle.classList.add('dragging');
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
  function onMove(e) {
    var dx = e.clientX - startX;
    var newW = Math.max(220, Math.min(Math.floor(window.innerWidth * 0.85), startW + dx));
    panel.style.width = newW + 'px';
  }
  function onUp() {
    handle.classList.remove('dragging');
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  }
})();

// ── Summary panel drag-resize ─────────────────────────────────────────────
(function() {
  var panel = document.getElementById('summary-panel');
  var handle = document.getElementById('summary-panel-drag-handle');
  if (!handle || !panel) return;
  var startX, startW;
  handle.addEventListener('mousedown', function(e) {
    e.preventDefault(); e.stopPropagation();
    startX = e.clientX; startW = panel.offsetWidth;
    handle.classList.add('dragging');
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
  function onMove(e) {
    var dx = e.clientX - startX;
    var newW = Math.max(220, Math.min(Math.floor(window.innerWidth * 0.85), startW + dx));
    panel.style.width = newW + 'px';
  }
  function onUp() {
    handle.classList.remove('dragging');
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  }
})();

var _focusPanelEl = null;
function focusNode(toolId, clickedEl) {
    if (_focusPanelEl) { _focusPanelEl.classList.remove('focused'); _focusPanelEl = null; }
    if (typeof window.graphFocusNode === 'function') window.graphFocusNode(toolId);
    var section = document.getElementById('graph-section');
    if (section) section.scrollIntoView({behavior: 'smooth', block: 'start'});
    if (clickedEl) { clickedEl.classList.add('focused'); _focusPanelEl = clickedEl; }
}

{{ step_detail_js | safe }}

(function() {
    var inp = document.getElementById('report-search-input');
    if (!inp) return;
    inp.addEventListener('input', function() { doReportSearch(this.value.trim()); });
})();
</script>
</div>
</div>
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
