"""Shared JavaScript for report/graph companion-window navigation."""

COMPANION_WINDOW_JS = """\
function openCompanionFile(url) {
    var base = url.replace(/[?#].*$/, '').replace(/_(report|graph)(\\.[^./?#]+)$/, '');
    var targetName = 'yxray_companion_' + encodeURIComponent(base).replace(/[^A-Za-z0-9_]/g, '_');
    var existingOrNew = window.open(url, targetName);
    if (existingOrNew) { existingOrNew.focus(); }
}
"""
