"""Shared JavaScript for report/graph companion-window navigation."""

COMPANION_WINDOW_JS = """\
function companionWindowName(url) {
    var cleanUrl = url.replace(/[?#].*$/, '');
    var match = cleanUrl.match(/_(report|graph)(\\.[^./?#]+)$/);
    var kind = match ? match[1] : 'page';
    var base = cleanUrl.replace(/_(report|graph)(\\.[^./?#]+)$/, '');
    return 'yxray_companion_' + kind + '_' +
        encodeURIComponent(base).replace(/[^A-Za-z0-9_]/g, '_');
}

window.name = companionWindowName(window.location.href);

function openCompanionFile(url) {
    var targetName = companionWindowName(url);
    var existingOrNew = window.open(url, targetName);
    if (existingOrNew) { existingOrNew.focus(); }
}
"""
