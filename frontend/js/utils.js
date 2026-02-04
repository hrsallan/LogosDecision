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


// -------------------------------------------------------
// Role-based visibility (RBAC) - nav + page guard
// Regras atuais:
//   - diretoria e analistas NÃO veem a aba "Área do Usuário"
//   - gerencia vê normalmente
// Observação: isso é UI/UX. As APIs continuam protegidas no backend.
// -------------------------------------------------------
(function () {
    let __vc_me_cache = null;

    async function vcGetMe() {
        if (__vc_me_cache) return __vc_me_cache;
        const token = localStorage.getItem('vigilacore_token') || localStorage.getItem('token');
        if (!token) return null;

        try {
            const res = await window.authFetch('/api/user/me', { method: 'GET' });
            if (!res.ok) return null;
            const me = await res.json();
            __vc_me_cache = me;
            return me;
        } catch (e) {
            return null;
        }
    }

    function hideUserAreaNav() {
        // Hides both by href and by data-title for robustness.
        const selectors = [
            'a[href="usuario.html"]',
            'a[href$="/usuario.html"]',
            'a[data-title="Área do Usuário"]',
        ];
        document.querySelectorAll(selectors.join(',')).forEach((el) => {
            el.style.display = 'none';
        });
    }

    function isOnUserPage() {
        const p = (window.location.pathname || '').toLowerCase();
        const h = (window.location.href || '').toLowerCase();
        return p.endsWith('usuario.html') || h.includes('/usuario.html') || h.endsWith('usuario.html');
    }

    async function apply() {
        const me = await vcGetMe();
        if (!me || !me.role) return;

        const role = String(me.role || '').toLowerCase();

        // \"Zerar banco\" é exclusivo do cargo desenvolvedor (UI/UX)
        if (role !== 'desenvolvedor') {
            document.querySelectorAll('#v2-reset-btn').forEach((el) => {
                el.style.display = 'none';
            });
        }

        // Hide nav for diretoria and analistas
        if (role === 'diretoria' || role === 'analistas' || role === 'supervisor') {
            hideUserAreaNav();

            // Guard direct access
            if (isOnUserPage()) {
                // prefer dashboard if available; otherwise go to menu principal
                try {
                    alert('Acesso restrito: sua função não possui acesso à Área do Usuário.');
                } catch {}
                window.location.href = 'dashboard.html';
            }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', apply);
    } else {
        apply();
    }
})();
