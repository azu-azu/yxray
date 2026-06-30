# ruff: noqa: E501
"""Standalone HTML report renderer for a single Alteryx workflow.

SingleGraphRenderer.render(doc) produces a full standalone HTML document
(not a fragment) containing an interactive vis-network graph.

vis-network UMD is inlined via load_vis_js() — zero CDN references.
Physics is disabled; nodes are placed at their Alteryx canvas coordinates.
Same-type BFS clusters (purple) and ToolContainer dashed borders are drawn.
"""

from __future__ import annotations

import importlib.resources as pkg_resources
import pathlib
from typing import Any

from jinja2 import Environment

from yxray.models.workflow import AlteryxNode, WorkflowDoc
from yxray.renderers._graph_builder import _safe_json, load_vis_js
from yxray.renderers._report_assets import CONTRAST_COLOR_JS, STEP_DETAIL_JS
from yxray.topology import compute_node_layer


def _load_single_graph_js() -> str:
    """Load the single-graph JavaScript bundle from the static package directory."""
    try:
        return (
            pkg_resources.files("yxray")
            .joinpath("static/single_graph.js")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, TypeError):
        p = pathlib.Path(__file__).parent.parent / "static" / "single_graph.js"
        return p.read_text(encoding="utf-8")


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }}</title>
  <style>
    :root {
      --bg: #0f172a;
      --surface: #1e293b;
      --surface-2: #334155;
      --border: #334155;
      --border-subtle: #1e293b;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --node-bg: #1d4ed8;
      --node-border: #3b82f6;
      --node-font: #e2e8f0;
      --node-hover: #2563eb;
      --node-select: #1e40af;
      --edge-color: #475569;
      --accent-added: #57ef92; --accent-added-bg: #052e16; --accent-added-border: #166534;
      --accent-modified: #fbbf24; --accent-modified-bg: #1c1506; --accent-modified-border: #78350f;
      --accent-conn: #60a5fa; --accent-conn-bg: #0c1a3a; --accent-conn-border: #1e3a5f;
      --badge-input-bg: #052e16;  --badge-input-text: #6ee7b7;  --badge-input-border: #166534;
      --badge-output-bg: #0c1a3a; --badge-output-text: #93c5fd; --badge-output-border: #1e3a5f;
      --badge-join-bg: #2e1065;   --badge-join-text: #c4b5fd;   --badge-join-border: #4c1d95;
      --badge-union-bg: #1e293b;  --badge-union-text: #94a3b8;  --badge-union-border: #334155;
      --badge-aggregate-bg: #1c1506; --badge-aggregate-text: #fcd34d; --badge-aggregate-border: #78350f;
      --badge-filter-bg: #450a0a;  --badge-filter-text: #fca5a5;  --badge-filter-border: #7f1d1d;
      --badge-formula-bg: #0c2938; --badge-formula-text: #67e8f9; --badge-formula-border: #164e63;
      --badge-reshape-bg: #1e1b4b; --badge-reshape-text: #a5b4fc; --badge-reshape-border: #3730a3;
      --connect-hint-bg: #92400e; --connect-hint-text: #fef3c7;
    }
    html.light {
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-2: #f1f5f9;
      --border: #e2e8f0;
      --border-subtle: #f1f5f9;
      --text: #0f172a;
      --text-muted: #64748b;
      --accent: #0284c7;
      --node-bg: #93c5fd;
      --node-border: #1d4ed8;
      --node-font: #1e293b;
      --node-hover: #bfdbfe;
      --node-select: #60a5fa;
      --edge-color: #94a3b8;
      --accent-added: #16a34a; --accent-added-bg: #f0fdf4; --accent-added-border: #bbf7d0;
      --accent-modified: #d97706; --accent-modified-bg: #fffbeb; --accent-modified-border: #fde68a;
      --accent-conn: #2563eb; --accent-conn-bg: #eff6ff; --accent-conn-border: #bfdbfe;
      --badge-input-bg: #d1fae5;  --badge-input-text: #065f46;  --badge-input-border: #6ee7b7;
      --badge-output-bg: #dbeafe; --badge-output-text: #1e40af; --badge-output-border: #93c5fd;
      --badge-join-bg: #ede9fe;   --badge-join-text: #5b21b6;   --badge-join-border: #c4b5fd;
      --badge-union-bg: #f1f5f9;  --badge-union-text: #475569;  --badge-union-border: #cbd5e1;
      --badge-aggregate-bg: #fef3c7; --badge-aggregate-text: #92400e; --badge-aggregate-border: #fcd34d;
      --badge-filter-bg: #fee2e2;  --badge-filter-text: #991b1b;  --badge-filter-border: #fca5a5;
      --badge-formula-bg: #cffafe; --badge-formula-text: #155e75; --badge-formula-border: #67e8f9;
      --badge-reshape-bg: #e0e7ff; --badge-reshape-text: #3730a3; --badge-reshape-border: #a5b4fc;
      --connect-hint-bg: #ca8a04; --connect-hint-text: #fff;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      overflow: hidden;
      display: flex; flex-direction: column; height: 100vh;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 20px;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
    }
    .header-title { font-size: 15px; font-weight: 600; color: var(--text); }
    .header-meta { font-size: 12px; color: var(--text-muted); }
    .header-hints { font-size: 11px; color: var(--text-muted); margin-top: 3px; display: flex; gap: 5px; align-items: center; flex-wrap: wrap; }
    .hint-item { opacity: 0.7; }
    .hint-sep { opacity: 0.35; }
    .header-right { display: flex; align-items: center; gap: 10px; }
    .ctrl-btn {
      padding: 5px 12px;
      border: 1px solid var(--border);
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      background: var(--surface-2);
      color: var(--text);
      transition: background 0.15s;
    }
    .ctrl-btn:hover { background: var(--border); }
    .ctrl-btn-active { background: var(--accent) !important; color: #fff !important; border-color: var(--accent) !important; }
    .search-wrap { position: relative; display: flex; align-items: center; }
    .search-input {
      width: 200px; padding: 5px 28px 5px 10px;
      border: 1px solid var(--border); border-radius: 6px;
      background: var(--surface-2); color: var(--text);
      font-size: 12px; outline: none;
      transition: border-color 0.15s, width 0.2s;
    }
    .search-input:focus { border-color: var(--accent); width: 260px; }
    .search-input::placeholder { color: var(--text-muted); }
    .search-clear {
      position: absolute; right: 6px;
      background: none; border: none;
      color: var(--text-muted); cursor: pointer;
      font-size: 14px; line-height: 1; display: none; padding: 0;
    }
    .search-clear:hover { color: var(--text); }
    header { flex-shrink: 0; }
    #graph-wrapper {
      flex: 1;
      background: var(--bg);
      overflow: hidden;
      position: relative;
    }
    #graph-canvas { width: 100%; height: 100%; }
    #minimap-wrap {
      position: absolute;
      bottom: 16px;
      right: 16px;
      z-index: 500;
      border-radius: 6px;
      overflow: hidden;
      border: 1px solid var(--border);
      box-shadow: 0 2px 12px rgba(0,0,0,0.35);
      background: var(--surface);
      user-select: none;
    }
    #minimap-canvas { display: block; }
    #minimap-resize-handle {
      position: absolute;
      top: 0; left: 0;
      width: 16px; height: 16px;
      cursor: nw-resize;
      z-index: 2;
      opacity: 0;
      transition: opacity 0.15s;
    }
    #minimap-resize-handle::before {
      content: '';
      position: absolute;
      top: 4px; left: 4px;
      width: 7px; height: 7px;
      border-top: 2px solid var(--text-muted);
      border-left: 2px solid var(--text-muted);
      border-radius: 1px;
    }
    #minimap-wrap:hover #minimap-resize-handle { opacity: 1; }
    #minimap-close {
      position: absolute;
      top: 3px; right: 4px;
      background: none; border: none;
      color: var(--text-muted); cursor: pointer;
      font-size: 12px; line-height: 1; padding: 0 2px;
      opacity: 0;
      transition: opacity 0.15s;
    }
    #minimap-wrap:hover #minimap-close { opacity: 1; }
    #minimap-close:hover { color: var(--text); }
    #minimap-reopen {
      position: absolute;
      bottom: 16px; right: 16px;
      z-index: 500;
      padding: 5px 8px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--surface-2);
      color: var(--text-muted);
      font-size: 11px;
      cursor: pointer;
      display: none;
    }
    #minimap-reopen:hover { background: var(--border); color: var(--text); }
    #config-panel {
      position: fixed;
      top: 0; right: 0;
      width: 400px; height: 100%;
      background: var(--surface);
      border-left: 1px solid var(--border);
      box-shadow: -2px 0 12px rgba(0,0,0,0.2);
      display: flex; flex-direction: column;
      overflow: hidden;
      transform: translateX(100%);
      transition: transform 0.2s ease;
      z-index: 1000;
      border-radius: 8px 0 0 8px;
    }
    #config-panel .panel-title { padding: 20px 20px 10px; margin-bottom: 0; flex-shrink: 0; }
    #panel-body { flex: 1; overflow-y: auto; padding: 14px 20px 20px; min-height: 0; }
    #config-panel.open { transform: translateX(0); }
    #panel-drag-handle {
      position: absolute;
      top: 0; left: 0;
      width: 6px; height: 100%;
      cursor: col-resize;
      z-index: 10;
      user-select: none;
    }
    #panel-drag-handle:hover, #panel-drag-handle.dragging {
      background: rgba(148,163,184,0.18);
    }
    #panel-overlay {
      display: none;
      position: fixed;
      inset: 0;
      z-index: 999;
    }
    #config-panel.open ~ #panel-overlay { display: block; }
    #left-panel-overlay {
      display: none;
      position: fixed;
      inset: 0;
      z-index: 999;
    }
    .panel-title {
      font-size: 14px; font-weight: 600;
      margin-bottom: 10px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border);
      color: var(--text);
    }
    .panel-close {
      float: right; cursor: pointer;
      color: var(--text-muted); font-size: 18px; line-height: 1;
      background: none; border: none;
    }
    .panel-close:hover { color: var(--text); }
    #panel-title-text { cursor: pointer; }
    #panel-title-text:hover { color: var(--accent); text-decoration: underline; }
    #panel-action-bar {
      display: flex; gap: 6px; flex-wrap: wrap;
      margin-bottom: 12px;
    }
    .panel-action-btn {
      cursor: pointer; font-size: 11px; color: var(--text-muted);
      background: none; border: 1px solid var(--border);
      border-radius: 3px; padding: 2px 8px; line-height: 1.5;
    }
    .panel-action-btn:hover { color: var(--text); border-color: var(--text-muted); }
    .config-row { margin: 8px 0; }
    .config-key {
      font-size: 11px; font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase; letter-spacing: 0.8px;
      margin-bottom: 3px;
    }
    .config-val {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px; color: var(--text);
      white-space: pre-wrap; word-break: break-all;
      background: var(--surface-2); padding: 4px 8px; border-radius: 4px;
    }
    .cluster-member-header {
      font-size: 12px; font-weight: 600; color: var(--accent);
      margin: 10px 0 4px; padding-top: 8px;
      border-top: 1px solid var(--border-subtle);
    }
    #panel-table-wrapper {
      overflow: auto;
      max-height: calc(100vh - 220px);
      border: 1px solid var(--border);
      border-radius: 4px;
    }
    #panel-data-table {
      border-collapse: collapse;
      font-size: 12px;
      width: 100%;
    }
    #panel-data-table thead th {
      text-align: left; padding: 5px 8px;
      border-bottom: 2px solid var(--border);
      font-size: 11px; font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase; letter-spacing: 0.8px;
      position: sticky; top: 0;
      background: var(--surface);
      white-space: nowrap;
    }
    #panel-data-table tbody td {
      padding: 3px 8px;
      border-bottom: 1px solid var(--border-subtle);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      white-space: nowrap; color: var(--text);
    }
    #panel-data-table tbody tr:hover td { background: var(--surface-2); }
    /* Memo feature */
    #memo-modal-overlay {
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,0.4); z-index: 1999;
    }
    #memo-modal-overlay.open { display: block; }
    #memo-modal {
      display: none; position: fixed;
      top: 50%; left: 50%; transform: translate(-50%,-50%);
      z-index: 2000; width: 300px;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 10px; padding: 16px 18px 14px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    #memo-modal.open { display: block; }
    .memo-modal-title {
      font-size: 11px; font-weight: 600; color: var(--text-muted);
      text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: 10px;
    }
    #memo-textarea {
      width: 100%; min-height: 80px; padding: 8px 10px; display: block;
      border: 1px solid var(--border); border-radius: 6px;
      background: var(--surface-2); color: var(--text);
      font-size: 13px; font-family: system-ui,-apple-system,sans-serif;
      resize: vertical; outline: none;
    }
    #memo-textarea:focus { border-color: var(--accent); }
    .memo-modal-actions {
      display: flex; gap: 8px; margin-top: 10px; justify-content: flex-end;
    }
    #connect-mode-hint {
      display: none; position: fixed; top: 65px; left: 50%;
      transform: translateX(-50%); z-index: 1500; pointer-events: none;
      background: var(--connect-hint-bg); color: var(--connect-hint-text); padding: 6px 18px;
      border-radius: 6px; font-size: 12px; font-weight: 500;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    /* ---- IO stat bar (above graph) ---- */
    #io-stat-bar {
      display: flex; gap: 8px; padding: 6px 16px;
      background: var(--surface); border-bottom: 1px solid var(--border-subtle);
      flex-shrink: 0;
    }
    .io-stat-btn {
      display: flex; align-items: center; gap: 5px;
      padding: 3px 12px; border-radius: 12px; cursor: pointer;
      font-size: 11px; font-weight: 600; border: 1px solid;
      transition: opacity 0.15s; font: inherit;
    }
    .io-stat-btn:hover { opacity: 0.75; }
    .io-stat-btn.io-stat-active { outline: 2px solid currentColor; outline-offset: 1px; }
    .io-stat-input  { color: var(--badge-input-text);     border-color: var(--badge-input-border);     background: var(--badge-input-bg); }
    .io-stat-output { color: var(--badge-output-text);    border-color: var(--badge-output-border);    background: var(--badge-output-bg); }
    .io-stat-join   { color: var(--badge-join-text);      border-color: var(--badge-join-border);      background: var(--badge-join-bg); }
    .io-stat-count  { font-size: 12px; font-weight: 700; }
    /* ---- Left panels (summary + insights + search-results) ---- */
    #summary-panel, #insights-panel, #search-results-panel {
      position: fixed;
      top: 0; left: 0;
      width: 640px; height: 100%;
      background: var(--surface);
      border-right: 1px solid var(--border);
      box-shadow: 2px 0 12px rgba(0,0,0,0.2);
      display: flex; flex-direction: column;
      overflow: hidden;
      transform: translateX(-100%);
      transition: transform 0.2s ease;
      z-index: 1000;
      border-radius: 0 8px 8px 0;
    }
    #summary-panel.open, #insights-panel.open, #search-results-panel.open { transform: translateX(0); }
    #summary-panel-drag-handle, #insights-panel-drag-handle, #search-results-panel-drag-handle {
      position: absolute;
      top: 0; right: 0;
      width: 6px; height: 100%;
      cursor: col-resize;
      z-index: 10;
      user-select: none;
    }
    #summary-panel-drag-handle:hover, #summary-panel-drag-handle.dragging,
    #insights-panel-drag-handle:hover, #insights-panel-drag-handle.dragging,
    #search-results-panel-drag-handle:hover, #search-results-panel-drag-handle.dragging {
      background: rgba(148,163,184,0.18);
    }
    #summary-panel-header, #insights-panel-header, #search-results-panel-header {
      padding: 12px 16px 10px;
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between;
    }
    #insights-panel-header span, #summary-panel-title, #search-results-panel-title { font-size: 14px; font-weight: 600; color: var(--text); }
    .panel-header-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
    .panel-copy-btn {
      cursor: pointer; font-size: 11px; color: var(--text-muted);
      background: none; border: 1px solid var(--border);
      border-radius: 3px; padding: 1px 7px; line-height: 1.5;
    }
    .panel-copy-btn:hover { color: var(--text); border-color: var(--text-muted); }
    #excel-dl-btn {
      cursor: pointer; font-size: 11px; color: var(--text-muted);
      background: none; border: 1px solid var(--border);
      border-radius: 3px; padding: 1px 7px; line-height: 1.5;
    }
    #excel-dl-btn:hover { color: var(--text); border-color: var(--text-muted); }
    #summary-panel-body { padding: 10px 12px; flex: 1; overflow-y: auto; direction: rtl; min-height: 0; }
    #summary-panel-body > * { direction: ltr; }
    #insights-panel-body { padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; flex: 1; overflow-y: auto; direction: rtl; min-height: 0; }
    #insights-panel-body > * { direction: ltr; }
    #search-results-panel-body { padding: 10px 12px; flex: 1; overflow-y: auto; direction: rtl; min-height: 0; }
    #search-results-panel-body > * { direction: ltr; }
    /* ---- Containers panel ---- */
    #containers-panel {
      position: fixed; top: 0; left: 0;
      width: 360px; height: 100%;
      background: var(--surface);
      border-right: 1px solid var(--border);
      box-shadow: 2px 0 12px rgba(0,0,0,0.2);
      display: flex; flex-direction: column;
      overflow: hidden;
      transform: translateX(-100%);
      transition: transform 0.2s ease;
      z-index: 1000;
      border-radius: 0 8px 8px 0;
    }
    #containers-panel.open { transform: translateX(0); }
    #containers-panel-drag-handle {
      position: absolute; top: 0; right: 0;
      width: 6px; height: 100%;
      cursor: col-resize; z-index: 10; user-select: none;
    }
    #containers-panel-drag-handle:hover, #containers-panel-drag-handle.dragging {
      background: rgba(148,163,184,0.18);
    }
    #containers-panel-header {
      padding: 12px 16px 10px;
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between;
    }
    #containers-panel-title { font-size: 14px; font-weight: 600; color: var(--text); }
    #containers-panel-body { padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; flex: 1; overflow-y: auto; direction: rtl; min-height: 0; }
    #containers-panel-body > * { direction: ltr; }
    .container-row { display: flex; align-items: center; gap: 8px; cursor: grab; border-radius: 4px; padding: 5px 8px; flex-wrap: wrap; }
    .container-row:hover { background: rgba(148,163,184,0.12); }
    .container-row.focused { background: rgba(245,158,11,0.18); outline: 1px solid #f59e0b; }
    .container-members { font-size: 11px; color: var(--text-muted); width: 100%; padding-left: 2px; }
    .container-row.drag-over-top { border-top: 2px solid #f59e0b; }
    .container-row.drag-over-bottom { border-bottom: 2px solid #f59e0b; }
    .container-row.dragging { opacity: 0.4; }
    .container-swatch { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; border: 1px solid rgba(0,0,0,0.25); }
    .container-label { font-size: 12px; color: var(--text); }
    .ki-summary { font-size: 11px; color: var(--text-muted); padding: 2px 0 8px;
      border-bottom: 1px solid var(--border); margin-bottom: 4px; }
    .ki-row { display: flex; align-items: baseline; gap: 6px; cursor: pointer; border-radius: 4px; padding: 1px 2px; }
    .ki-row:hover { background: rgba(148,163,184,0.12); }
    .ki-row.focused { background: rgba(245,158,11,0.18); outline: 1px solid #f59e0b; }
    .step-badge { cursor: pointer; }
    .step-badge:hover { filter: brightness(0.88); }
    .step-badge.focused { background: #92400e !important; border-color: #f59e0b !important; color: #fef3c7 !important; box-shadow: 0 0 0 2px rgba(245,158,11,0.5); }
    .ki-badge { font-size: 10px; font-weight: 700; border-radius: 3px;
      padding: 1px 5px; flex-shrink: 0; text-transform: uppercase; letter-spacing: 0.03em; }
    .ki-badge-input    { background: var(--badge-input-bg);     color: var(--badge-input-text);     border: 1px solid var(--badge-input-border); }
    .ki-badge-output   { background: var(--badge-output-bg);    color: var(--badge-output-text);    border: 1px solid var(--badge-output-border); }
    .ki-badge-join     { background: var(--badge-join-bg);      color: var(--badge-join-text);      border: 1px solid var(--badge-join-border); }
    .ki-badge-union    { background: var(--badge-union-bg);     color: var(--badge-union-text);     border: 1px solid var(--badge-union-border); }
    .ki-badge-aggregate{ background: var(--badge-aggregate-bg); color: var(--badge-aggregate-text); border: 1px solid var(--badge-aggregate-border); }
    .ki-badge-filter   { background: var(--badge-filter-bg);    color: var(--badge-filter-text);    border: 1px solid var(--badge-filter-border); }
    .ki-badge-formula  { background: var(--badge-formula-bg);   color: var(--badge-formula-text);   border: 1px solid var(--badge-formula-border); }
    .ki-badge-reshape  { background: var(--badge-reshape-bg);   color: var(--badge-reshape-text);   border: 1px solid var(--badge-reshape-border); }
    .ki-desc { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 11px; color: var(--text); white-space: nowrap; }
    .ki-id { font-size: 10px; color: var(--text-muted); font-variant-numeric: tabular-nums; flex-shrink: 0; min-width: 28px; }
    .summary-steps { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
    .summary-step { display: flex; flex-direction: column; border-radius: 6px; cursor: pointer; }
    .summary-step:hover { filter: brightness(1.08); }
    .summary-step-input  { background: var(--accent-conn-bg); }
    .summary-step-output { background: var(--accent-added-bg); }
    .summary-step-transform { background: var(--surface-2); }
    .summary-step-unknown { background: var(--surface-2); opacity: 0.7; }
    .summary-step-added    { outline: 1px solid var(--accent-added-border); }
    .summary-step-modified { outline: 1px solid var(--accent-modified-border); }
    .step-row { display: flex; align-items: baseline; gap: 8px; padding: 5px 8px; }
    .step-num { font-size: 11px; color: var(--text-muted); min-width: 22px; text-align: right; flex-shrink: 0; }
    .step-badge { font-size: 11px; font-weight: 600; border-radius: 4px; padding: 1px 7px; border: 1px solid; flex-shrink: 0; }
    .step-badge-input    { color: var(--accent-conn);     background: var(--accent-conn-bg);     border-color: var(--accent-conn-border); }
    .step-badge-output   { color: var(--accent-added);    background: var(--accent-added-bg);    border-color: var(--accent-added-border); }
    .step-badge-transform { color: var(--accent-modified); background: var(--accent-modified-bg); border-color: var(--accent-modified-border); }
    .step-badge-unknown  { color: var(--text-muted);      background: var(--surface-2);          border-color: var(--border); }
    .step-desc { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; color: var(--text-muted); word-break: break-all; }
    .step-expand-arrow { font-size: 10px; color: var(--text-muted); margin-left: auto; flex-shrink: 0; transition: transform 0.15s ease; }
    .search-mark { background: rgba(245,158,11,0.35); color: inherit; border-radius: 2px; padding: 0 1px; }
    .step-expand-arrow.open { transform: rotate(90deg); }
    .step-detail { overflow: hidden; max-height: 0; transition: max-height 0.2s ease; }
    .step-detail-inner { padding: 4px 8px 8px 30px; display: flex; flex-direction: column; gap: 3px; border-top: 1px solid var(--border-subtle); margin-top: 2px; }
    .step-config-row { display: flex; gap: 8px; align-items: baseline; }
    .step-config-key { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; flex-shrink: 0; min-width: 120px; }
    .step-config-val { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; color: var(--text); word-break: break-all; }
  </style>
</head>
<body>
  <header>
    <div>
      <div class="header-title">{{ title }}</div>
      <div class="header-meta">{{ node_count }} nodes &middot; {{ edge_count }} connections</div>
      <div class="header-hints">
        <span class="hint-item">&#128203; 空白をダブルクリック &rarr; メモ追加</span>
        <span class="hint-sep">&middot;</span>
        <span class="hint-item">&#128308; 赤いクラスタをダブルクリック &rarr; 展開</span>
        <span class="hint-sep">&middot;</span>
        <span class="hint-item">&#128203; メモをダブルクリック &rarr; 編集</span>
      </div>
    </div>
    <div class="header-right">
      {% if workflow_steps %}<button class="ctrl-btn" id="excel-dl-btn" onclick="downloadSummaryExcel()">&#8595; Excel</button>{% endif %}
      <div class="search-wrap">
        <input type="text" id="search-input" class="search-input" placeholder="Search node…" autocomplete="off" spellcheck="false" />
        <button class="search-clear" id="search-clear-btn" aria-label="Clear">&times;</button>
      </div>
      {% if containers_for_panel %}<button class="ctrl-btn" id="containers-btn" onclick="openContainersPanel()">Containers</button>{% endif %}
      {% if key_insights %}<button class="ctrl-btn" id="insights-btn" onclick="openInsightsPanel()">At a Glance</button>{% endif %}
      {% if workflow_steps %}<button class="ctrl-btn" id="summary-btn" onclick="openSummaryPanel()">Summary</button>{% endif %}
      <button class="ctrl-btn" id="add-memo-btn">+ Memo</button>
      <button class="ctrl-btn" id="fit-btn">Fit to Screen</button>
      <button class="ctrl-btn" id="fullscreen-btn">Fullscreen</button>
      <button class="ctrl-btn" id="theme-btn">Light Mode</button>
    </div>
  </header>
  {% if key_insights %}
  {% set _input_count = key_insights | selectattr('role', 'equalto', 'input') | list | length %}
  {% set _output_count = key_insights | selectattr('role', 'equalto', 'output') | list | length %}
  {% set _join_count = key_insights | selectattr('role', 'equalto', 'join') | list | length %}
  {% if _input_count or _output_count or _join_count %}
  <div id="io-stat-bar">
    {% if _input_count %}<button class="io-stat-btn io-stat-input" onclick="openInsightsPanelFiltered('input')">Input <span class="io-stat-count">{{ _input_count }}</span></button>{% endif %}
    {% if _output_count %}<button class="io-stat-btn io-stat-output" onclick="openInsightsPanelFiltered('output')">Output <span class="io-stat-count">{{ _output_count }}</span></button>{% endif %}
    {% if _join_count %}<button class="io-stat-btn io-stat-join" onclick="openInsightsPanelFiltered('join')">Join <span class="io-stat-count">{{ _join_count }}</span></button>{% endif %}
  </div>
  {% endif %}
  {% endif %}
  <div id="graph-wrapper">
    <div id="graph-canvas"></div>
    <div id="minimap-wrap">
      <div id="minimap-resize-handle"></div>
      <canvas id="minimap-canvas" width="240" height="160"></canvas>
      <button id="minimap-close" title="Hide minimap" onclick="closeMinimapPanel()">&times;</button>
    </div>
  </div>
  <button id="minimap-reopen" title="Show minimap" onclick="openMinimapPanel()">&#9638; Map</button>
  {% if key_insights %}
  <div id="insights-panel">
    <div id="insights-panel-drag-handle"></div>
    <div id="insights-panel-header">
      <span id="insights-panel-title">At a Glance</span>
      <div class="panel-header-actions">
        <button class="panel-copy-btn" id="insights-copy-btn" onclick="copyInsightsPanel()">Copy</button>
        <button class="panel-close" onclick="closeInsightsPanel()">&times;</button>
      </div>
    </div>
    <div id="insights-panel-body">
      {% for insight in key_insights %}
      {% if insight.role == "summary" %}
      <div class="ki-summary">{{ insight.description }}</div>
      {% else %}
      <div class="ki-row" data-role="{{ insight.role }}" onclick="focusNode({{ insight.tool_id }}, this)">
        <span class="ki-id">#{{ insight.tool_id }}</span>
        <span class="ki-badge ki-badge-{{ insight.role }}">{{ insight.short_type }}</span>
        <span class="ki-desc">{{ insight.description or insight.short_type }}</span>
      </div>
      {% endif %}
      {% endfor %}
    </div>
  </div>
  {% endif %}
  {% if containers_for_panel %}
  <div id="containers-panel">
    <div id="containers-panel-drag-handle"></div>
    <div id="containers-panel-header">
      <span id="containers-panel-title">Containers ({{ containers_for_panel | length }})</span>
      <div class="panel-header-actions">
        <button class="panel-copy-btn" id="containers-copy-btn" onclick="copyContainersPanel()">Copy</button>
      </div>
    </div>
    <div id="containers-panel-body">
      {% for c in containers_for_panel %}
      <div class="container-row" draggable="true" data-label="{{ c.label }}" data-container-idx="{{ loop.index0 }}" onclick="focusContainer({{ loop.index0 }}, this)">
        {% if c.fill_color %}<span class="container-swatch" style="background:{{ c.fill_color }};"></span>{% endif %}
        {% if c.tool_id %}<span class="ki-id">#{{ c.tool_id }}</span>{% endif %}
        <span class="container-label">{{ c.label }}</span>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endif %}
  {% if workflow_steps %}
  <div id="summary-panel">
    <div id="summary-panel-drag-handle"></div>
    <div id="summary-panel-header">
      <span id="summary-panel-title">Workflow Steps ({{ workflow_steps | length }})</span>
      <div class="panel-header-actions">
        <button class="panel-copy-btn" id="summary-copy-btn" onclick="copySummaryPanel()">Copy</button>
        <button class="panel-close" onclick="closeSummaryPanel()">&times;</button>
      </div>
    </div>
    <div id="summary-panel-body">
      <ol class="summary-steps">
        {% for step in workflow_steps %}
        <li class="summary-step summary-step-{{ step.category }}{% if step.change %} summary-step-{{ step.change }}{% endif %}"
            onclick="toggleStepDetail(this)">
          <div class="step-row">
            <span class="step-num">{{ loop.index }}.</span>
            <span class="ki-id">#{{ step.tool_id }}</span>
            <span class="step-badge step-badge-{{ step.category }}" onclick="event.stopPropagation(); focusNode({{ step.tool_id }}, this)">{{ step.short_type }}</span>
            {% if step.description %}<span class="step-desc">{{ step.description }}</span>{% endif %}
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
  <div id="search-results-panel">
    <div id="search-results-panel-drag-handle"></div>
    <div id="search-results-panel-header">
      <span id="search-results-panel-title">Results</span>
      <button class="panel-close" onclick="closeSearchResultsPanel()">&times;</button>
    </div>
    <div id="search-results-panel-body"></div>
  </div>
  <div id="config-panel">
    <div id="panel-drag-handle"></div>
    <div class="panel-title">
      <button class="panel-close" id="panel-close-btn">&times;</button>
      <span id="panel-title-text"></span>
    </div>
    <div id="panel-action-bar">
      <button class="panel-action-btn" id="panel-copy-id-btn">Copy ID</button>
      <button class="panel-action-btn" id="panel-copy-btn">Copy for Excel</button>
      <button class="panel-action-btn" id="panel-copy-json-btn">Copy JSON</button>
    </div>
    <div id="panel-body"></div>
  </div>
  <div id="left-panel-overlay"></div>
  <div id="panel-overlay"></div>
  <div id="memo-modal-overlay"></div>
  <div id="memo-modal">
    <div class="memo-modal-title" id="memo-modal-title">New Memo</div>
    <textarea id="memo-textarea" placeholder="Enter memo text…" rows="4"></textarea>
    <div class="memo-modal-actions">
      <button class="ctrl-btn" id="memo-delete-btn" style="display:none;color:#f87171;">Delete</button>
      <button class="ctrl-btn" id="memo-cancel-btn">Cancel</button>
      <button class="ctrl-btn" id="memo-save-btn" style="background:var(--accent);color:#fff;border-color:var(--accent);">Save</button>
    </div>
  </div>
  <div id="connect-mode-hint">Click a node to connect &mdash; Esc to cancel</div>
  <script>{{ vis_js | safe }}</script>
  <script id="yxray-data" type="application/json">{{ graph_data_json | safe }}</script>
  {% if workflow_steps %}<script id="summary-data" type="application/json">{{ workflow_steps | tojson }}</script>{% endif %}
  {% if key_insights %}<script id="insights-data" type="application/json">{{ key_insights | tojson }}</script>{% endif %}
  {% if containers_for_panel %}<script id="containers-data" type="application/json">{{ containers_for_panel | tojson }}</script>{% endif %}
  <script>{{ contrast_color_js | safe }}</script>
  <script>
{{ single_graph_js | safe }}
  </script>
  <script>
{{ step_detail_js | safe }}

// ── focusNode: highlight a graph node and the clicked panel element ────────
var _focusHighlightId = null;
var _focusHighlightOrigColor = null;
var _focusHighlightPanelEl = null;

function focusNode(toolId, clickedEl) {
    // Clear container focus state
    _focusedContainerIdx = null;
    if (_containerFocusEl) { _containerFocusEl.classList.remove('focused'); _containerFocusEl = null; }

    // Restore previous node colour
    if (_focusHighlightId !== null && nodesDataset && nodesDataset.get(_focusHighlightId) !== null) {
        var restore = _focusHighlightOrigColor !== null
            ? {id: _focusHighlightId, color: _focusHighlightOrigColor, shadow: false}
            : {id: _focusHighlightId, color: null, shadow: false};
        nodesDataset.update(restore);
    }
    _focusHighlightId = null;
    _focusHighlightOrigColor = null;

    // Remove focused class from previous panel element
    if (_focusHighlightPanelEl) {
        _focusHighlightPanelEl.classList.remove('focused');
        _focusHighlightPanelEl = null;
    }

    if (typeof network === 'undefined' || !network || toolId < 0) return;
    var visibleId = (typeof resolveNode === 'function') ? resolveNode(toolId) : toolId;
    if (visibleId === null) return;

    // If the node is inside a cluster, expand it first so the real node becomes visible.
    // After expanding, focus without animation to avoid vis.js animation/DataSet conflicts.
    var _expandedFromCluster = false;
    if (typeof visibleId === 'string' &&
        (visibleId.indexOf('cluster:') === 0 || visibleId.indexOf('container:') === 0) &&
        typeof expandCluster === 'function') {
        expandCluster(visibleId);
        visibleId = toolId;  // after expansion, the real node is now in the dataset
        _expandedFromCluster = true;
    }

    // Save original colour then apply vivid amber highlight
    var nodeData = nodesDataset ? nodesDataset.get(visibleId) : null;
    if (nodeData) {
        _focusHighlightId = visibleId;
        _focusHighlightOrigColor = nodeData.color || null;
        nodesDataset.update({
            id: visibleId,
            color: {
                background: '#92400e',
                border: '#f59e0b',
                highlight: {background: '#78350f', border: '#fbbf24'},
                hover:     {background: '#78350f', border: '#fbbf24'}
            },
            shadow: {enabled: true, color: 'rgba(245,158,11,0.55)', size: 14, x: 0, y: 0}
        });
    }

    var _focusOpts = _expandedFromCluster
        ? { scale: FOCUS_SCALE, animation: false }
        : { scale: FOCUS_SCALE, animation: { duration: 400, easingFunction: 'easeInOutQuad' } };
    network.focus(visibleId, _focusOpts);
    network.selectNodes([visibleId]);

    // Highlight the clicked panel element
    if (clickedEl) {
        clickedEl.classList.add('focused');
        _focusHighlightPanelEl = clickedEl;
    }
}

var _insightsPanelActiveRole = null;
var _searchPrevPanel = null;
var _searchResultsFocusEl = null;

function _syncPanelBtnState() {
    var ip = document.getElementById('insights-panel');
    var sp = document.getElementById('summary-panel');
    var cp = document.getElementById('containers-panel');
    var ib = document.getElementById('insights-btn');
    var sb = document.getElementById('summary-btn');
    var cb = document.getElementById('containers-btn');
    var isInsightsOpen = !!(ip && ip.classList.contains('open'));
    // "At a Glance" button is active only when the panel is open without a role filter
    if (ib) ib.classList.toggle('ctrl-btn-active', isInsightsOpen && _insightsPanelActiveRole === null);
    if (sb) sb.classList.toggle('ctrl-btn-active', !!(sp && sp.classList.contains('open')));
    if (cb) cb.classList.toggle('ctrl-btn-active', !!(cp && cp.classList.contains('open')));
    // io-stat buttons: indicate active filter state
    ['input', 'output', 'join'].forEach(function(role) {
        var btn = document.querySelector('.io-stat-' + role);
        if (btn) btn.classList.toggle('io-stat-active', isInsightsOpen && _insightsPanelActiveRole === role);
    });
    var srp = document.getElementById('search-results-panel');
    var leftOpen = isInsightsOpen || (sp && sp.classList.contains('open')) || (cp && cp.classList.contains('open')) || (srp && srp.classList.contains('open'));
    var ov = document.getElementById('left-panel-overlay');
    if (ov) ov.style.display = leftOpen ? 'block' : '';
}

function openSearchResultsPanel(entries) {
    var srp = document.getElementById('search-results-panel');
    if (!srp) return;
    if (!srp.classList.contains('open')) {
        var ip = document.getElementById('insights-panel');
        var sp = document.getElementById('summary-panel');
        var cp = document.getElementById('containers-panel');
        if (ip && ip.classList.contains('open')) _searchPrevPanel = 'insights';
        else if (sp && sp.classList.contains('open')) _searchPrevPanel = 'summary';
        else if (cp && cp.classList.contains('open')) _searchPrevPanel = 'containers';
        else _searchPrevPanel = null;
        if (ip) ip.classList.remove('open');
        if (sp) sp.classList.remove('open');
        if (cp) cp.classList.remove('open');
    }
    var body = document.getElementById('search-results-panel-body');
    body.innerHTML = '';
    var title = document.getElementById('search-results-panel-title');
    if (title) title.textContent = 'Results (' + entries.length + ')';
    var ol = document.createElement('ol');
    ol.className = 'summary-steps';
    entries.forEach(function(entry, idx) {
        var li = document.createElement('li');
        li.className = 'summary-step summary-step-' + (entry.category || 'unknown');
        li.onclick = function() { if (typeof toggleStepDetail === 'function') toggleStepDetail(this); };
        var row = document.createElement('div');
        row.className = 'step-row';
        var num = document.createElement('span');
        num.className = 'step-num';
        num.textContent = (idx + 1) + '.';
        var badge = document.createElement('span');
        badge.className = 'step-badge step-badge-' + (entry.category || 'unknown');
        badge.textContent = entry.shortType;
        badge.onclick = (function(id, badgeEl) {
            return function(e) {
                e.stopPropagation();
                if (_searchResultsFocusEl) _searchResultsFocusEl.classList.remove('focused');
                badgeEl.classList.add('focused');
                _searchResultsFocusEl = badgeEl;
                if (typeof network !== 'undefined' && network) {
                    var visId = (typeof resolveNode === 'function') ? resolveNode(id) : id;
                    if (visId !== null) {
                        network.selectNodes([visId]);
                        network.focus(visId, {scale: FOCUS_SCALE, animation: {duration: 400, easingFunction: 'easeInOutQuad'}});
                    }
                }
            };
        })(entry.id, badge);
        var desc = document.createElement('span');
        desc.className = 'step-desc';
        desc.textContent = entry.label;
        var arrow = document.createElement('span');
        arrow.className = 'step-expand-arrow';
        arrow.textContent = '▶';
        var idSpan = document.createElement('span');
        idSpan.className = 'ki-id';
        idSpan.textContent = '#' + entry.id;
        row.appendChild(num);
        row.appendChild(idSpan);
        row.appendChild(badge);
        row.appendChild(desc);
        row.appendChild(arrow);
        var detail = document.createElement('div');
        detail.className = 'step-detail';
        var configData = (typeof CONFIG_MAP !== 'undefined' && CONFIG_MAP) ? (CONFIG_MAP[String(entry.id)] || {}) : {};
        detail.dataset.config = JSON.stringify(configData);
        var inner = document.createElement('div');
        inner.className = 'step-detail-inner';
        detail.appendChild(inner);
        li.appendChild(row);
        li.appendChild(detail);
        ol.appendChild(li);
    });
    body.appendChild(ol);
    srp.classList.add('open');
    _syncPanelBtnState();
}

function closeSearchResultsPanel() {
    var srp = document.getElementById('search-results-panel');
    if (srp) srp.classList.remove('open');
    _searchResultsFocusEl = null;
    if (_searchPrevPanel === 'insights') {
        var ip = document.getElementById('insights-panel');
        if (ip) ip.classList.add('open');
    } else if (_searchPrevPanel === 'summary') {
        var sp = document.getElementById('summary-panel');
        if (sp) sp.classList.add('open');
    } else if (_searchPrevPanel === 'containers') {
        var cp = document.getElementById('containers-panel');
        if (cp) cp.classList.add('open');
    }
    _searchPrevPanel = null;
    _syncPanelBtnState();
}

function openInsightsPanel() {
    var ip = document.getElementById('insights-panel');
    var sp = document.getElementById('summary-panel');
    var cp = document.getElementById('containers-panel');
    if (!ip) return;
    if (ip.classList.contains('open') && _insightsPanelActiveRole === null) { ip.classList.remove('open'); _syncPanelBtnState(); return; }
    if (sp) sp.classList.remove('open');
    if (cp) cp.classList.remove('open');
    _insightsPanelActiveRole = null;
    // Reset filter — show all rows
    var titleEl = document.getElementById('insights-panel-title');
    if (titleEl) titleEl.textContent = 'At a Glance';
    ip.querySelectorAll('.ki-row').forEach(function(row) { row.style.display = ''; });
    var summary = ip.querySelector('.ki-summary');
    if (summary) summary.style.display = '';
    ip.classList.add('open');
    _syncPanelBtnState();
}
function openInsightsPanelFiltered(role) {
    var ip = document.getElementById('insights-panel');
    var sp = document.getElementById('summary-panel');
    var cp = document.getElementById('containers-panel');
    if (!ip) return;
    if (ip.classList.contains('open') && _insightsPanelActiveRole === role) {
        ip.classList.remove('open');
        _insightsPanelActiveRole = null;
        _syncPanelBtnState();
        return;
    }
    if (sp) sp.classList.remove('open');
    if (cp) cp.classList.remove('open');
    _insightsPanelActiveRole = role;
    // Filter rows to matching role
    var titleEl = document.getElementById('insights-panel-title');
    if (titleEl) titleEl.textContent = role.charAt(0).toUpperCase() + role.slice(1) + 's';
    ip.querySelectorAll('.ki-row').forEach(function(row) {
        row.style.display = (row.dataset.role === role) ? '' : 'none';
    });
    var summary = ip.querySelector('.ki-summary');
    if (summary) summary.style.display = 'none';
    ip.classList.add('open');
    _syncPanelBtnState();
}
function closeInsightsPanel() {
    var ip = document.getElementById('insights-panel');
    if (ip) { ip.classList.remove('open'); _insightsPanelActiveRole = null; }
    _syncPanelBtnState();
}
function openSummaryPanel() {
    var sp = document.getElementById('summary-panel');
    var ip = document.getElementById('insights-panel');
    var cp = document.getElementById('containers-panel');
    if (!sp) return;
    if (sp.classList.contains('open')) { sp.classList.remove('open'); _syncPanelBtnState(); return; }
    if (ip) { ip.classList.remove('open'); _insightsPanelActiveRole = null; }
    if (cp) cp.classList.remove('open');
    sp.classList.add('open');
    _syncPanelBtnState();
}
function closeSummaryPanel() {
    var sp = document.getElementById('summary-panel');
    if (sp) sp.classList.remove('open');
    _syncPanelBtnState();
}
function openContainersPanel() {
    var cp = document.getElementById('containers-panel');
    var ip = document.getElementById('insights-panel');
    var sp = document.getElementById('summary-panel');
    if (!cp) return;
    if (cp.classList.contains('open')) { cp.classList.remove('open'); _syncPanelBtnState(); return; }
    if (ip) { ip.classList.remove('open'); _insightsPanelActiveRole = null; }
    if (sp) sp.classList.remove('open');
    cp.classList.add('open');
    _syncPanelBtnState();
}
var _containerFocusEl = null;
function focusContainer(containerIdx, clickedEl) {
    // Clear node focus state
    if (_focusHighlightId !== null && nodesDataset && nodesDataset.get(_focusHighlightId) !== null) {
        var restoreColor = _focusHighlightOrigColor !== null
            ? {id: _focusHighlightId, color: _focusHighlightOrigColor, shadow: false}
            : {id: _focusHighlightId, color: null, shadow: false};
        nodesDataset.update(restoreColor);
    }
    _focusHighlightId = null;
    _focusHighlightOrigColor = null;
    if (_focusHighlightPanelEl) { _focusHighlightPanelEl.classList.remove('focused'); _focusHighlightPanelEl = null; }

    if (_containerFocusEl) { _containerFocusEl.classList.remove('focused'); _containerFocusEl = null; }
    if (clickedEl) { clickedEl.classList.add('focused'); _containerFocusEl = clickedEl; }
    // Update graph highlight and redraw.
    _focusedContainerIdx = containerIdx;
    if (!network) return;
    network.redraw();
    // Compute bounding box of container members in vis-network canvas coords.
    var membership = computeContainerMembership();
    var memberIds = [];
    Object.keys(membership).forEach(function(nid) {
        if (membership[parseInt(nid)] === containerIdx) {
            var rep = resolveNode(parseInt(nid));
            if (rep !== null && memberIds.indexOf(rep) === -1) memberIds.push(rep);
        }
    });
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    if (memberIds.length > 0) {
        var positions = network.getPositions(memberIds);
        memberIds.forEach(function(id) {
            var pos = positions[id];
            if (pos) {
                minX = Math.min(minX, pos.x); minY = Math.min(minY, pos.y);
                maxX = Math.max(maxX, pos.x); maxY = Math.max(maxY, pos.y);
            }
        });
    }
    if (!isFinite(minX)) {
        var c = CONTAINERS_DATA[containerIdx];
        if (!c) return;
        minX = c.x; minY = c.y; maxX = c.x + (c.w || 0); maxY = c.y + (c.h || 0);
    }
    // Add container padding to match the drawn box.
    minX -= CONT_PAD_X; minY -= CONT_PAD_Y;
    maxX += CONT_PAD_X; maxY += CONT_PAD_Y;
    var boxW = maxX - minX;
    var boxH = maxY - minY;
    var canvas = network.canvas.frame.canvas;
    var scale = Math.min(Math.min(canvas.clientWidth / boxW, canvas.clientHeight / boxH) * 0.6, 0.9);
    var center = {x: (minX + maxX) / 2, y: (minY + maxY) / 2};
    network.moveTo({position: center, scale: scale, animation: {duration: 400, easingFunction: 'easeInOutQuad'}});
}

// ── Panel drag-resize (shared helper) ────────────────────────────────────
// direction: +1 = handle on right edge (drag right to widen),
//            -1 = handle on left edge  (drag left to widen, e.g. config-panel)
function makeDragResize(panelId, handleId, direction) {
  var panel  = document.getElementById(panelId);
  var handle = document.getElementById(handleId);
  if (!handle || !panel) return;
  var startX, startW;
  handle.addEventListener('mousedown', function(e) {
    e.preventDefault();
    e.stopPropagation();
    startX = e.clientX;
    startW = panel.offsetWidth;
    handle.classList.add('dragging');
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
  function onMove(e) {
    var dx  = (e.clientX - startX) * direction;
    var newW = Math.max(220, Math.min(Math.floor(window.innerWidth * 0.85), startW + dx));
    panel.style.width = newW + 'px';
  }
  function onUp() {
    handle.classList.remove('dragging');
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  }
}
(function() {
    var ov = document.getElementById('left-panel-overlay');
    if (!ov) return;
    ov.addEventListener('click', function() {
        ['insights-panel', 'summary-panel', 'containers-panel', 'search-results-panel'].forEach(function(id) {
            var el = document.getElementById(id);
            if (el) el.classList.remove('open');
        });
        if (typeof _insightsPanelActiveRole !== 'undefined') _insightsPanelActiveRole = null;
        if (typeof _searchPrevPanel !== 'undefined') _searchPrevPanel = null;
        if (typeof _searchResultsFocusEl !== 'undefined') _searchResultsFocusEl = null;
        _syncPanelBtnState();
    });
})();
makeDragResize('config-panel',          'panel-drag-handle',                -1);
makeDragResize('insights-panel',        'insights-panel-drag-handle',       +1);
makeDragResize('summary-panel',         'summary-panel-drag-handle',        +1);
makeDragResize('containers-panel',      'containers-panel-drag-handle',     +1);
makeDragResize('search-results-panel',  'search-results-panel-drag-handle', +1);
  </script>
</body>
</html>
"""


class SingleGraphRenderer:
    """Render a single WorkflowDoc as a standalone vis-network HTML file.

    Returns a full HTML document (not a fragment).
    vis-network UMD is inlined — zero CDN references.
    """

    def render(
        self,
        doc: WorkflowDoc,
        *,
        workflow_steps: list[Any] | None = None,
        key_insights: list[Any] | None = None,
    ) -> str:
        """WorkflowDoc → standalone HTML string.

        Args:
            doc: The parsed workflow document.
            workflow_steps: Optional list of WorkflowStep objects. When provided,
                a collapsible Summary panel is shown.
            key_insights: Optional list of KeyInsight objects shown as an
                at-a-glance summary at the top of the Summary panel.
        """
        nodes_list, edges_list, config_map, containers_list = self._build_graph_data(
            doc
        )
        vis_js = load_vis_js()
        single_graph_js = _load_single_graph_js()
        title = pathlib.Path(doc.filepath).name

        steps_dicts: list[Any] | None = None
        if workflow_steps:
            steps_dicts = [
                s.to_dict(include_change=False) if hasattr(s, "to_dict") else s
                for s in workflow_steps
            ]

        # Sort containers by canvas position (x, y) to match the left-to-right visual flow.
        if containers_list:
            containers_list = sorted(containers_list, key=lambda c: (c["x"], c["y"]))

        insights_dicts: list[Any] | None = None
        if key_insights:
            insights_dicts = [
                i.to_dict() if hasattr(i, "to_dict") else i for i in key_insights
            ]

        graph_data_json = _safe_json(
            {
                "nodes": nodes_list,
                "edges": edges_list,
                "config_map": config_map,
                "containers": containers_list,
                "node_layer": compute_node_layer(doc),
            },
            ensure_ascii=False,
        )

        env = Environment(autoescape=True)  # noqa: S701
        env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}
        template = env.from_string(_HTML_TEMPLATE)
        data_node_count = sum(
            1 for n in doc.nodes if "ToolContainer" not in n.tool_type
        )
        containers_for_panel = [
            {"label": c["label"], "fill_color": c.get("fillColor"), "tool_id": c.get("tool_id")}
            for c in containers_list
        ] or None

        return template.render(
            title=title,
            node_count=data_node_count,
            edge_count=len(doc.connections),
            graph_data_json=graph_data_json,
            vis_js=vis_js,
            single_graph_js=single_graph_js,
            step_detail_js=STEP_DETAIL_JS,
            contrast_color_js=CONTRAST_COLOR_JS,
            workflow_steps=steps_dicts,
            key_insights=insights_dicts,
            containers_for_panel=containers_for_panel,
        )

    def _build_graph_data(
        self, doc: WorkflowDoc
    ) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]
    ]:
        data_nodes = [n for n in doc.nodes if "ToolContainer" not in n.tool_type]
        data_node_ids = {int(n.tool_id) for n in data_nodes}

        nodes_json: list[dict[str, Any]] = [
            self._vis_node(int(node.tool_id), node) for node in data_nodes
        ]

        edges_json: list[dict[str, Any]] = [
            {"id": i, "from": int(c.src_tool), "to": int(c.dst_tool)}
            for i, c in enumerate(doc.connections)
            if int(c.src_tool) in data_node_ids and int(c.dst_tool) in data_node_ids
        ]

        config_map: dict[str, Any] = {
            str(int(node.tool_id)): {
                "label": f"{node.tool_type.split('.')[-1]} (ID: {int(node.tool_id)})",
                "tool_type": node.tool_type.split(".")[-1],
                "config": self._clean_config(node),
            }
            for node in data_nodes
        }

        containers_json: list[dict[str, Any]] = [
            {
                "x": node.x,
                "y": node.y,
                "w": node.width,
                "h": node.height,
                "label": self._container_label(node),
                "fillColor": self._container_fill_color(node),
                "tool_id": int(node.tool_id),
            }
            for node in doc.nodes
            if "ToolContainer" in node.tool_type and node.width > 0 and node.height > 0
        ]

        return nodes_json, edges_json, config_map, containers_json

    def _container_fill_color(self, node: AlteryxNode) -> str | None:
        """Return '#rrggbb' extracted from container config, or None if absent/white.

        Alteryx stores container color inside the <Style> element's attributes:
          <Style FillColor="xxx" TextColor="xxx" BorderColor="xxx" .../>
        parsed as config["Style"]["@FillColor"].
        Value may be hex (#RRGGBB, AARRGGBB) or a decimal ARGB integer.

        Fallback: <Tint> (Qt ARGB32 int), <FillColor> hex string.
        """
        config = node.config

        def _hex_or_int_to_rgb(raw: str) -> str | None:
            raw = raw.strip().lstrip("#")
            if not raw:
                return None
            # 8-char hex AARRGGBB → take RGB part
            if len(raw) == 8 and all(c in "0123456789abcdefABCDEF" for c in raw):
                return f"#{raw[2:8].lower()}"
            # 6-char hex RRGGBB
            if len(raw) == 6 and all(c in "0123456789abcdefABCDEF" for c in raw):
                return f"#{raw.lower()}"
            # Decimal integer → ARGB32
            try:
                val = int(raw)
                if val > 0:
                    r = (val >> 16) & 0xFF
                    g = (val >> 8) & 0xFF
                    b = val & 0xFF
                    return f"#{r:02x}{g:02x}{b:02x}"
            except ValueError:
                pass
            return None

        # Primary: Style/@FillColor attribute
        style_entry = config.get("Style")
        if isinstance(style_entry, dict):
            fill_attr = style_entry.get("@FillColor", "")
            if fill_attr:
                result = _hex_or_int_to_rgb(fill_attr)
                if result:
                    return result
            # Fallback: Style as plain integer index (old format)
            text = style_entry.get("#text", "").strip()
            try:
                style_int = int(text)
                if style_int > 9:
                    return _hex_or_int_to_rgb(text)
                _STYLE_COLORS: dict[int, str] = {
                    1: "#dbeafe",
                    2: "#dcfce7",
                    3: "#fef9c3",
                    4: "#ffedd5",
                    5: "#fce7f3",
                    6: "#ede9fe",
                    7: "#d1fae5",
                    8: "#e0f2fe",
                    9: "#fee2e2",
                }
                return _STYLE_COLORS.get(style_int)
            except ValueError:
                pass

        # Tint: Qt ARGB32 packed integer
        tint_entry = config.get("Tint")
        if tint_entry:
            raw = (
                tint_entry.get("#text", "")
                if isinstance(tint_entry, dict)
                else str(tint_entry)
            )
            result = _hex_or_int_to_rgb(raw)
            if result:
                return result

        # FillColor: top-level hex string (some versions)
        fill_entry = config.get("FillColor") or config.get("fillColor")
        if fill_entry:
            raw = (
                fill_entry.get("#text", "")
                if isinstance(fill_entry, dict)
                else str(fill_entry)
            )
            result = _hex_or_int_to_rgb(raw)
            if result:
                return result

        return None

    def _container_label(self, node: AlteryxNode) -> str:
        caption_entry = node.config.get("Caption", {})
        if isinstance(caption_entry, dict):
            text = caption_entry.get("#text", "")
        else:
            text = str(caption_entry) if caption_entry else ""
        return text or f"Container ({int(node.tool_id)})"

    def _vis_node(self, node_id: int, node: AlteryxNode) -> dict[str, Any]:
        short_type = node.tool_type.split(".")[-1]
        result: dict[str, Any] = {
            "id": node_id,
            "label": f"{short_type}\n({node_id})",
            "title": node.tool_type,
            "containerId": node.container_id,
            "x": node.x,
            "y": node.y,
        }
        subtitle = self._node_subtitle(node)
        if subtitle:
            result["subtitle"] = subtitle
        return result

    def _node_subtitle(self, node: AlteryxNode) -> str | None:
        """Return the File path from config for input/output nodes, else None."""
        file_entry = node.config.get("File")
        if file_entry is None:
            return None
        raw = (
            file_entry.get("#text", "")
            if isinstance(file_entry, dict)
            else str(file_entry)
        )
        return raw.strip() or None

    def _clean_config(self, node: AlteryxNode) -> dict[str, Any]:
        """Return config dict excluding XML attribute keys (@ prefix)."""
        return {k: v for k, v in node.config.items() if not k.startswith("@")}
