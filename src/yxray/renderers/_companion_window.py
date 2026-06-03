"""Shared JavaScript for report/graph companion-window navigation."""

COMPANION_WINDOW_JS = """\
var COMPANION_HEARTBEAT_MS = 2000;
var COMPANION_STALE_MS = 8000;

function cleanCompanionUrl(url) {
    return url.replace(/[?#].*$/, '');
}

function companionWindowName(url) {
    var cleanUrl = cleanCompanionUrl(url);
    var match = cleanUrl.match(/_(report|graph)(\\.[^./?#]+)$/);
    var kind = match ? match[1] : 'page';
    var base = cleanUrl.replace(/_(report|graph)(\\.[^./?#]+)$/, '');
    return 'yxray_companion_' + kind + '_' +
        encodeURIComponent(base).replace(/[^A-Za-z0-9_]/g, '_');
}

function companionInfo(url) {
    var cleanUrl = cleanCompanionUrl(url);
    var match = cleanUrl.match(/_(report|graph)(\\.[^./?#]+)$/);
    var kind = match ? match[1] : 'page';
    var base = cleanUrl.replace(/_(report|graph)(\\.[^./?#]+)$/, '');
    var pairKey = encodeURIComponent(base).replace(/[^A-Za-z0-9_]/g, '_');
    return {
        url: cleanUrl,
        kind: kind,
        pairKey: pairKey,
        storageKey: 'yxray_companion_' + kind + '_' + pairKey
    };
}

var COMPANION_INFO = companionInfo(window.location.href);
var COMPANION_CHANNEL = null;

window.name = companionWindowName(window.location.href);

function updateCompanionPresence() {
    try {
        localStorage.setItem(COMPANION_INFO.storageKey, JSON.stringify({
            url: COMPANION_INFO.url,
            at: Date.now()
        }));
    } catch (_e) {}
}

function removeCompanionPresence() {
    try { localStorage.removeItem(COMPANION_INFO.storageKey); } catch (_e) {}
}

function readCompanionPresence(url) {
    var info = companionInfo(url);
    try {
        var raw = localStorage.getItem(info.storageKey);
        if (!raw) return null;
        var parsed = JSON.parse(raw);
        if (!parsed || parsed.url !== info.url) return null;
        if (Date.now() - parsed.at > COMPANION_STALE_MS) return null;
        return parsed;
    } catch (_e) {
        return null;
    }
}

function focusCompanionViaBroadcast(url) {
    if (!COMPANION_CHANNEL || !readCompanionPresence(url)) return false;
    COMPANION_CHANNEL.postMessage({
        type: 'focus',
        url: cleanCompanionUrl(url)
    });
    return true;
}

updateCompanionPresence();
setInterval(updateCompanionPresence, COMPANION_HEARTBEAT_MS);
window.addEventListener('beforeunload', removeCompanionPresence);

if ('BroadcastChannel' in window) {
    COMPANION_CHANNEL = new BroadcastChannel('yxray_companion_' + COMPANION_INFO.pairKey);
    COMPANION_CHANNEL.onmessage = function(event) {
        var data = event.data || {};
        if (data.type === 'focus' && data.url === COMPANION_INFO.url) {
            window.focus();
            updateCompanionPresence();
        }
    };
}

function openCompanionFile(url) {
    if (focusCompanionViaBroadcast(url)) return;
    var targetName = companionWindowName(url);
    var existingOrNew = window.open(url, targetName);
    if (existingOrNew) { existingOrNew.focus(); }
}
"""
