/**
 * Configuração Global da API
 *
 * Define a URL base para todas as chamadas ao backend.
 * Tenta ler do localStorage primeiro (para desenvolvimento flexível),
 * caso contrário usa o padrão localhost:5000.
 */
window.VIGILACORE_API_BASE = (function() {
    const saved = (localStorage.getItem('vigilacore_api_base') || '').trim();
    return saved || 'http://127.0.0.1:5000';
})();

/**
 * Função Wrapper para Fetch com Autenticação (JWT)
 *
 * Adiciona automaticamente o cabeçalho 'Authorization: Bearer <token>'
 * e resolve a URL relativa usando VIGILACORE_API_BASE.
 *
 * @param {string} url - Caminho relativo (ex: '/api/dados') ou URL absoluta.
 * @param {object} options - Opções padrão da API Fetch (method, body, etc.).
 * @returns {Promise<Response>} - A promessa da resposta Fetch.
 */
window.authFetch = function(url, options = {}) {
    const token = localStorage.getItem('vigilacore_token');
    options.headers = options.headers || {};

    if (token) {
        options.headers['Authorization'] = 'Bearer ' + token;
    }

    const isAbsolute = /^https?:\/\//i.test(url);
    let finalUrl = url;

    if (!isAbsolute) {
        // Garante que não haja barras duplas na junção
        const path = url.startsWith('/') ? url : ('/' + url);
        finalUrl = window.VIGILACORE_API_BASE.replace(/\/$/, '') + path;
    }

    return fetch(finalUrl, options);
};

/**
 * Função de Ping (Healthcheck)
 *
 * Verifica se o backend está online. Não usa cache para garantir status real.
 * @param {string} path - Caminho do endpoint de ping (padrão: '/api/ping').
 */
window.pingFetch = function(path = '/api/ping') {
    const base = window.VIGILACORE_API_BASE.replace(/\/$/, '');
    const p = path.startsWith('/') ? path : ('/' + path);
    return fetch(base + p, { method: 'GET', cache: 'no-store' });
};

// Contador de falhas consecutivas de ping para evitar "piscar" o status
window.__vc_ping_failures = 0;

/**
 * Atualiza o Indicador de Status do Sistema (Online/Offline)
 *
 * Altera o texto e a classe CSS do elemento de status (pill).
 * Só marca como OFFLINE após 2 falhas consecutivas.
 *
 * @param {string} pillId - ID do elemento HTML que exibe o status.
 */
window.updateConnectionPill = async function(pillId = 'v2-conn') {
    const el = document.getElementById(pillId);
    if (!el) return;

    try {
        const res = await window.pingFetch('/api/ping');
        if (!res.ok) throw new Error('Backend inacessível');

        // Reset de falhas se sucesso
        window.__vc_ping_failures = 0;
        el.textContent = 'SISTEMA ONLINE';
        el.classList.remove('offline');
        el.classList.add('online');
    } catch (e) {
        window.__vc_ping_failures = (window.__vc_ping_failures || 0) + 1;

        // Tolerância de 1 falha antes de mostrar erro visual
        if (window.__vc_ping_failures < 2) {
            return;
        }

        el.textContent = 'SISTEMA OFFLINE';
        el.classList.remove('online');
        el.classList.add('offline');
    }
};

// Inicialização automática do monitoramento de conexão
(function(){
    function start(){
        window.updateConnectionPill();
        // Verifica a cada 15 segundos
        setInterval(() => window.updateConnectionPill(), 15000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();

/**
 * Tratamento Global de Erros de Rede e Alertas
 *
 * Substitui o window.alert padrão para suprimir erros genéricos de rede ("Failed to fetch"),
 * que são comuns quando o navegador interrompe requisições ao navegar entre páginas.
 */
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

    /**
     * Exibe um alerta de erro amigável, ignorando erros de rede irrelevantes.
     */
    window.vcShowErrorAlert = function (err, fallbackMsg) {
        const msg = (err && (err.message || err.toString())) ? String(err.message || err.toString()) : '';
        if (isNetworkMessage(msg)) {
            console.warn('[VigilaCore] Alerta de rede suprimido:', msg, err);
            return;
        }
        if (_alert) _alert('❌ ' + (msg || fallbackMsg || 'Erro ao conectar com o servidor'));
    };

    // Override do alert global
    if (_alert) {
        window.alert = function (msg) {
            if (isNetworkMessage(msg)) {
                console.warn('[VigilaCore] Alerta suprimido:', msg);
                return;
            }
            return _alert(msg);
        };
    }
})();

/**
 * Controle de Acesso e UI Baseado em Função (Role-Based Access)
 *
 * - Oculta botões de "Zerar Banco" para quem não é desenvolvedor.
 * - Restringe acesso à "Área do Usuário" para perfis que não devem vê-la.
 */
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

        // Apenas desenvolvedores veem o botão de reset global
        if (role !== 'desenvolvedor') {
            document.querySelectorAll('#v2-reset-btn').forEach((el) => {
                el.style.display = 'none';
            });
        }

        // Restrição de acesso à página de usuário (se necessário pela regra de negócio)
        // Nota: Atualmente configurado para esconder de Diretoria, Analistas e Supervisores
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
