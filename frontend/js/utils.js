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

    const isAbsolute = /^https?:\/\//i.test(url);
    let finalUrl = url;
    if (!isAbsolute) {
        const path = url.startsWith('/') ? url : ('/' + url);
        finalUrl = window.VIGILACORE_API_BASE.replace(/\/$/, '') + path;
    }

    return fetch(finalUrl, options);
};

window.pingFetch = function(path = '/api/ping') {
    const base = window.VIGILACORE_API_BASE.replace(/\/$/, '');
    const p = path.startsWith('/') ? path : ('/' + path);
    return fetch(base + p, { method: 'GET', cache: 'no-store' });
};

window.__vc_ping_failures = 0;
window.updateConnectionPill = async function(pillId = 'v2-conn') {
    const el = document.getElementById(pillId);
    if (!el) return;

    try {
        const res = await window.pingFetch('/api/ping');
        if (!res.ok) throw new Error('Backend not reachable');
        window.__vc_ping_failures = 0;
        el.textContent = 'SISTEMA ONLINE';
        el.classList.remove('offline');
        el.classList.add('online');
    } catch (e) {
        window.__vc_ping_failures = (window.__vc_ping_failures || 0) + 1;
        if (window.__vc_ping_failures < 2) {
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

        if (role !== 'desenvolvedor') {
            document.querySelectorAll('#v2-reset-btn').forEach((el) => {
                el.style.display = 'none';
            });
        }

        if (role === 'diretoria' || role === 'analistas' || role === 'supervisor') {
            hideUserAreaNav();

            if (isOnUserPage()) {
                try {
                    alert('Acesso restrito: sua função não possui acesso à Área do Usuário.');
                } catch {}
                window.location.href = 'menu_principal.html';
            }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', apply);
    } else {
        apply();
    }
})();
