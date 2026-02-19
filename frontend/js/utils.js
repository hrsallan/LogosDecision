/**
 * Utilitários Globais do Frontend - LOGOS DECISION
 *
 * Este arquivo contém funções compartilhadas para comunicação com a API (fetch),
 * gerenciamento de estado de conexão (online/offline), tratamento de erros
 * e controle de acesso baseado em função (RBAC) no lado do cliente.
 */

/**
 * Configuração Global da API
 *
 * Define a URL base para todas as chamadas ao backend.
 * Tenta ler do localStorage primeiro (para permitir configuração dinâmica em desenvolvimento),
 * caso contrário usa o padrão 'http://127.0.0.1:5000'.
 */
window.LOGOS_DECISION_API_BASE = (function() {
    const saved = (
        localStorage.getItem('logos_decision_api_base') ||
        localStorage.getItem('vigilacore_api_base') ||
        ''
    ).trim();
    return saved || window.location.origin;
})();

// Compatibilidade: alguns pontos antigos ainda usam VIGILACORE_API_BASE
window.VIGILACORE_API_BASE = window.LOGOS_DECISION_API_BASE;

// Helper central de token (mantém compat com chave antiga)
window.ldGetToken = function() {
    return (
        localStorage.getItem('logos_decision_token') ||
        localStorage.getItem('vigilacore_token') ||
        localStorage.getItem('token') ||
        ''
    );
};
/**
 * Wrapper para Fetch com Autenticação (JWT)
 *
 * Intercepta chamadas de rede para:
 * 1. Adicionar automaticamente o cabeçalho 'Authorization: Bearer <token>'.
 * 2. Resolver URLs relativas usando a constante VIGILACORE_API_BASE.
 *
 * @param {string} url - Caminho relativo (ex: '/api/dados') ou URL absoluta.
 * @param {object} options - Opções padrão da API Fetch (method, body, headers, etc.).
 * @returns {Promise<Response>} - A promessa da resposta Fetch.
 */
window.authFetch = function(url, options = {}) {
    const token = window.ldGetToken();
    options.headers = options.headers || {};

    if (token) {
        options.headers['Authorization'] = 'Bearer ' + token;
    }

    // Verifica se a URL é absoluta (http:// ou https://)
    const isAbsolute = /^https?:\/\//i.test(url);
    let finalUrl = url;

    if (!isAbsolute) {
        // Garante que não haja barras duplas na junção da URL
        const path = url.startsWith('/') ? url : ('/' + url);
        finalUrl = window.VIGILACORE_API_BASE.replace(/\/$/, '') + path;
    }

    // ✅ NGROK (FREE TIER): remove o "browser warning" em chamadas programáticas (fetch/XHR)
    // - Não remove o aviso quando o usuário abre o link diretamente no navegador.
    // - É seguro enviar esse header só quando o destino é ngrok.
    try {
        const host = new URL(finalUrl).hostname;
        const isNgrok = /ngrok(-free)?\.dev$/i.test(host) || /ngrok\.io$/i.test(host);
        if (isNgrok) {
            options.headers['ngrok-skip-browser-warning'] = options.headers['ngrok-skip-browser-warning'] || '1';
        }
    } catch (_) {
        // Se a URL não for parseável por algum motivo, apenas ignora.
    }

    return fetch(finalUrl, options);
};

/**
 * Função de Ping (Healthcheck)
 *
 * Verifica se o backend está online fazendo uma requisição leve.
 * Configurada para não usar cache ('no-store') para garantir status em tempo real.
 *
 * @param {string} path - Caminho do endpoint de ping (padrão: '/api/ping').
 * @returns {Promise<Response>}
 */
window.pingFetch = function(path = '/api/ping') {
    const base = window.VIGILACORE_API_BASE.replace(/\/$/, '');
    const p = path.startsWith('/') ? path : ('/' + path);
    const url = base + p;
    const headers = {};
    try {
        const host = new URL(url).hostname;
        const isNgrok = /ngrok(-free)?\.dev$/i.test(host) || /ngrok\.io$/i.test(host);
        if (isNgrok) headers['ngrok-skip-browser-warning'] = '1';
    } catch (_) {}
    return fetch(url, { method: 'GET', cache: 'no-store', headers });
};

// Contador de falhas consecutivas de ping para evitar "piscar" o status em instabilidades breves
window.__vc_ping_failures = 0;

/**
 * Atualiza o Indicador de Status do Sistema (Online/Offline)
 *
 * Altera o texto e a classe CSS do elemento de status (geralmente uma "pill" no topo da página).
 * Só marca como OFFLINE após 2 falhas consecutivas para maior tolerância.
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

// Inicialização automática do monitoramento de conexão ao carregar a página
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
 * que são comuns quando o navegador interrompe requisições ao navegar entre páginas,
 * evitando spam de alertas irrelevantes para o usuário.
 */
(function () {
    const _alert = window.alert ? window.alert.bind(window) : null;

    function isNetworkMessage(msg) {
        const s = String(msg || '');
        return /failed to fetch|networkerror|load failed|fetch api cannot load/i.test(s);
    }

    // Exporta função utilitária para verificar se é erro de rede
    window.vcIsNetworkError = function (err) {
        const m = (err && (err.message || err.toString())) ? String(err.message || err.toString()) : '';
        return isNetworkMessage(m);
    };

    /**
     * Exibe um alerta de erro amigável, ignorando erros de rede irrelevantes.
     * @param {Error|string} err - O erro capturado.
     * @param {string} fallbackMsg - Mensagem padrão caso o erro não tenha detalhes.
     */
    window.vcShowErrorAlert = function (err, fallbackMsg) {
        const msg = (err && (err.message || err.toString())) ? String(err.message || err.toString()) : '';
        if (isNetworkMessage(msg)) {
            console.warn('[LOGOS DECISION] Alerta de rede suprimido:', msg, err);
            return;
        }
        if (_alert) _alert('❌ ' + (msg || fallbackMsg || 'Erro ao conectar com o servidor'));
    };

    // Override do alert global para aplicar o filtro
    if (_alert) {
        window.alert = function (msg) {
            if (isNetworkMessage(msg)) {
                console.warn('[LOGOS DECISION] Alerta suprimido:', msg);
                return;
            }
            return _alert(msg);
        };
    }
})();

/**
 * Controle de Acesso e UI Baseado em Função (Role-Based Access Control - RBAC)
 *
 * - Oculta elementos sensíveis (como botões de "Zerar Banco") para não-desenvolvedores.
 * - Restringe acesso à "Área do Usuário" removendo links de navegação para perfis não autorizados.
 */
(function () {
    let __vc_me_cache = null;

    // Cache simples para evitar múltiplas chamadas ao endpoint /me
    async function vcGetMe() {
        if (__vc_me_cache) return __vc_me_cache;
        const token = window.ldGetToken();
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

    // Remove visualmente os links de navegação para a Área do Usuário
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

    // Verifica se o usuário está atualmente na página restrita
    function isOnUserPage() {
        const p = (window.location.pathname || '').toLowerCase();
        const h = (window.location.href || '').toLowerCase();
        return p.endsWith('usuario.html') || h.includes('/usuario.html') || h.endsWith('usuario.html');
    }

    async function apply() {
        const me = await vcGetMe();
        if (!me || !me.role) return;

        const role = String(me.role || '').toLowerCase();

        // Regra: Apenas 'desenvolvedor' vê o botão de reset global
        if (role !== 'desenvolvedor') {
            document.querySelectorAll('#v2-reset-btn').forEach((el) => {
                el.style.display = 'none';
            });
        }

        // Regra: Apenas 'desenvolvedor' e 'gerencia' (gerente) podem ver/acessar a Área do Usuário
        const allowedUserAreaRoles = ['desenvolvedor', 'gerencia', 'gerente'];

        if (!allowedUserAreaRoles.includes(role)) {
            hideUserAreaNav();

            // Redirecionamento de segurança caso acessem a URL diretamente
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
