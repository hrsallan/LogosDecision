"""
Módulo Principal da Aplicação LOGOS DECISION (Backend)

Este arquivo inicializa a aplicação Flask, configura as rotas da API e gerencia
o ciclo de vida da aplicação. Atua como o ponto de entrada principal para o servidor backend.

Funcionalidades principais:
- Configuração do servidor Flask e CORS.
- Definição de rotas para autenticação (login/registro).
- Endpoints para upload e processamento de arquivos (Releitura/Porteira).
- Endpoints para visualização de dashboards e métricas.
- Gerenciamento de sincronização automática via Scheduler.
"""

import os
from pathlib import Path
from core.config import DB_PATH as CONFIG_DB_PATH
try:
    from dotenv import load_dotenv  # type: ignore
    # Carrega variáveis do arquivo .env na raiz do projeto (LOGOS DECISION/.env)
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
except Exception:
    # Se python-dotenv não estiver instalado, o app continua rodando (assumindo vars de ambiente do sistema)
    pass
import os
import sqlite3
import unicodedata
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import jwt
from datetime import datetime, timedelta, timezone
from core.analytics import deep_scan_excel, deep_scan_porteira_excel, get_file_hash
from core.portal_scraper import download_releitura_excel, download_porteira_excel
from core.porteira_abertura import get_due_date
from core.database import (
    init_db, register_user, authenticate_user, get_user_by_id,
    list_users,
    save_releitura_data, save_porteira_data,
    get_releitura_chart_data, get_releitura_metrics, get_releitura_details,
    get_releitura_due_chart_data, reset_database, is_file_duplicate, save_file_history,
    get_porteira_chart_data, get_porteira_metrics, reset_porteira_database, reset_porteira_global,
    save_porteira_table_data, get_porteira_table_data, get_porteira_totals,
    get_porteira_chart_summary, get_porteira_abertura_monthly_quantities, get_porteira_abertura_snapshot_latest, get_porteira_nao_executadas_chart,
    get_porteira_stats_by_region, get_current_cycle_info,
    set_portal_credentials, get_portal_credentials, get_portal_credentials_status, clear_portal_credentials,
    get_releitura_region_targets, set_releitura_region_targets, get_user_id_by_username, get_user_id_by_matricula,
    get_releitura_unrouted, count_releitura_unrouted, reset_releitura_global,
    save_releitura_daily_snapshot, get_releitura_daily_snapshot
    ,
    # Porteira: Atrasos (snapshot diário)
    get_porteira_atrasos_snapshot, list_porteira_atrasos_snapshot_dates,
    list_porteira_atrasos_congelados_months, get_porteira_atrasos_congelados_month
)
from core.releitura_routing_v2 import route_releituras
from core.scheduler import init_scheduler, get_scheduler

# Chave secreta para assinatura de tokens JWT (padrão seguro em produção via .env)
SECRET_KEY = os.environ.get("JWT_SECRET", "segredo-super-seguro")

# Configuração de caminhos do projeto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_PATH = CONFIG_DB_PATH
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend')
VIEWS_DIR = os.path.join(FRONTEND_DIR, 'views')

# Serve arquivos estáticos (CSS/JS/Imagens) diretamente em /css, /js, etc.
# (equivalente ao Live Server do VSCode, mas pelo próprio Flask)
app = Flask(
    __name__,
    static_folder=FRONTEND_DIR,
    static_url_path=''
)


# Configuração de CORS (Cross-Origin Resource Sharing)
# Permite que o frontend (geralmente em porta diferente no desenvolvimento) acesse a API.
# Exibe headers específicos necessários para autenticação JWT.
CORS(
    app,
    resources={r"/api/*": {"origins": "*"}},
    # Inclui o header do ngrok para pular o "browser warning" em chamadas programáticas
    # (isso é especialmente importante se o frontend estiver em outro domínio/porta e cair em preflight CORS)
    allow_headers=["Content-Type", "Authorization", "ngrok-skip-browser-warning"],
    expose_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)


# -------------------------------------------------------
# Middleware para controle de cache
# -------------------------------------------------------
@app.after_request
def add_cache_control_headers(response):
    """
    Adiciona headers de controle de cache para evitar problemas com cache de navegador.
    Para arquivos estáticos (CSS, JS), permite cache curto mas força revalidação.
    """
    if request.path.startswith('/css/') or request.path.startswith('/js/'):
        # Cache de 1 hora para CSS/JS, mas com revalidação
        response.headers['Cache-Control'] = 'public, max-age=3600, must-revalidate'
    elif request.path.startswith('/api/'):
        # APIs nunca devem ser cacheadas
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


# -------------------------------------------------------
# Rotas de Páginas (Frontend)
# -------------------------------------------------------
@app.get('/')
def page_login():
    # Página inicial: login
    return send_from_directory(VIEWS_DIR, 'login.html')

@app.get('/pages/<path:filename>')
def page_views(filename: str):
    # Todas as páginas HTML ficam em frontend/views
    return send_from_directory(VIEWS_DIR, filename)



# -------------------------------------------------------
# Tratamento de Preflight CORS
# -------------------------------------------------------
@app.before_request
def _handle_preflight_options():
    """
    Intercepta requisições OPTIONS antes do processamento principal.
    Necessário para navegadores aceitarem requisições complexas (com Authorization).
    Retorna 204 (No Content) para aprovar o preflight rapidamente.
    """
    if request.method == 'OPTIONS':
        return ('', 204)

# -------------------------------------------------------
# Utilitários de Autenticação (JWT)
# -------------------------------------------------------
def get_user_id_from_token():
    """
    Extrai o ID do usuário do token JWT presente no cabeçalho Authorization.

    Retorna:
        int: ID do usuário se o token for válido.
        None: Se o token estiver ausente ou inválido.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:] # Remove o prefixo "Bearer "
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return int(payload["user_id"])
    except Exception:
        return None


def get_current_user_from_request():
    """
    Recupera o objeto completo do usuário atual a partir do token da requisição.

    Retorna:
        dict: Dados do usuário (id, username, role, etc.).
        None: Se não autenticado.
    """
    uid = get_user_id_from_token()
    if not uid:
        return None
    return get_user_by_id(uid)


def norm_role(v: str | None) -> str:
    """
    Normaliza a string de cargo/função (role).
    Remove acentos, espaços e converte para minúsculas.

    Exemplo: 'Gerência' -> 'gerencia'
    """
    s = (v or '').strip().lower()
    if not s:
        return ''
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    s = s.replace(' ', '')
    return s

def list_all_user_ids() -> list[int]:
    """
    Lista todos os IDs de usuários cadastrados no banco de dados.
    Utilizado para distribuir dados globais (como Porteira) para todos.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute('SELECT id FROM users')
        ids = [int(r[0]) for r in cur.fetchall() if r and r[0] is not None]
        conn.close()
        return ids
    except Exception as e:
        print(f"[WARN] Erro ao listar usuários: {e}")
        return []

# -------------------------------------------------------
# Rotas de Autenticação
# -------------------------------------------------------
@app.route('/api/register', methods=['POST'])
def register():
    """
    Endpoint para registro de novos usuários.

    Regras de negócio:
    - Qualquer um pode criar contas com permissões básicas ('analistas').
    - Contas privilegiadas ('gerencia', 'diretoria', 'desenvolvedor') exigem
      autenticação prévia de um usuário com privilégios similares, exceto
      no bootstrap (primeiro usuário do sistema).
    """
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    nome = (data.get('nome') or '').strip() or None
    base = (data.get('base') or '').strip() or None
    matricula = (data.get('matricula') or '').strip() or None

    def _normalize_role(v):
        s = (v or '').strip().lower()
        if not s:
            return ''
        s = ''.join(
            c for c in unicodedata.normalize('NFKD', s)
            if not unicodedata.combining(c)
        )
        s = s.replace(' ', '')
        return s

    role_raw = _normalize_role(data.get('role'))

    public_roles = {'analistas', 'supervisor'}
    privileged_roles = {'diretoria', 'gerencia', 'desenvolvedor'}
    all_roles = public_roles | privileged_roles

    # Verifica se é o primeiro usuário privilegiado (bootstrap)
    def bootstrap_privileged_allowed():
        import sqlite3
        from core.database import DB_PATH
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE LOWER(role) IN ('diretoria','gerencia','desenvolvedor')")
        n = (cur.fetchone() or [0])[0]
        conn.close()
        return n == 0

    if not role_raw:
        role = 'analistas'
    elif role_raw not in all_roles:
        return jsonify({
            'success': False,
            'msg': 'Função (role) inválida',
            'allowed': sorted(list(all_roles)),
        }), 400
    elif role_raw in public_roles:
        role = role_raw
    else:
        # Lógica de proteção para criação de usuários privilegiados
        current_user = get_current_user_from_request()
        if not current_user:
            if bootstrap_privileged_allowed():
                role = role_raw
            else:
                return jsonify({
                'success': False,
                'msg': 'Criação de usuário privilegiado requer autenticação.',
                'allowed_public': sorted(list(public_roles)),
                'requested': role_raw,
                }), 403
        else:
            creator_role = (current_user.get('role') or '').strip().lower()
            if creator_role in ('diretoria', 'desenvolvedor'):
                role = role_raw
            else:
                return jsonify({
                    'success': False,
                    'msg': 'Acesso negado para criar usuários com privilégios elevados.',
                    'allowed_public': sorted(list(public_roles)),
                    'requested': role_raw,
                }), 403

    if not username or not password:
        return jsonify({'success': False, 'msg': 'Usuário e senha são obrigatórios.'}), 400

    try:
        ok = register_user(username, password, role=role, nome=nome, base=base, matricula=matricula)
    except Exception as e:
        return jsonify({
            'success': False,
            'msg': 'Falha ao registrar usuário no banco de dados',
            'detail': f'{e.__class__.__name__}: {str(e)}'
        }), 500

    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'msg': 'Usuário já existe.'}), 409

@app.route('/api/login', methods=['POST'])
def login():
    """
    Autentica o usuário e retorna um token JWT válido por 24 horas.
    """
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = authenticate_user(username, password)
    if user:
        payload = {
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "exp": (datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        return jsonify({"success": True, "token": token})
    return jsonify({"success": False, "msg": "Credenciais inválidas"}), 401



# -------------------------------------------------------
# Rotas: Credenciais do Portal (SGL)
# -------------------------------------------------------
@app.route('/api/user/portal-credentials', methods=['GET'])
def portal_credentials_status():
    """
    Verifica se o usuário possui credenciais do portal SGL configuradas.

    Regra especial: Usuários da diretoria/desenvolvimento "herdam" a configuração
    do Gerente se a própria não estiver configurada, para facilitar o uso.
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    user_id = int(user.get('id'))
    role = norm_role(user.get('role'))

    status = get_portal_credentials_status(user_id)

    if (not status.get('configured')) and role in ("diretoria", "desenvolvedor"):
        manager_username = (os.environ.get("RELEITURA_MANAGER_USERNAME") or "GRTRI").strip()
        manager_id = get_user_id_by_username(manager_username)
        if manager_id:
            mgr_status = get_portal_credentials_status(manager_id)
            if mgr_status.get('configured'):
                mgr_status["configured_via_manager"] = True
                return jsonify(mgr_status)

    return jsonify(status)

@app.route('/api/user/portal-credentials', methods=['PUT'])
def portal_credentials_set():
    """Define as credenciais do portal SGL para o usuário atual."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    data = request.json or {}
    portal_user = (data.get("portal_user") or "").strip()
    portal_password = data.get("portal_password") or ""
    try:
        set_portal_credentials(user_id, portal_user, portal_password)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/user/portal-credentials', methods=['DELETE'])
def portal_credentials_clear():
    """Remove as credenciais do portal SGL do usuário atual."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    try:
        clear_portal_credentials(int(user_id))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# -------------------------------------------------------
# Rotas: Perfil do Usuário
# -------------------------------------------------------
@app.get('/api/user/me')
def user_me():
    """Retorna os dados do usuário autenticado."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401
    return jsonify(user)


# -------------------------------------------------------
# Rotas: Status e Monitoramento (Releitura)
# -------------------------------------------------------

@app.get('/api/ping')
def api_ping():
    """Healthcheck simples para verificar se o backend está online."""
    return jsonify({'ok': True})

@app.route('/api/status/releitura', methods=['GET'])
def status_releitura():
    """Retorna métricas, gráficos e detalhes de Releitura.

    Histórico por data:
      - A data selecionada deve refletir o estado/snapshot daquele dia.
      - Analistas: usa snapshot diário (se existir) e gráficos por hora.
      - Gerência/Diretoria/Desenvolvedor: agrega snapshots/gráficos por região.
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    user_id = int(user['id'])
    role = norm_role(user.get('role'))

    # Parâmetros
    date_str = (request.args.get('date') or '').strip() or None
    region = (request.args.get('region') or 'all').strip()

    # "Hoje" local (evita bug UTC vs Brasil)
    try:
        from zoneinfo import ZoneInfo  # py3.9+
        tz = ZoneInfo(os.environ.get('APP_TIMEZONE', 'America/Araguaina'))
        today_str = datetime.now(tz).date().isoformat()
    except Exception:
        # Fallback: -3h (Brasil sem DST)
        today_str = (datetime.now() - timedelta(hours=3)).date().isoformat()

    if not date_str:
        date_str = today_str

    is_today = (date_str == today_str)
    privileged = role in ('gerencia', 'diretoria', 'desenvolvedor')

    # ============================
    # VISÃO DO ANALISTA (INDIVIDUAL)
    # ============================
    if not privileged:
        snap = None
        if not is_today and date_str:
            try:
                snap = get_releitura_daily_snapshot(user_id, date_str)
            except Exception:
                snap = None

        labels, values = get_releitura_chart_data(user_id, date_str)
        due_labels, due_values = get_releitura_due_chart_data(user_id, date_str)
        details = get_releitura_details(user_id, date_str)

        if snap and isinstance(snap, dict) and isinstance(snap.get('metrics'), dict):
            metrics = snap['metrics']
            regions_summary = snap.get('regions') or {}
        else:
            metrics = get_releitura_metrics(user_id, date_str)
            base_name = (user.get('base') or '').strip() or 'Minha Base'
            regions_summary = {
                base_name: {
                    "configured": True,
                    "total": metrics.get('total', 0),
                    "pendentes": metrics.get('pendentes', 0),
                    "realizadas": metrics.get('realizadas', 0),
                    "atrasadas": metrics.get('atrasadas', 0),
                }
            }

        try:
            unrouted_count = count_releitura_unrouted(user_id, date_str)
        except Exception:
            unrouted_count = 0

        # Snapshot de HOJE (best-effort). Obs.: também é salvo na sincronização.
        if is_today:
            try:
                snapshot_data = {
                    'metrics': metrics if isinstance(metrics, dict) else {},
                    'regions': regions_summary if isinstance(regions_summary, dict) else {},
                }
                save_releitura_daily_snapshot(user_id, today_str, snapshot_data)
            except Exception:
                pass

        return jsonify({
            "status": "online",
            "metrics": metrics,
            "chart": {"labels": labels, "values": values},
            "due_chart": {"labels": due_labels, "values": due_values},
            "details": details,
            "regions": regions_summary,
            "unrouted_count": unrouted_count,
            "from_snapshot": bool(snap)
        })

    # =======================================
    # VISÃO GERENCIAL (AGREGADA POR REGIÃO)
    # =======================================
    targets = get_releitura_region_targets()

    region_user_ids = {}
    for rname in ('Araxá', 'Uberaba', 'Frutal'):
        matricula = targets.get(rname)
        uid = get_user_id_by_matricula(matricula) if matricula else None
        region_user_ids[rname] = uid

    # Manager "padrão" para registros não roteados
    manager_username = (os.environ.get("RELEITURA_MANAGER_USERNAME") or "GRTRI").strip()
    manager_id = get_user_id_by_username(manager_username) or user_id

    # Regiões selecionadas
    selected = []
    for rname, uid in region_user_ids.items():
        if not uid:
            continue
        if region != 'all' and region != rname:
            continue
        selected.append((rname, uid))

    # Agrega gráfico por hora
    def agg_hourly_chart():
        labels_ref = None
        totals = None
        for _r, uid in selected:
            labs, vals = get_releitura_chart_data(uid, date_str)
            if labels_ref is None:
                labels_ref = list(labs)
                totals = [0] * len(vals)
            for i, v in enumerate(vals):
                if totals is not None and i < len(totals):
                    totals[i] += int(v or 0)
        if labels_ref is None:
            labels_ref = [f"{h:02d}h" for h in range(5, 22)]
            totals = [0] * len(labels_ref)
        return labels_ref, totals

    # Agrega gráfico de vencimentos
    def agg_due_chart():
        labels_ref = None
        combined = {}
        for _r, uid in selected:
            labs, vals = get_releitura_due_chart_data(uid, date_str)
            if labels_ref is None:
                labels_ref = list(labs)
            for l, v in zip(labs, vals):
                combined[l] = combined.get(l, 0) + int(v or 0)
        if labels_ref is None:
            labels_ref = ['--/--'] * 7
        values_ref = [combined.get(l, 0) for l in labels_ref]
        return labels_ref, values_ref

    labels, values = agg_hourly_chart()
    due_labels, due_values = agg_due_chart()

    # Resumo por região com snapshot (se existir)
    regions_summary = {}
    total_sum = pend_sum = real_sum = atr_sum = 0

    for rname, uid in region_user_ids.items():
        if not uid:
            regions_summary[rname] = {"configured": False, "total": 0, "pendentes": 0, "realizadas": 0, "atrasadas": 0}
            continue

        snap = None
        if date_str and not is_today:
            try:
                snap = get_releitura_daily_snapshot(uid, date_str)
            except Exception:
                snap = None

        if snap and isinstance(snap, dict) and isinstance(snap.get('metrics'), dict):
            m = snap['metrics']
        else:
            m = get_releitura_metrics(uid, date_str)

        r_total = int(m.get('total', 0) or 0)
        r_pend = int(m.get('pendentes', 0) or 0)
        r_real = int(m.get('realizadas', 0) or 0)
        r_atr = int(m.get('atrasadas', 0) or 0)

        regions_summary[rname] = {
            "configured": True,
            "total": r_total,
            "pendentes": r_pend,
            "realizadas": r_real,
            "atrasadas": r_atr,
        }

        if region == 'all' or region == rname:
            total_sum += r_total
            pend_sum += r_pend
            real_sum += r_real
            atr_sum += r_atr

    metrics = {"total": total_sum, "pendentes": pend_sum, "realizadas": real_sum, "atrasadas": atr_sum}

    # Detalhes (tabela) — best-effort
    details = []
    try:
        if selected:
            ids = [uid for _r, uid in selected]
            ph = ",".join(["?"] * len(ids))
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            if date_str:
                cur.execute(f"""
                    SELECT status, ul, instalacao, endereco, razao, vencimento, reg, upload_time, region, route_status, route_reason, ul_regional, localidade
                    FROM releituras
                    WHERE user_id IN ({ph}) AND status='PENDENTE' AND DATE(upload_time)=DATE(?)
                    ORDER BY
                        CASE WHEN vencimento IS NULL OR TRIM(vencimento) = '' THEN 1 ELSE 0 END,
                        CASE
                            WHEN instr(vencimento, '/') = 3 THEN substr(vencimento, 7, 4) || '-' || substr(vencimento, 4, 2) || '-' || substr(vencimento, 1, 2)
                            WHEN instr(vencimento, '-') = 5 THEN substr(vencimento, 1, 10)
                            ELSE '9999-12-31'
                        END,
                        reg ASC,
                        upload_time DESC
                    LIMIT 500
                """, tuple(ids) + (date_str,))
            else:
                cur.execute(f"""
                    SELECT status, ul, instalacao, endereco, razao, vencimento, reg, upload_time, region, route_status, route_reason, ul_regional, localidade
                    FROM releituras
                    WHERE user_id IN ({ph}) AND status='PENDENTE'
                    ORDER BY
                        CASE WHEN vencimento IS NULL OR TRIM(vencimento) = '' THEN 1 ELSE 0 END,
                        CASE
                            WHEN instr(vencimento, '/') = 3 THEN substr(vencimento, 7, 4) || '-' || substr(vencimento, 4, 2) || '-' || substr(vencimento, 1, 2)
                            WHEN instr(vencimento, '-') = 5 THEN substr(vencimento, 1, 10)
                            ELSE '9999-12-31'
                        END,
                        reg ASC,
                        upload_time DESC
                    LIMIT 500
                """, tuple(ids))

            rows = cur.fetchall()
            conn.close()
            details = [{
                "status": r[0],
                "ul": r[1],
                "inst": r[2],
                "instalacao": r[2],
                "endereco": r[3],
                "razao": r[4],
                "venc": r[5],
                "vencimento": r[5],
                "reg": r[6],
                "upload_time": r[7],
                "region": r[8],
                "route_status": r[9],
                "route_reason": r[10],
                "ul_regional": r[11],
                "localidade": r[12],
            } for r in rows]
    except Exception:
        details = []

    # Não roteados (contagem) — mantém regra existente (manager)
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        if date_str:
            cur.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND route_status='UNROUTED' AND DATE(upload_time)=DATE(?)", (manager_id, date_str))
        else:
            cur.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND route_status='UNROUTED'", (manager_id,))
        unrouted_count = int(cur.fetchone()[0] or 0)
        conn.close()
    except Exception:
        unrouted_count = 0

    # Snapshot gerencial de HOJE (best-effort)
    if is_today:
        try:
            snapshot_data = {
                'metrics': metrics if isinstance(metrics, dict) else {},
                'regions': regions_summary if isinstance(regions_summary, dict) else {},
            }
            save_releitura_daily_snapshot(user_id, today_str, snapshot_data)
        except Exception:
            pass

    return jsonify({
        "status": "online",
        "metrics": metrics,
        "chart": {"labels": labels, "values": values},
        "due_chart": {"labels": due_labels, "values": due_values},
        "details": details,
        "regions": regions_summary,
        "unrouted_count": unrouted_count,
        "from_snapshot": (not is_today)
    })


@app.route('/api/status/porteira', methods=['GET'])
def status_porteira():
    """Retorna o status geral do módulo Porteira."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    date_str = request.args.get('date')
    labels, values = get_porteira_chart_data(user_id, date_str)
    metrics = get_porteira_metrics(user_id)
    return jsonify({
        "status": "online",
        "chart": {"labels": labels, "values": values},
        "metrics": metrics,
        "details": []
    })

@app.route('/api/reset', methods=['POST'])
def reset():
    """Zera o banco de dados global de Releitura (Apenas Desenvolvedor)."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({"success": False, "error": "Usuário não autenticado"}), 401

    if norm_role(user.get('role')) != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    reset_releitura_global()
    return jsonify({"success": True, "message": "Banco de releituras zerado (GLOBAL)."})

@app.route('/api/reset/porteira', methods=['POST'])
def reset_porteira():
    """Zera o banco de dados global de Porteira (Apenas Desenvolvedor)."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({"success": False, "error": "Usuário não autenticado"}), 401

    if norm_role(user.get('role')) != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    reset_porteira_global()
    return jsonify({"success": True, "message": "Banco de porteira zerado (GLOBAL)."})


# -------------------------------------------------------
# Rotas: Upload de Arquivos
# -------------------------------------------------------
@app.route('/api/upload', methods=['POST'])
def upload_releitura():
    """
    Processa o upload de um arquivo Excel de Releitura.
    - Salva temporariamente.
    - Calcula hash para evitar duplicidade.
    - Executa o roteamento (V2) para distribuir entre regiões.
    """
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    file = request.files.get('file')
    if not file:
        return jsonify({"success": False, "error": "Arquivo não enviado"}), 400

    temp_path = os.path.join(DATA_DIR, 'temp_' + file.filename)
    os.makedirs(DATA_DIR, exist_ok=True)
    file.save(temp_path)

    file_hash = get_file_hash(temp_path)
    details = deep_scan_excel(temp_path) or []
    if not details:
        return jsonify({"success": False, "error": "Falha ao processar o Excel (releitura) ou arquivo vazio."}), 400

    if is_file_duplicate(file_hash, 'releitura', user_id):
        return jsonify({"success": False, "error": "DUPLICADO", "message": "Este relatório já foi processado anteriormente."})

    # Roteamento V2
    routed_details = route_releituras(details)
    save_releitura_data(routed_details, file_hash, user_id)
    labels, values = get_releitura_chart_data(user_id)
    due_labels, due_values = get_releitura_due_chart_data(user_id)
    metrics = get_releitura_metrics(user_id)
    all_details = get_releitura_details(user_id)

    return jsonify({
        "success": True,
        "metrics": metrics,
        "chart": {"labels": labels, "values": values},
        "due_chart": {"labels": due_labels, "values": due_values},
        "details": all_details
    })

@app.route('/api/upload/porteira', methods=['POST'])
def upload_porteira():
    """
    Processa o upload de um arquivo Excel de Porteira.
    - O arquivo é processado e distribuído para TODOS os usuários, pois
      a visão é filtrada posteriormente por região/matrícula no acesso aos dados.
    """
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    file = request.files.get('file')
    if not file:
        return jsonify({"success": False, "error": "Nenhum arquivo enviado"}), 400

    temp_path = os.path.join(DATA_DIR, 'temp_porteira_' + file.filename)
    os.makedirs(DATA_DIR, exist_ok=True)
    file.save(temp_path)

    file_hash = get_file_hash(temp_path)
    details = deep_scan_porteira_excel(temp_path)
    if details is None:
        return jsonify({"success": False, "error": "Falha ao processar o Excel (porteira)."}), 400

    if is_file_duplicate(file_hash, 'porteira', user_id):
        return jsonify({"success": False, "error": "DUPLICADO", "message": "Este relatório já foi processado anteriormente."})

    for _uid in list_all_user_ids():
        save_porteira_table_data(details, _uid, file_hash=file_hash)
    save_file_history('porteira', len(details), file_hash, user_id)

    totals = get_porteira_totals(user_id)
    chart = get_porteira_chart_summary(user_id)
    table = get_porteira_table_data(user_id)

    return jsonify({
        "success": True,
        "totals": totals,
        "chart": chart,
        "table": table
    })


# -------------------------------------------------------
# Rotas: Sincronização Automática (Portal Scraper)
# -------------------------------------------------------
@app.route('/api/sync/releitura', methods=['POST'])
def sync_releitura():
    """
    Dispara manualmente a sincronização de Releitura (download do portal).
    Restrito a desenvolvedores para testes.
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({"success": False, "error": "Usuário não autenticado"}), 401

    role = norm_role(user.get('role'))
    if role != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    # BUG FIX: manager_username definido fora do try para evitar NameError no except → HTTP 500
    manager_username = (os.environ.get("RELEITURA_MANAGER_USERNAME") or "GRTRI").strip()

    try:
        manager_id = get_user_id_by_username(manager_username) or int(user['id'])

        creds = get_portal_credentials(manager_id)
        if not creds:
            return jsonify({
                "success": False,
                "error": f"Credenciais do portal não configuradas para o gerente '{manager_username}'. Cadastre em 'Área do Usuário' (logado como {manager_username})."
            }), 400

        downloaded_path = download_releitura_excel(portal_user=creds['portal_user'], portal_pass=creds['portal_password'])
        if not downloaded_path or not os.path.exists(downloaded_path):
            try:
                from core.email_alerts import notify_scraper_error
                notify_scraper_error(
                    where="API/sync/releitura",
                    err=RuntimeError("Relatório não foi baixado (releitura)"),
                    extra={"manager_username": manager_username, "downloaded_path": downloaded_path},
                    traceback_text="(sem traceback: download não gerou arquivo)",
                )
            except Exception:
                pass
            return jsonify({"success": False, "error": "Relatório não foi baixado (arquivo inexistente)."}), 500

    except Exception as e:
        try:
            from core.email_alerts import notify_scraper_error
            notify_scraper_error(where="API/sync/releitura", err=e, extra={"manager_username": manager_username})
        except Exception:
            pass
        return jsonify({"success": False, "error": "Falha ao baixar relatório (releitura).", "detail": str(e)}), 500

    file_hash = get_file_hash(downloaded_path)
    details = deep_scan_excel(downloaded_path) or []
    if not details:
        return jsonify({"success": False, "error": "Falha ao processar o Excel baixado (releitura) ou arquivo vazio."}), 400

    try:
        details_v2 = route_releituras(details)
        from dataclasses import dataclass
        @dataclass
        class LegacyRouted:
            routed: dict
            unrouted: list
        
        routed_map = {"Araxá": [], "Uberaba": [], "Frutal": []}
        unrouted_list = []
        for it in details_v2:
            reg = it.get("region")
            if it.get("route_status") == "ROUTED" and reg in routed_map:
                routed_map[reg].append(it)
            else:
                unrouted_list.append(it)
        
        routed = LegacyRouted(routed=routed_map, unrouted=unrouted_list)
        targets = get_releitura_region_targets()

        summary = {
            "Araxá": {"saved": 0, "user_id": None, "matricula": targets.get("Araxá"), "status": "OK"},
            "Uberaba": {"saved": 0, "user_id": None, "matricula": targets.get("Uberaba"), "status": "OK"},
            "Frutal": {"saved": 0, "user_id": None, "matricula": targets.get("Frutal"), "status": "OK"},
            "unrouted_saved": 0
        }

        for region, items in routed.routed.items():
            matricula = targets.get(region)
            uid = get_user_id_by_matricula(matricula) if matricula else None
            summary[region]["user_id"] = uid

            if not items:
                continue

            if uid:
                if is_file_duplicate(file_hash, 'releitura', uid):
                    summary[region]["status"] = "DUPLICADO"
                    continue
                save_releitura_data(items, file_hash, uid)
                summary[region]["saved"] = len(items)
            else:
                for it in items:
                    it["route_status"] = "UNROUTED"
                    it["route_reason"] = "REGIAO_SEM_MATRICULA"
                    it["region"] = region

                if not is_file_duplicate(file_hash, 'releitura', manager_id):
                    save_releitura_data(items, file_hash, manager_id)
                    summary[region]["status"] = "UNROUTED_TO_MANAGER"
                else:
                    summary[region]["status"] = "DUPLICADO"

        if routed.unrouted:
            if not is_file_duplicate(file_hash, 'releitura', manager_id):
                save_releitura_data(routed.unrouted, file_hash, manager_id)
                summary["unrouted_saved"] = len(routed.unrouted)
            else:
                summary["unrouted_saved"] = 0

        return jsonify({
            "success": True,
            "message": "Sincronização concluída (roteamento regional aplicado).",
            "summary": summary
        })

    except Exception as e:
        return jsonify({"success": False, "error": "Falha ao rotear/salvar dados regionais.", "detail": str(e)}), 500


@app.route('/api/sync/porteira', methods=['POST'])
def sync_porteira():
    """
    Dispara manualmente a sincronização de Porteira (download do portal).
    Restrito a desenvolvedores.
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    if norm_role(user.get('role')) != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    user_id = int(user['id'])

    # BUG FIX: manager_username definido fora do try para evitar NameError no except → HTTP 500
    manager_username = (os.environ.get("RELEITURA_MANAGER_USERNAME") or "GRTRI").strip()

    try:
        manager_id = get_user_id_by_username(manager_username) or None
        creds = get_portal_credentials(manager_id) if manager_id else None
        if not creds:
            return jsonify({
                "success": False,
                "error": f"Credenciais do portal não configuradas para o gerente '{manager_username}'. Cadastre em 'Área do Usuário' (logado como {manager_username})."
            }), 400
        downloaded_path = download_porteira_excel(portal_user=creds['portal_user'], portal_pass=creds['portal_password'])
        if not downloaded_path or not os.path.exists(downloaded_path):
            try:
                from core.email_alerts import notify_scraper_error
                notify_scraper_error(
                    where="API/sync/porteira",
                    err=RuntimeError("Relatório não foi baixado (porteira)"),
                    extra={"manager_username": manager_username, "downloaded_path": downloaded_path},
                    traceback_text="(sem traceback: download não gerou arquivo)",
                )
            except Exception:
                pass
            return jsonify({"success": False, "error": "Relatório não foi baixado (arquivo inexistente)."}), 500

    except Exception as e:
        try:
            from core.email_alerts import notify_scraper_error
            notify_scraper_error(where="API/sync/porteira", err=e, extra={"manager_username": manager_username})
        except Exception:
            pass
        return jsonify({"success": False, "error": "Falha ao baixar relatório (porteira).", "detail": str(e)}), 500

    file_hash = get_file_hash(downloaded_path)
    details = deep_scan_porteira_excel(downloaded_path)
    if details is None:
        return jsonify({"success": False, "error": "Falha ao processar o Excel baixado (porteira)."}), 400

    # BUG FIX: verificar duplicidade individualmente, não só pelo user_id do dev logado
    # (usar user_id do dev como proxy fazia retornar DUPLICADO para todos os outros usuários)
    all_uids = list_all_user_ids()
    any_new = any(not is_file_duplicate(file_hash, 'porteira', _uid) for _uid in all_uids)
    if not any_new:
        return jsonify({"success": False, "error": "DUPLICADO", "message": "Este relatório já foi processado para todos os usuários."})

    for _uid in all_uids:
        if not is_file_duplicate(file_hash, 'porteira', _uid):
            save_porteira_table_data(details, _uid, file_hash=file_hash)
            save_file_history('porteira', len(details), file_hash, _uid)

    totals = get_porteira_totals(user_id)
    chart = get_porteira_chart_summary(user_id)
    table = get_porteira_table_data(user_id)

    return jsonify({
        "success": True,
        "totals": totals,
        "chart": chart,
        "table": table
    })


# -------------------------------------------------------
# Rotas: Análise de Dados (Porteira)
# -------------------------------------------------------
@app.route('/api/porteira/chart', methods=['GET'])
def porteira_chart():
    """Retorna dados para os gráficos de porteira, com filtros de ciclo e região."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    ciclo = request.args.get('ciclo')
    regiao = request.args.get('regiao')
    data = get_porteira_chart_summary(user_id, ciclo=ciclo, regiao=regiao)
    return jsonify(data)


@app.route('/api/porteira/current-cycle', methods=['GET'])
def porteira_current_cycle():
    """Retorna informações sobre o ciclo de leitura atual (baseado no mês)."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    
    cycle_info = get_current_cycle_info()
    return jsonify({
        "success": True,
        "data": cycle_info
    })


@app.route('/api/porteira/table', methods=['GET'])
def porteira_table():
    """Retorna a tabela detalhada da Porteira com totais."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    ciclo = request.args.get('ciclo')
    regiao = request.args.get('regiao')
    rows = get_porteira_table_data(user_id, ciclo=ciclo, regiao=regiao)
    totals = get_porteira_totals(user_id, ciclo=ciclo, regiao=regiao)

    return jsonify({
        "success": True,
        "data": rows,
        "totals": totals
    })


@app.route('/api/porteira/abertura', methods=['GET'])
def porteira_abertura():
    """
    Retorna dados para a tabela 'Abertura de Porteira' (Comparativo Mensal).
    Compara o desempenho do mês atual com o mês anterior.

    Observação:
      - 'atraso' é flag 0/1 (venceu => 1).
      - 'finalizado_em' aparece quando a quantidade daquela razão zerou (fechou pendências).
    """
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    ciclo = request.args.get('ciclo')
    regiao = request.args.get('regiao')

    now = datetime.now()
    cur_year, cur_month = int(now.year), int(now.month)
    prev_year, prev_month = (cur_year - 1, 12) if cur_month == 1 else (cur_year, cur_month - 1)

    PT_MONTHS = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
        7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }

    def month_label(y: int, m: int) -> str:
        return f"{PT_MONTHS.get(int(m), 'Mês')} {int(y)}"

    def _fmt_iso_to_br(d_iso: str | None) -> str:
        if not d_iso:
            return ''
        try:
            return datetime.fromisoformat(str(d_iso)).date().strftime('%d/%m/%Y')
        except Exception:
            # Se vier algo inesperado, retorna cru (ainda assim é melhor que quebrar)
            return str(d_iso)

    def build_month_payload(y: int, m: int, is_current_month: bool = False):
        # 1) Preferir snapshot salvo no banco (auditoria/histórico)
        snap = None
        snap_rows = None
        try:
            snap = get_porteira_abertura_snapshot_latest(
                int(user_id), int(y), int(m),
                ciclo=ciclo, regiao=regiao
            )
            if snap and isinstance(snap.get("rows"), dict) and snap["rows"]:
                snap_rows = snap["rows"]
        except Exception:
            snap = None
            snap_rows = None

        # 2) Fallback: histórico mensal (ou cálculo direto do snapshot atual quando for mês corrente)
        quantities = None
        if not snap_rows:
            quantities = get_porteira_abertura_monthly_quantities(
                int(user_id), int(y), int(m),
                ciclo=ciclo, regiao=regiao,
                fallback_latest=bool(is_current_month)
            )

        temp_rows = []
        total_osb = 0
        total_cnv = 0
        total_qtd = 0
        total_atraso = 0

        today = now.date()

        for r in range(1, 19):
            key = f"{r:02d}"

            if snap_rows:
                raw = snap_rows.get(key) or {}

                # due_date salva em ISO (YYYY-MM-DD)
                due = None
                due_iso = raw.get("due_date")
                if due_iso:
                    try:
                        due = datetime.fromisoformat(str(due_iso)).date()
                    except Exception:
                        due = None

                data_str = due.strftime('%d/%m/%Y') if due else '--/--'
                osb = int(round(float(raw.get("osb", 0) or 0)))
                cnv = int(round(float(raw.get("cnv", 0) or 0)))
                qtd = int(round(float(raw.get("quantidade", 0) or 0)))
                atraso = int(raw.get("atraso", 0) or 0)

                finalizado_str = _fmt_iso_to_br(raw.get("finalizado_em"))
                finalizado_osb_str = _fmt_iso_to_br(raw.get("finalizado_osb"))
                finalizado_cnv_str = _fmt_iso_to_br(raw.get("finalizado_cnv"))
            else:
                due = get_due_date(int(y), int(m), int(r))
                data_str = due.strftime('%d/%m/%Y') if due else '--/--'

                raw = (quantities or {}).get(key) or {}
                osb = int(round(float(raw.get("osb", 0) or 0)))
                cnv = int(round(float(raw.get("cnv", 0) or 0)))
                qtd = int(round(float(raw.get("quantidade", 0) or 0)))

                # Regra: "venceu => 1" (independente da quantidade).
                if due:
                    atraso = 1 if (today > due) else 0
                else:
                    atraso = 1

                finalizado_str = ''
                finalizado_osb_str = ''
                finalizado_cnv_str = ''

            total_osb += osb
            total_cnv += cnv
            total_qtd += qtd
            total_atraso += atraso
            temp_rows.append((r, data_str, finalizado_str, finalizado_osb_str, finalizado_cnv_str, osb, cnv, qtd, atraso))

        has_data = bool(snap_rows) or bool(total_qtd > 0)

        rows = []
        for (r, data_str, finalizado_str, finalizado_osb_str, finalizado_cnv_str, osb, cnv, qtd, atraso) in temp_rows:
            rows.append({
                'razao': f'RZ {r:02d}',
                'data': data_str,
                'finalizado_em': (finalizado_str if has_data else None),
                'finalizado_osb': (finalizado_osb_str if has_data else None),
                'finalizado_cnv': (finalizado_cnv_str if has_data else None),
                'osb': (int(osb) if has_data else None),
                'cnv': (int(cnv) if has_data else None),
                'quantidade': (int(qtd) if has_data else None),
                'atraso': (int(atraso) if has_data else None),
            })

        payload = {
            'year': int(y),
            'month': int(m),
            'label': month_label(int(y), int(m)),
            'has_data': has_data,
            'rows': rows,
            'totals': {
                'osb': (int(total_osb) if has_data else None),
                'cnv': (int(total_cnv) if has_data else None),
                'quantidade': (int(total_qtd) if has_data else None),
                'atraso': (int(total_atraso) if has_data else None)
            }
        }

        # Metadados do snapshot (opcional; frontend ignora se não usar)
        if snap and snap.get("snapshot_at"):
            payload["snapshot_at"] = snap.get("snapshot_at")
            payload["snapshot_file_hash"] = snap.get("file_hash")

        return payload

    current_payload = build_month_payload(cur_year, cur_month, is_current_month=True)
    previous_payload = build_month_payload(prev_year, prev_month, is_current_month=False)

    return jsonify({
        'success': True,
        'current': current_payload,
        'previous': previous_payload
    })


# -------------------------------------------------------
# Porteira: Atrasos (Snapshot diário - primeiro relatório do dia)
# -------------------------------------------------------

@app.route('/api/porteira/atrasos-snapshot/dates', methods=['GET'])
def porteira_atrasos_snapshot_dates():
    """Lista datas disponíveis de snapshots diários de atraso (para dropdown no frontend)."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    try:
        dates = list_porteira_atrasos_snapshot_dates(int(user_id), limit=21)
        return jsonify({"success": True, "dates": dates})
    except Exception as e:
        return jsonify({"success": False, "error": "Falha ao listar snapshots", "detail": str(e)}), 500


@app.route('/api/porteira/atrasos-snapshot', methods=['GET'])
def porteira_atrasos_snapshot():
    """Retorna o snapshot diário congelado (18 razões) para a data informada."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    date_str = request.args.get('date')
    try:
        payload = get_porteira_atrasos_snapshot(int(user_id), snapshot_date=date_str)
        return jsonify(payload)
    except Exception as e:
        return jsonify({"success": False, "error": "Falha ao carregar snapshot", "detail": str(e)}), 500


# -------------------------------------------------------
# Porteira: Atrasos Congelados (Acumulado mensal - OSB/CNV)
# -------------------------------------------------------

@app.route('/api/porteira/atrasos-congelados/months', methods=['GET'])
def porteira_atrasos_congelados_months():
    """Lista meses disponíveis (YYYY-MM) para o widget de Atrasos Congelados."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    ciclo = request.args.get('ciclo')
    regiao = request.args.get('regiao')

    try:
        months = list_porteira_atrasos_congelados_months(int(user_id), ciclo=ciclo, regiao=regiao, limit=18)
        return jsonify({"success": True, "months": months})
    except Exception as e:
        return jsonify({"success": False, "error": "Falha ao listar meses", "detail": str(e)}), 500


@app.route('/api/porteira/atrasos-congelados', methods=['GET'])
def porteira_atrasos_congelados():
    """Retorna o acumulado mensal de Atrasos Congelados (18 razões) – nunca diminui no mês."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    ciclo = request.args.get('ciclo')
    regiao = request.args.get('regiao')

    month_str = (request.args.get('month') or '').strip()
    try:
        if month_str and re.match(r"^\d{4}-\d{2}$", month_str):
            ano = int(month_str.split('-')[0])
            mes = int(month_str.split('-')[1])
        else:
            now = datetime.now()
            ano = int(now.year)
            mes = int(now.month)

        payload = get_porteira_atrasos_congelados_month(int(user_id), ano=ano, mes=mes, ciclo=ciclo, regiao=regiao)
        payload["month_key"] = f"{ano:04d}-{mes:02d}"
        return jsonify(payload)
    except Exception as e:
        return jsonify({"success": False, "error": "Falha ao carregar atrasos congelados", "detail": str(e)}), 500

@app.route('/api/porteira/nao-executadas-chart', methods=['GET'])
def porteira_nao_executadas_chart():
    """Retorna dados para o gráfico de 'Não Executadas'."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    ciclo = request.args.get('ciclo')
    regiao = request.args.get('regiao')
    labels, values = get_porteira_nao_executadas_chart(user['id'], ciclo=ciclo, regiao=regiao)
    return jsonify({
        "labels": labels,
        "values": values
    })



@app.route('/api/porteira/stats-by-region', methods=['GET'])
def porteira_stats_by_region():
    """Retorna estatísticas agregadas por região."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    ciclo = request.args.get('ciclo')
    regiao = request.args.get('regiao')

    try:
        stats = get_porteira_stats_by_region(user['id'], ciclo=ciclo, regiao=regiao)
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        print(f"[ERROR] Erro ao buscar estatísticas por região: {e}")
        return jsonify({'success': False, 'error': 'Erro ao processar estatísticas por região'}), 500


@app.route('/api/porteira/regioes', methods=['GET'])
def porteira_listar_regioes():
    """Lista todas as regiões disponíveis no banco."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT Regiao
            FROM resultados_leitura
            WHERE user_id = ? AND Regiao IS NOT NULL
            ORDER BY Regiao
        ''', (user['id'],))

        regioes = [row[0] for row in cursor.fetchall()]
        conn.close()

        return jsonify({'success': True, 'regioes': regioes})
    except Exception as e:
        print(f"[ERROR] Erro ao listar regiões: {e}")
        return jsonify({'success': False, 'error': 'Erro ao buscar regiões'}), 500


@app.route('/api/porteira/localidades/<regiao>', methods=['GET'])
def porteira_localidades_por_regiao(regiao):
    """
    Lista localidades de uma região, respeitando o ciclo ativo.
    Importante para que os filtros do frontend sejam consistentes.
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    ciclo = (request.args.get('ciclo') or '').strip() or None

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        from core.database import _porteira_cycle_where

        where_parts = ["user_id = ?", "Regiao = ?"]
        params = [user['id'], regiao]

        cycle_where, cycle_params = _porteira_cycle_where(ciclo, prefix="AND")
        if cycle_where:
            where_parts.append(cycle_where.replace("AND ", "", 1))
            params.extend(list(cycle_params))

        where_clause = "WHERE " + " AND ".join(where_parts)

        cursor.execute(f'''
            SELECT DISTINCT UL, Localidade
            FROM resultados_leitura
            {where_clause}
            ORDER BY UL
        ''', tuple(params))

        localidades = [{'ul': row['UL'], 'localidade': row['Localidade']} for row in cursor.fetchall()]
        conn.close()

        return jsonify({'success': True, 'regiao': regiao, 'localidades': localidades})
    except Exception as e:
        print(f"Erro ao listar localidades: {e}")
        return jsonify({'success': False, 'error': 'Erro ao buscar localidades'}), 500

# -------------------------------------------------------
# Rotas: Scheduler (Controle)
# -------------------------------------------------------
@app.route('/api/scheduler/status', methods=['GET'])
def scheduler_status():
    """Retorna o status atual do serviço de agendamento (Scheduler)."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    
    scheduler = get_scheduler()
    status = scheduler.get_status()
    return jsonify(status)

@app.route('/api/scheduler/toggle', methods=['POST'])
def scheduler_toggle():
    """
    Liga/desliga o scheduler.
    Restrito a usuários administradores (Diretoria/Gerência).
    """
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    
    user = get_user_by_id(user_id)
    if not user or user.get('role') not in ('diretoria', 'gerencia'):
        return jsonify({"error": "Apenas administradores podem controlar o scheduler"}), 403
    
    data = request.json
    action = data.get('action')
    
    scheduler = get_scheduler()
    
    if action == 'start':
        scheduler.start()
        return jsonify({"success": True, "message": "Scheduler iniciado"})
    elif action == 'stop':
        scheduler.stop()
        return jsonify({"success": True, "message": "Scheduler parado"})
    else:
        return jsonify({"error": "Ação inválida. Use 'start' ou 'stop'"}), 400

# -------------------------------------------------------
# Inicialização do App
# -------------------------------------------------------
with app.app_context():
    # Inicializa/Atualiza o schema do banco de dados
    init_db()
    # Tenta iniciar o scheduler se estiver habilitado no .env
    try:
        init_scheduler()
    except Exception as e:
        print(f"[WARN] Scheduler não iniciado: {e}")


# -------------------------------
# Releitura: Configuração de Targets
# -------------------------------
@app.route('/api/releitura/region-targets', methods=['GET', 'POST'])
def releitura_region_targets():
    """
    Gerencia o mapeamento de responsáveis por região (Quem vê o que na Releitura).
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    role = norm_role(user.get('role'))

    if role not in ('diretoria', 'gerencia', 'desenvolvedor'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403

    if request.method == 'GET':
        mapping = get_releitura_region_targets()
        out = {}
        for region, matricula in mapping.items():
            uid = get_user_id_by_matricula(matricula) if matricula else None
            out[region] = {'matricula': matricula, 'user_id': uid, 'configured': bool(uid)}
        return jsonify({'success': True, 'targets': out})

    data = request.json or {}
    mapping = data.get('regions') if isinstance(data.get('regions'), dict) else data
    cleaned = {}
    for region, matricula in (mapping or {}).items():
        if region not in ('Araxá', 'Uberaba', 'Frutal', 'Araxa'):
            continue
        rname = 'Araxá' if region == 'Araxa' else region
        cleaned[rname] = (str(matricula).strip() if matricula else None)
    set_releitura_region_targets(cleaned)
    return jsonify({'success': True, 'updated': cleaned})


# -------------------------------


# -------------------------------
# Utilitário: Teste de E-mail (SMTP)
# -------------------------------
@app.route('/api/test/email', methods=['POST'])
def api_test_email():
    """Envia um e-mail de teste para validar a configuração SMTP.

    Segurança: permitido apenas para diretoria/gerência/desenvolvedor.
    Body opcional (JSON):
        { "to": "destinatario@dominio.com" }
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401

    role = norm_role(user.get('role'))
    if role not in ('diretoria', 'gerencia', 'desenvolvedor'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403

    # Import local para evitar dependência circular e garantir que o endpoint
    # sempre tenha acesso à função (evita NameError -> 500).
    try:
        from core.email_alerts import send_test_email
    except Exception as e:
        return jsonify({'success': False, 'error': f'Falha ao carregar módulo de e-mail: {e}'}), 500

    data = request.json or {}
    to_override = (data.get('to') or '').strip() or None

    ok, msg = send_test_email(
        requested_by=str(user.get('username') or user.get('id') or ''),
        to_override=to_override,
        force=True,
    )

    if ok:
        return jsonify({'success': True, 'message': msg}), 200

    # Retorna detalhes para facilitar debug no Postman
    return jsonify({'success': False, 'error': msg}), 400


# Releitura: Itens não roteados
# -------------------------------

@app.route('/api/region-targets', methods=['GET', 'POST'])
def releitura_region_targets_alias():
    """Alias para compatibilidade com versões anteriores do frontend."""
    return releitura_region_targets()

@app.route('/api/releitura/unrouted', methods=['GET'])
def api_releitura_unrouted():
    """
    Retorna itens que não puderam ser roteados para uma região específica
    (ficam sob responsabilidade da gerência).
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    role = norm_role(user.get('role'))
    if role not in ('gerencia', 'diretoria'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    date_str = request.args.get('date')
    return jsonify({'success': True, 'items': get_releitura_unrouted(date_str)})


# -------------------------------
# Releitura: Reset Específico
# -------------------------------
@app.route('/api/releitura/reset', methods=['POST'])
def api_releitura_reset():
    """Reset apenas para o módulo de Releitura."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    role = norm_role(user.get('role'))
    if role != 'desenvolvedor':
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    reset_releitura_global()
    return jsonify({'success': True, 'message': 'Releitura zerada com sucesso'})

if __name__ == '__main__':
    # Em produção, utilize gunicorn ou similar.
    app.run(host='0.0.0.0', port=5000)
