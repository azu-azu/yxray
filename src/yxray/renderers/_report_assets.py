"""Shared inline assets for standalone HTML reports."""

from __future__ import annotations

REPORT_BASE_CSS = """
:root {
  --bg: #0f172a; --surface: #1e293b; --surface-2: #131f31;
  --border: #1e3a5f; --border-subtle: #334155;
  --text: #e2e8f0; --text-muted: #64748b;
  --accent-added: #57ef92; --accent-added-bg: #052e16;
  --accent-added-border: #166534; --accent-added-text: #001a00;
  --accent-removed: #f87171; --accent-removed-bg: #2d1515;
  --accent-removed-border: #7f1d1d; --accent-removed-text: #1a0000;
  --accent-modified: #fbbf24; --accent-modified-bg: #1c1506;
  --accent-modified-border: #78350f;
  --accent-conn: #60a5fa; --accent-conn-bg: #0c1a3a;
  --accent-conn-border: #1e3a5f;
}
html.light {
  --bg: #ffffff; --surface: #f8f9fb; --surface-2: #f1f5f9;
  --border: #e2e8f0; --border-subtle: #f1f5f9;
  --text: #0f172a; --text-muted: #64748b;
  --accent-added: #16a34a; --accent-added-bg: #f0fdf4;
  --accent-added-border: #bbf7d0; --accent-added-text: #fff;
  --accent-removed: #dc2626; --accent-removed-bg: #fef2f2;
  --accent-removed-border: #fecaca; --accent-removed-text: #fff;
  --accent-modified: #d97706; --accent-modified-bg: #fffbeb;
  --accent-modified-border: #fde68a;
  --accent-conn: #2563eb; --accent-conn-bg: #eff6ff;
  --accent-conn-border: #bfdbfe;
}
*, *::before, *::after { box-sizing: border-box; }
body {
  margin: 0; padding: 0;
  background: var(--bg); color: var(--text);
  font-family:
    Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 14px; line-height: 1.5;
}
.container { max-width: 960px; margin: 0 auto; padding: 0 32px; }
.site-header {
  background: var(--bg); border-bottom: 1px solid var(--border);
  padding: 16px 0; margin-bottom: 24px;
}
.header-inner {
  max-width: 960px; margin: 0 auto; padding: 0 32px;
  display: flex; justify-content: space-between; align-items: flex-start;
}
.header-left { display: flex; flex-direction: column; gap: 4px; }
.header-title-row { display: flex; align-items: center; gap: 8px; }
.header-title { font-size: 18px; font-weight: 600; color: var(--text); margin: 0; }
.header-meta { font-size: 12px; color: var(--text-muted); margin: 0; line-height: 1.7; }
.header-meta-label {
  color: var(--text); font-weight: 600; display: inline-block; width: 3.8em;
}
.header-meta-generated { margin-top: 2px; font-size: 11px; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.pulse-dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: #57ef92; animation: pulse 2s ease-in-out infinite; flex-shrink: 0;
}
.theme-toggle {
  background: var(--surface); border: 1px solid var(--border); border-radius: 9999px;
  padding: 6px 14px; cursor: pointer; color: var(--text-muted);
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-family: inherit; transition: background 0.15s ease;
}
.theme-toggle:hover { background: var(--surface-2); }
/* ---- Workflow summary steps ---- */
.summary-steps { list-style: none; padding: 0; margin: 0 0 4px; display: flex; flex-direction: column; gap: 4px; }
.summary-step { display: flex; flex-direction: column; border-radius: 6px; cursor: pointer; }
.summary-step:hover { filter: brightness(1.08); }
.summary-step-input  { background: var(--accent-conn-bg); }
.summary-step-output { background: var(--accent-added-bg); }
.summary-step-transform { background: var(--surface); }
.summary-step-unknown { background: var(--surface); opacity: 0.7; }
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
.step-expand-arrow.open { transform: rotate(90deg); }
.step-detail { overflow: hidden; max-height: 0; transition: max-height 0.2s ease; }
.step-detail.open { max-height: none; }
.step-detail-inner { padding: 4px 8px 8px 30px; display: flex; flex-direction: column; gap: 3px; border-top: 1px solid var(--border-subtle); margin-top: 2px; }
.step-config-row { display: flex; gap: 8px; align-items: baseline; }
.step-config-key { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; flex-shrink: 0; min-width: 120px; }
.step-config-val { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; color: var(--text); word-break: break-all; }
"""

STEP_DETAIL_JS = """\
function toggleStepDetail(li) {
    var detail = li.querySelector('.step-detail');
    var arrow = li.querySelector('.step-expand-arrow');
    if (!detail) return;
    var isOpen = detail.classList.contains('open');
    if (!isOpen && detail.querySelector('.step-detail-inner').childElementCount === 0) {
        try {
            var config = JSON.parse(detail.dataset.config || '{}');
            _renderConfigRows(config, detail.querySelector('.step-detail-inner'));
        } catch (e) {
            detail.querySelector('.step-detail-inner').textContent = 'No config data.';
        }
    }
    var opening = !isOpen;
    if (opening) {
        // Measure natural height, animate to it, then remove fixed height so
        // content can reflow freely (avoids the max-height: 9999px hack).
        var inner = detail.querySelector('.step-detail-inner');
        detail.style.maxHeight = inner.scrollHeight + 'px';
    } else {
        detail.style.maxHeight = detail.scrollHeight + 'px';
        requestAnimationFrame(function() { detail.style.maxHeight = '0'; });
    }
    detail.classList.toggle('open');
    if (arrow) arrow.classList.toggle('open');
}

function _renderConfigRows(config, container) {
    if (!config || typeof config !== 'object' || Array.isArray(config)) {
        var val = document.createElement('span');
        val.className = 'step-config-val';
        val.textContent = JSON.stringify(config);
        container.appendChild(val);
        return;
    }
    var keys = Object.keys(config).filter(function(k) { return !k.startsWith('@'); });
    if (keys.length === 0) {
        var empty = document.createElement('div');
        empty.className = 'step-config-val';
        empty.style.color = 'var(--text-muted)';
        empty.textContent = '(no config)';
        container.appendChild(empty);
        return;
    }
    keys.forEach(function(k) {
        var row = document.createElement('div');
        row.className = 'step-config-row';
        var keyEl = document.createElement('span');
        keyEl.className = 'step-config-key';
        keyEl.textContent = k;
        var valEl = document.createElement('span');
        valEl.className = 'step-config-val';
        var v = config[k];
        valEl.textContent = (typeof v === 'object' && v !== null) ? JSON.stringify(v) : String(v);
        row.appendChild(keyEl);
        row.appendChild(valEl);
        container.appendChild(row);
    });
}
"""
