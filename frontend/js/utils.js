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

// Update ONLINE/OFFLINE pill if present on the page.
window.updateConnectionPill = async function(pillId = 'v2-conn') {
    const el = document.getElementById(pillId);
    if (!el) return;

    try {
        const res = await window.authFetch('/api/ping', { method: 'GET' });
        if (!res.ok) throw new Error('Backend not reachable');
        // If the request succeeded, consider the system online.
        el.textContent = 'SISTEMA ONLINE';
        el.classList.remove('offline');
        el.classList.add('online');
    } catch (e) {
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