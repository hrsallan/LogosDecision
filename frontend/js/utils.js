// Shared helper for authenticated requests.
//
// IMPORTANT:
// The frontend may be opened via file:// or a different dev server port (e.g. 5500).
// In those cases, calling fetch('/api/...') would hit the *wrong origin* and everything
// appears as OFFLINE. This helper automatically prefixes relative API URLs with the
// backend base URL.
//
// You can override the backend URL at runtime:
//   localStorage.setItem('vigilacore_api_base', 'http://127.0.0.1:5000');
//
// Default: Flask backend on 127.0.0.1:5000
window.VIGILACORE_API_BASE = (function() {
    const saved = (localStorage.getItem('vigilacore_api_base') || '').trim();
    return saved || 'http://127.0.0.1:5000';
})();

window.authFetch = function(url, options = {}) {
    const token = localStorage.getItem('vigilacore_token');
    options.headers = options.headers || {};
    if (token) {
        options.headers['Authorization'] = 'Bearer ' + token;
    }

    // Prefix only relative URLs. Keep absolute URLs untouched.
    const isAbsolute = /^https?:\/\//i.test(url);
    let finalUrl = url;
    if (!isAbsolute) {
        // Ensure we have a leading slash for path joins.
        const path = url.startsWith('/') ? url : ('/' + url);
        finalUrl = window.VIGILACORE_API_BASE.replace(/\/$/, '') + path;
    }

    return fetch(finalUrl, options);
};

// Lightweight ping that NEVER sends Authorization (avoids CORS preflight/OPTIONS).
window.pingFetch = function(path = '/api/ping') {
    const base = window.VIGILACORE_API_BASE.replace(/\/$/, '');
    const p = path.startsWith('/') ? path : ('/' + path);
    // Use no-store to avoid caching a stale offline/online state.
    return fetch(base + p, { method: 'GET', cache: 'no-store' });
};

window.__vc_ping_failures = 0;
// Update ONLINE/OFFLINE pill if present on the page.
window.updateConnectionPill = async function(pillId = 'v2-conn') {
    const el = document.getElementById(pillId);
    if (!el) return;

    try {
        const res = await window.pingFetch('/api/ping');
        if (!res.ok) throw new Error('Backend not reachable');
        window.__vc_ping_failures = 0;
        // If the request succeeded, consider the system online.
        el.textContent = 'SISTEMA ONLINE';
        el.classList.remove('offline');
        el.classList.add('online');
    } catch (e) {
        window.__vc_ping_failures = (window.__vc_ping_failures || 0) + 1;
        if (window.__vc_ping_failures < 2) {
            // evita piscar OFFLINE por falha momentânea
            return;
        }
        el.textContent = 'SISTEMA OFFLINE';
        el.classList.remove('online');
        el.classList.add('offline');
    }
};

(function(){
    function start(){
        window.updateConnectionPill();
        setInterval(() => window.updateConnectionPill(), 15000);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();

// -------------------------------------------------------
// Global alert filter + helpers
// Some browsers report network/CORS issues as: "TypeError: Failed to fetch".
// The app may still be fine (e.g., preflight/abort), but the UI would spam alerts.
// We suppress only these noisy network messages.
(function () {
    const _alert = window.alert ? window.alert.bind(window) : null;

    function isNetworkMessage(msg) {
        const s = String(msg || '');
        return /failed to fetch|networkerror|load failed|fetch api cannot load/i.test(s);
    }

    window.vcIsNetworkError = function (err) {
        const m = (err && (err.message || err.toString())) ? String(err.message || err.toString()) : '';
        return isNetworkMessage(m);
    };

    window.vcShowErrorAlert = function (err, fallbackMsg) {
        const msg = (err && (err.message || err.toString())) ? String(err.message || err.toString()) : '';
        if (isNetworkMessage(msg)) {
            console.warn('[VigilaCore] Suppressed network alert:', msg, err);
            return;
        }
        if (_alert) _alert('❌ ' + (msg || fallbackMsg || 'Erro ao conectar com o servidor'));
    };

    if (_alert) {
        window.alert = function (msg) {
            if (isNetworkMessage(msg)) {
                console.warn('[VigilaCore] Suppressed alert:', msg);
                return;
            }
            return _alert(msg);
        };
    }
})();
