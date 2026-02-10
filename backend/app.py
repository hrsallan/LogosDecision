import os
from pathlib import Path
try:
    from dotenv import load_dotenv  # type: ignore
    # Carrega variáveis do arquivo .env na raiz do projeto (VigilaCore/.env)
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
except Exception:
    # Se python-dotenv não estiver instalado, o app continua rodando
    pass
import os
import sqlite3
import unicodedata
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
    get_porteira_chart_summary, get_porteira_abertura_monthly_quantities, get_porteira_nao_executadas_chart,
    get_porteira_stats_by_region, get_current_cycle_info,
    set_portal_credentials, get_portal_credentials, get_portal_credentials_status, clear_portal_credentials,
    get_releitura_region_targets, set_releitura_region_targets, get_user_id_by_username, get_user_id_by_matricula,
    get_releitura_unrouted, count_releitura_unrouted, reset_releitura_global
)
from core.releitura_routing_v2 import route_releituras
from core.scheduler import init_scheduler, get_scheduler

SECRET_KEY = os.environ.get("JWT_SECRET", "segredo-super-seguro")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_PATH = Path(__file__).resolve().parent / 'data' / 'vigilacore.db'

app = Flask(__name__)
# CORS: o frontend costuma rodar em outra porta (ex.: Live Server 5500)
# e faz requisições com header Authorization (JWT). Se o CORS não permitir
# o header Authorization no preflight, o navegador falha com "TypeError: Failed to fetch".
CORS(
    app,
    resources={r"/api/*": {"origins": "*"}},
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)


# -------------------------------------------------------
# CORS preflight: o navegador envia OPTIONS antes de POST com Authorization.
# Se retornarmos 401/403 no OPTIONS, o browser acusa 'Failed to fetch'.
# Então respondemos 204 rapidamente e deixamos o Flask-CORS anexar headers.
# -------------------------------------------------------
@app.before_request
def _handle_preflight_options():
    if request.method == 'OPTIONS':
        return ('', 204)

# -------------------------------------------------------
# AJUDA: Funções utilitárias (autenticação JWT)
# -------------------------------------------------------
def get_user_id_from_token():
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:] # Remove "Bearer "
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return int(payload["user_id"])
    except Exception:
        return None


def get_current_user_from_request():
    """Retorna o usuário atual (id, username, role) a partir do token JWT."""
    uid = get_user_id_from_token()
    if not uid:
        return None
    return get_user_by_id(uid)


def norm_role(v: str | None) -> str:
    """Normaliza roles (lower, remove acentos e espaços)."""
    s = (v or '').strip().lower()
    if not s:
        return ''
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    s = s.replace(' ', '')
    return s

def list_all_user_ids() -> list[int]:
    """Lista todos os IDs de usuários cadastrados."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute('SELECT id FROM users')
        ids = [int(r[0]) for r in cur.fetchall() if r and r[0] is not None]
        conn.close()
        return ids
    except Exception as e:
        print(f"⚠️  Erro ao listar usuários: {e}")
        return []


@app.route('/api/register', methods=['POST'])
def register():
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
        # remove acentos (ex.: gerência -> gerencia)
        s = ''.join(
            c for c in unicodedata.normalize('NFKD', s)
            if not unicodedata.combining(c)
        )
        # tolerar espaços
        s = s.replace(' ', '')
        return s

    role_raw = _normalize_role(data.get('role'))

    # Registro público: apenas roles equivalentes a "usuário comum".
    # Roles privilegiadas só podem ser criadas por alguém autenticado (diretoria/desenvolvedor).
    public_roles = {'analistas', 'supervisor'}
    privileged_roles = {'diretoria', 'gerencia', 'desenvolvedor'}
    all_roles = public_roles | privileged_roles

    # Bootstrap: permitir criar o PRIMEIRO usuário privilegiado sem token
    def bootstrap_privileged_allowed():
        import sqlite3
        from core.database import DB_PATH
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE LOWER(role) IN ('diretoria','gerencia','desenvolvedor')")
        n = (cur.fetchone() or [0])[0]
        conn.close()
        return n == 0

    # role padrão
    if not role_raw:
        role = 'analistas'
    elif role_raw not in all_roles:
        return jsonify({
            'success': False,
            'msg': 'role inválido',
            'allowed': sorted(list(all_roles)),
        }), 400
    elif role_raw in public_roles:
        role = role_raw
    else:
        # Tentativa de criar um usuário privilegiado via /api/register
        current_user = get_current_user_from_request()
        if not current_user:
            if bootstrap_privileged_allowed():
                # Bootstrap: permite criar o primeiro usuário privilegiado sem autenticação
                role = role_raw
            else:
                return jsonify({
                'success': False,
                'msg': 'role privilegiado requer autenticação (Bearer token)',
                'allowed_public': sorted(list(public_roles)),
                'requested': role_raw,
                }), 403
        else:
            # Usuário autenticado: verificar permissão para criar usuários privilegiados
            creator_role = (current_user.get('role') or '').strip().lower()
            if creator_role in ('diretoria', 'desenvolvedor'):
                role = role_raw
            else:
                return jsonify({
                    'success': False,
                    'msg': 'Acesso negado para criar usuários com role privilegiado',
                    'allowed_public': sorted(list(public_roles)),
                    'requested': role_raw,
                }), 403

    if not username or not password:
        return jsonify({'success': False, 'msg': 'username e password são obrigatórios'}), 400

    try:
        ok = register_user(username, password, role=role, nome=nome, base=base, matricula=matricula)
    except Exception as e:
        # Erro operacional (ex.: DB locked, schema antigo, etc.)
        return jsonify({
            'success': False,
            'msg': 'Falha ao registrar usuário no banco de dados',
            'detail': f'{e.__class__.__name__}: {str(e)}'
        }), 500

    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'msg': 'Usuário já existe'}), 409

@app.route('/api/login', methods=['POST'])
def login():
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
# Rotas protegidas: Credenciais do Portal (por usuário)
# -------------------------------------------------------
@app.route('/api/user/portal-credentials', methods=['GET'])
def portal_credentials_status():
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    user_id = int(user.get('id'))
    role = norm_role(user.get('role'))

    # Por padrão, retorna o status do próprio usuário.
    status = get_portal_credentials_status(user_id)

    # Regra do projeto: a credencial do portal é requisitada/salva apenas pela gerência.
    # Para roles privilegiadas (diretoria/desenvolvedor), considera "configurado" se a
    # gerência possuir credenciais válidas.
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
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    try:
        clear_portal_credentials(int(user_id))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# -------------------------------------------------------
# Rotas protegidas: Perfil do usuário (me)
# -------------------------------------------------------
@app.get('/api/user/me')
def user_me():
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401
    return jsonify(user)



# -------------------------------------------------------
# Rotas protegidas: Sempre exigem autenticação
# -------------------------------------------------------
# RELEITURAS
# -------------------------------------------------------

# Healthcheck simples (usado pelo indicador ONLINE/OFFLINE no frontend)
@app.get('/api/ping')
def api_ping():
    return jsonify({'ok': True})

# Rotas para Releitura e Porteira
@app.route('/api/status/releitura', methods=['GET'])
def status_releitura():
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    user_id = int(user['id'])
    role = norm_role(user.get('role'))

    date_str = request.args.get('date')
    region = (request.args.get('region') or 'all').strip()

    # Usuário comum: visão normal
    if role not in ('gerencia', 'diretoria', 'desenvolvedor'):
        labels, values = get_releitura_chart_data(user_id, date_str)
        metrics = get_releitura_metrics(user_id, date_str)
        due_labels, due_values = get_releitura_due_chart_data(user_id, date_str)
        details = get_releitura_details(user_id, date_str)
        try:
            unrouted_count = count_releitura_unrouted(user_id, date_str)
        except Exception:
            unrouted_count = 0

        # Segurança: analistas/supervisor só enxergam a sua própria base/matrícula.
        # Para evitar vazamento e também evitar "cards zerados" no frontend,
        # devolvemos um resumo de região contendo SOMENTE a base do usuário.
        base_name = (user.get('base') or '').strip() or 'Minha Base'
        regions_summary = {
            base_name: {
                "configured": True,
                "total": metrics.get('total', 0) if isinstance(metrics, dict) else 0,
                "pendentes": metrics.get('pendentes', 0) if isinstance(metrics, dict) else 0,
                "realizadas": metrics.get('realizadas', 0) if isinstance(metrics, dict) else 0,
                "atrasadas": metrics.get('atrasadas', 0) if isinstance(metrics, dict) else 0,
            }
        }
        return jsonify({
            "status": "online",
            "metrics": metrics,
            "chart": {"labels": labels, "values": values},
            "due_chart": {"labels": due_labels, "values": due_values},
            "details": details,
            "regions": regions_summary,
            "unrouted_count": unrouted_count
        })

    # Gerência/Diretoria: agregação por targets + gerente (unrouted)
    targets = get_releitura_region_targets()
    print(f"[DEBUG Releitura] Targets configurados: {targets}")
    
    region_user_ids = {}
    for rname in ('Araxá','Uberaba','Frutal'):
        matricula = targets.get(rname)
        uid = get_user_id_by_matricula(matricula) if matricula else None
        print(f"[DEBUG Releitura] Região {rname} -> Matrícula: {matricula} -> User ID: {uid}")
        region_user_ids[rname]=uid

    manager_username = (os.environ.get("RELEITURA_MANAGER_USERNAME") or "GRTRI").strip()
    manager_id = get_user_id_by_username(manager_username) or user_id
    print(f"[DEBUG Releitura] Manager: {manager_username} -> ID: {manager_id}")

    def agg_chart(fn):
        # fn(user_id, date_str) -> (labels, values)
        combined = {}
        for rname, uid in region_user_ids.items():
            if not uid: 
                continue
            if region != 'all' and region != rname:
                continue
            labs, vals = fn(uid, date_str)
            for l,v in zip(labs, vals):
                combined[l]=combined.get(l,0)+v
        # NOTE: Manager NÃO é incluído aqui para evitar contagem duplicada
        # Manager possui registros UNROUTED que não devem ser somados com as regiões
        labels_sorted = sorted(combined.keys())
        return labels_sorted, [combined[k] for k in labels_sorted]

    # Metrics: sum across selected user_ids + manager
    import sqlite3
    from core.database import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    selected_ids=[]
    if region=='all':
        selected_ids=[uid for uid in region_user_ids.values() if uid]
    else:
        selected_ids=[region_user_ids.get(region)] if region_user_ids.get(region) else []
    # NOTE: manager_id NÃO é incluído aqui para evitar contagem duplicada
    # Manager só contabiliza registros UNROUTED (consulta separada nas linhas 424-428)

    if not selected_ids:
        metrics={"total":0,"pendentes":0,"realizadas":0,"atrasadas":0}
        labels, values = [], []
        due_labels, due_values = [], []
        details=[]
    else:
        ph=",".join(["?"]*len(selected_ids))
        # total/pendentes/realizadas/atrasadas (atrasadas: vencimento < hoje e status PENDENTE)
        today=datetime.now().strftime("%d/%m/%Y")
        
        # Aplicar filtro de data se fornecido
        if date_str:
            # Com filtro de data
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND DATE(upload_time)=DATE(?)", tuple(selected_ids)+(date_str,))
            total=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE' AND DATE(upload_time)=DATE(?)", tuple(selected_ids)+(date_str,))
            pend=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='CONCLUÍDA' AND DATE(upload_time)=DATE(?)", tuple(selected_ids)+(date_str,))
            real=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE' AND vencimento <> '' AND vencimento < ? AND DATE(upload_time)=DATE(?)", tuple(selected_ids)+(today,date_str))
            atr=cur.fetchone()[0]
            metrics={"total":total,"pendentes":pend,"realizadas":real,"atrasadas":atr}

            # details (limit) com filtro de data
            cur.execute(f"SELECT status, ul, instalacao, endereco, razao, vencimento, reg, upload_time, region, route_status, route_reason, ul_regional, localidade FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE' AND DATE(upload_time)=DATE(?) ORDER BY upload_time DESC LIMIT 500", tuple(selected_ids)+(date_str,))
        else:
            # Sem filtro de data (comportamento original)
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph})", tuple(selected_ids))
            total=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE'", tuple(selected_ids))
            pend=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='CONCLUÍDA'", tuple(selected_ids))
            real=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE' AND vencimento <> '' AND vencimento < ?", tuple(selected_ids)+(today,))
            atr=cur.fetchone()[0]
            metrics={"total":total,"pendentes":pend,"realizadas":real,"atrasadas":atr}

            # details (limit) sem filtro de data
            cur.execute(f"SELECT status, ul, instalacao, endereco, razao, vencimento, reg, upload_time, region, route_status, route_reason, ul_regional, localidade FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE' ORDER BY upload_time DESC LIMIT 500", tuple(selected_ids))
        
        rows=cur.fetchall()
        details=[{
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

        labels, values = agg_chart(get_releitura_chart_data)
        due_labels, due_values = agg_chart(get_releitura_due_chart_data)

    conn.close()

    # Summary por região (cards)
    regions_summary={}
    for rname, uid in region_user_ids.items():
        if not uid:
            print(f"[DEBUG Releitura] Região {rname} não configurada (uid=None)")
            regions_summary[rname]={"configured":False,"total":0,"pendentes":0,"realizadas":0,"atrasadas":0}
            continue
        
        print(f"[DEBUG Releitura] Calculando métricas para {rname} (uid={uid})")
        cur2 = sqlite3.connect(str(DB_PATH)).cursor()
        
        # Aplicar filtro de data se fornecido
        if date_str:
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND DATE(upload_time)=DATE(?)", (uid, date_str))
            t=cur2.fetchone()[0]
            print(f"[DEBUG Releitura]   {rname} Total: {t}")
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='PENDENTE' AND DATE(upload_time)=DATE(?)", (uid, date_str))
            p=cur2.fetchone()[0]
            print(f"[DEBUG Releitura]   {rname} Pendentes: {p}")
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='CONCLUÍDA' AND DATE(upload_time)=DATE(?)", (uid, date_str))
            rd=cur2.fetchone()[0]
            print(f"[DEBUG Releitura]   {rname} Realizadas: {rd}")
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='PENDENTE' AND vencimento <> '' AND vencimento < ? AND DATE(upload_time)=DATE(?)", (uid, today, date_str))
            a=cur2.fetchone()[0]
            print(f"[DEBUG Releitura]   {rname} Atrasadas: {a}")
        else:
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=?", (uid,))
            t=cur2.fetchone()[0]
            print(f"[DEBUG Releitura]   {rname} Total: {t}")
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='PENDENTE'", (uid,))
            p=cur2.fetchone()[0]
            print(f"[DEBUG Releitura]   {rname} Pendentes: {p}")
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='CONCLUÍDA'", (uid,))
            rd=cur2.fetchone()[0]
            print(f"[DEBUG Releitura]   {rname} Realizadas: {rd}")
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='PENDENTE' AND vencimento <> '' AND vencimento < ?", (uid, today))
            a=cur2.fetchone()[0]
            print(f"[DEBUG Releitura]   {rname} Atrasadas: {a}")
        
        cur2.connection.close()
        regions_summary[rname]={"configured":True,"total":t,"pendentes":p,"realizadas":rd,"atrasadas":a}

    # unrouted count for manager
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    if date_str:
        cur.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND route_status='UNROUTED' AND DATE(upload_time)=DATE(?)", (manager_id, date_str))
    else:
        cur.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND route_status='UNROUTED'", (manager_id,))
    unrouted_count=cur.fetchone()[0]
    conn.close()

    print(f"[DEBUG Releitura] Resumo final das regiões: {regions_summary}")
    print(f"[DEBUG Releitura] Não roteados (manager): {unrouted_count}")

    return jsonify({
        "status":"online",
        "metrics":metrics,
        "chart":{"labels":labels,"values":values},
        "due_chart":{"labels":due_labels,"values":due_values},
        "details":details,
        "regions":regions_summary,
        "unrouted_count":unrouted_count
    })


@app.route('/api/status/porteira', methods=['GET'])
def status_porteira():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    date_str = request.args.get('date')
    labels, values = get_porteira_chart_data(user_id, date_str)
    metrics = get_porteira_metrics(user_id)
    # No details para porteira
    return jsonify({
        "status": "online",
        "chart": {"labels": labels, "values": values},
        "metrics": metrics,
        "details": []
    })

@app.route('/api/reset', methods=['POST'])
def reset():
    user = get_current_user_from_request()
    if not user:
        return jsonify({"success": False, "error": "Usuário não autenticado"}), 401

    # Somente desenvolvedor pode zerar o banco (global)
    if norm_role(user.get('role')) != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    reset_releitura_global()
    return jsonify({"success": True, "message": "Banco de releituras zerado (GLOBAL)."})

@app.route('/api/reset/porteira', methods=['POST'])
def reset_porteira():
    user = get_current_user_from_request()
    if not user:
        return jsonify({"success": False, "error": "Usuário não autenticado"}), 401

    # Somente desenvolvedor pode zerar o banco (global)
    if norm_role(user.get('role')) != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    reset_porteira_global()
    return jsonify({"success": True, "message": "Banco de porteira zerado (GLOBAL)."})

@app.route('/api/upload', methods=['POST'])
def upload_releitura():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    file = request.files.get('file')
    if not file:
        return jsonify({"success": False, "error": "Arquivo não enviado"}), 400

    # Salve o arquivo temporário, calcule hash e processe como no seu código
    temp_path = os.path.join(DATA_DIR, 'temp_' + file.filename)
    os.makedirs(DATA_DIR, exist_ok=True)
    file.save(temp_path)
    # Aqui você implementaria get_file_hash, deep_scan_excel etc
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

    # Porteira usa a tabela resultados_leitura
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




@app.route('/api/sync/releitura', methods=['POST'])
def sync_releitura():
    # Somente roles privilegiadas podem acionar o sync manual (teste)
    user = get_current_user_from_request()
    if not user:
        return jsonify({"success": False, "error": "Usuário não autenticado"}), 401

    role = norm_role(user.get('role'))
    if role != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    try:
        # Sempre usar o login do gerente (conforme solicitado)
        manager_username = (os.environ.get("RELEITURA_MANAGER_USERNAME") or "GRTRI").strip()
        manager_id = get_user_id_by_username(manager_username) or int(user['id'])

        creds = get_portal_credentials(manager_id)
        if not creds:
            return jsonify({
                "success": False,
                "error": f"Credenciais do portal não configuradas para o gerente '{manager_username}'. Cadastre em 'Área do Usuário' (logado como {manager_username})."
            }), 400

        downloaded_path = download_releitura_excel(portal_user=creds['portal_user'], portal_pass=creds['portal_password'])
        if not downloaded_path or not os.path.exists(downloaded_path):
            return jsonify({"success": False, "error": "Relatório não foi baixado (arquivo inexistente)."}), 500

    except Exception as e:
        return jsonify({"success": False, "error": "Falha ao baixar relatório (releitura).", "detail": str(e)}), 500

    file_hash = get_file_hash(downloaded_path)
    details = deep_scan_excel(downloaded_path) or []
    if not details:
        return jsonify({"success": False, "error": "Falha ao processar o Excel baixado (releitura) ou arquivo vazio."}), 400

    # Roteamento V2
    try:
        # details_v2 terá ul_regional e localidade
        details_v2 = route_releituras(details)
        # Re-encapsula no objeto que a lógica abaixo espera (compatibilidade)
        from dataclasses import dataclass
        @dataclass
        class LegacyRouted:
            routed: dict
            unrouted: list
        
        # Filtra por região para o loop original
        routed_map = {"Araxá": [], "Uberaba": [], "Frutal": []}
        unrouted_list = []
        for it in details_v2:
            reg = it.get("region")
            if it.get("route_status") == "ROUTED" and reg in routed_map:
                routed_map[reg].append(it)
            else:
                unrouted_list.append(it)
        
        routed = LegacyRouted(routed=routed_map, unrouted=unrouted_list)
        targets = get_releitura_region_targets()  # {Araxá: MAT_..., ...}

        summary = {
            "Araxá": {"saved": 0, "user_id": None, "matricula": targets.get("Araxá"), "status": "OK"},
            "Uberaba": {"saved": 0, "user_id": None, "matricula": targets.get("Uberaba"), "status": "OK"},
            "Frutal": {"saved": 0, "user_id": None, "matricula": targets.get("Frutal"), "status": "OK"},
            "unrouted_saved": 0
        }

        # Salva os roteados por região (se não houver matrícula configurada, cai no gerente como UNROUTED)
        for region, items in routed.routed.items():
            matricula = targets.get(region)
            uid = get_user_id_by_matricula(matricula) if matricula else None
            summary[region]["user_id"] = uid

            if not items:
                continue

            if uid:
                # Evita duplicar exatamente o mesmo arquivo para o mesmo usuário
                if is_file_duplicate(file_hash, 'releitura', uid):
                    summary[region]["status"] = "DUPLICADO"
                    continue
                save_releitura_data(items, file_hash, uid)
                summary[region]["saved"] = len(items)
            else:
                # sem matrícula configurada: registra como não roteado no gerente (para auditoria)
                for it in items:
                    it["route_status"] = "UNROUTED"
                    it["route_reason"] = "REGIAO_SEM_MATRICULA"
                    it["region"] = region

                if not is_file_duplicate(file_hash, 'releitura', manager_id):
                    save_releitura_data(items, file_hash, manager_id)
                    summary[region]["status"] = "UNROUTED_TO_MANAGER"
                else:
                    summary[region]["status"] = "DUPLICADO"

        # Salva os não roteados (UL inválida/desconhecida) no gerente
        if routed.unrouted:
            if not is_file_duplicate(file_hash, 'releitura', manager_id):
                save_releitura_data(routed.unrouted, file_hash, manager_id)
                summary["unrouted_saved"] = len(routed.unrouted)
            else:
                # já foi processado por gerente
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
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    if norm_role(user.get('role')) != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    user_id = int(user['id'])

    try:
        # Regra do projeto: credenciais do portal ficam na GERÊNCIA.
        manager_username = (os.environ.get("RELEITURA_MANAGER_USERNAME") or "GRTRI").strip()
        manager_id = get_user_id_by_username(manager_username) or None
        creds = get_portal_credentials(manager_id) if manager_id else None
        if not creds:
            return jsonify({
                "success": False,
                "error": f"Credenciais do portal não configuradas para o gerente '{manager_username}'. Cadastre em 'Área do Usuário' (logado como {manager_username})."
            }), 400
        downloaded_path = download_porteira_excel(portal_user=creds['portal_user'], portal_pass=creds['portal_password'])
        if not downloaded_path or not os.path.exists(downloaded_path):
            return jsonify({"success": False, "error": "Relatório não foi baixado (arquivo inexistente)."}), 500

    except Exception as e:
        return jsonify({"success": False, "error": "Falha ao baixar relatório (porteira).", "detail": str(e)}), 500

    file_hash = get_file_hash(downloaded_path)
    details = deep_scan_porteira_excel(downloaded_path)
    if details is None:
        return jsonify({"success": False, "error": "Falha ao processar o Excel baixado (porteira)."}), 400

    # Se o dev rodar o sync, não queremos duplicar para quem já processou.
    if is_file_duplicate(file_hash, 'porteira', user_id):
        return jsonify({"success": False, "error": "DUPLICADO", "message": "Este relatório já foi processado anteriormente."})

    # Porteira usa a tabela resultados_leitura. Distribui para todos para que cada
    # usuário veja apenas o que é permitido (sigilo aplicado em save_porteira_table_data).
    for _uid in list_all_user_ids():
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


@app.route('/api/porteira/chart', methods=['GET'])
def porteira_chart():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    ciclo = request.args.get('ciclo')
    regiao = request.args.get('regiao')
    data = get_porteira_chart_summary(user_id, ciclo=ciclo, regiao=regiao)
    return jsonify(data)


@app.route('/api/porteira/current-cycle', methods=['GET'])
def porteira_current_cycle():
    """Retorna informações do ciclo atual baseado no mês."""
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
    """Retorna dados para a tabela 'Abertura de Porteira' (Mês Atual vs Mês Anterior)."""
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

    def build_month_payload(y: int, m: int, is_current_month: bool = False):
        # Se não existir histórico para o mês atual, calcula direto do snapshot atual
        quantities = get_porteira_abertura_monthly_quantities(
            int(user_id), int(y), int(m),
            ciclo=ciclo, regiao=regiao,
            fallback_latest=bool(is_current_month)
        )

        # Primeiro calcula os valores e decide se o mês tem dados.
        temp_rows = []
        total_osb = 0
        total_cnv = 0
        total_qtd = 0
        total_atraso = 0

        today = now.date()
        for r in range(1, 19):
            due = get_due_date(int(y), int(m), int(r))
            data_str = due.strftime('%d/%m/%Y') if due else '--/--'

            key = f"{r:02d}"
            raw = quantities.get(key) or {}
            osb = int(round(float(raw.get("osb", 0) or 0)))
            cnv = int(round(float(raw.get("cnv", 0) or 0)))
            qtd = int(round(float(raw.get("quantidade", 0) or 0)))

            # Atraso só conta quando há pendência (quantidade total > 0)
            # Atraso (binário):
            # - Se houver pendência (qtd > 0), marca 1 quando a data de referência já passou.
            # - Para evitar falso '0' quando a data não for encontrada no calendário,
            #   assumimos atraso = 1 se qtd > 0 e não há data (due is None).
            if qtd > 0: 
                if due:
                    atraso = 1 if (today > due) else 0
                else:
                     # Sem data de referência no calendário: mantém como atrasado para não mascarar pendências.
                    atraso = 1
            else:
                atraso = 0

            total_osb += osb
            total_cnv += cnv
            total_qtd += qtd
            total_atraso += atraso
            temp_rows.append((r, data_str, osb, cnv, qtd, atraso))

        has_data = bool(total_qtd > 0)

        rows = []
        for (r, data_str, osb, cnv, qtd, atraso) in temp_rows:
            rows.append({
                'razao': f'RZ {r:02d}',
                'data': data_str,
                # Regra:
                # - se o mês tem dados: zeros aparecem como 0
                # - se o mês não tem dados (sem histórico): lacuna (null)
                'osb': (int(osb) if has_data else None),
                'cnv': (int(cnv) if has_data else None),
                'quantidade': (int(qtd) if has_data else None),
                # Se quantidade = 0 => atraso = 0 (e deve aparecer 0 quando o mês tem dados)
                'atraso': (int(atraso) if has_data else None),
            })

        return {
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

    current_payload = build_month_payload(cur_year, cur_month, is_current_month=True)
    previous_payload = build_month_payload(prev_year, prev_month, is_current_month=False)

    return jsonify({
        'success': True,
        'current': current_payload,
        'previous': previous_payload
    })

@app.route('/api/porteira/nao-executadas-chart', methods=['GET'])
def porteira_nao_executadas_chart():
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
    """Retorna estatísticas agregadas por região (Araxa, Uberaba, Frutal)."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    ciclo = request.args.get('ciclo')
    regiao = request.args.get('regiao')

    try:
        stats = get_porteira_stats_by_region(user['id'], ciclo=ciclo, regiao=regiao)
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        print(f"Erro ao buscar estatísticas por região: {e}")
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
        print(f"Erro ao listar regiões: {e}")
        return jsonify({'success': False, 'error': 'Erro ao buscar regiões'}), 500


@app.route('/api/porteira/localidades/<regiao>', methods=['GET'])
def porteira_localidades_por_regiao(regiao):
    """Lista todas as localidades de uma região específica."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    # IMPORTANTE:
    # O dropdown de UL/Localidade precisa respeitar o filtro de ciclo (97/98/99)
    # exatamente como a tabela e os gráficos. Caso contrário, aparecem ULs "fora do ciclo"
    # no seletor, gerando inconsistência visual e de análise.
    ciclo = (request.args.get('ciclo') or '').strip() or None

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Reaproveita a mesma regra de ciclo aplicada em core.database._porteira_cycle_where
        # (urbano 01..88 sempre + rurais por ciclo).
        from core.database import _porteira_cycle_where  # lazy import para evitar circular

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
# Endpoint do Scheduler
# -------------------------------------------------------
@app.route('/api/scheduler/status', methods=['GET'])
def scheduler_status():
    """Retorna status do scheduler automático"""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    
    scheduler = get_scheduler()
    status = scheduler.get_status()
    return jsonify(status)

@app.route('/api/scheduler/toggle', methods=['POST'])
def scheduler_toggle():
    """Liga/desliga o scheduler (apenas diretoria/gerência)"""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    
    # Verificar se é diretoria/gerência
    user = get_user_by_id(user_id)
    if not user or user.get('role') not in ('diretoria', 'gerencia'):
        return jsonify({"error": "Apenas administradores podem controlar o scheduler"}), 403
    
    data = request.json
    action = data.get('action')  # 'start' ou 'stop'
    
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
# Inicialização automática do banco se necessário
# -------------------------------------------------------
with app.app_context():
    init_db()
    # Inicializar scheduler automático
    try:
        init_scheduler()
    except Exception as e:
        print(f"⚠️ Scheduler não iniciado: {e}")


# -------------------------------
# Releitura: targets por região
# -------------------------------
@app.route('/api/releitura/region-targets', methods=['GET', 'POST'])
def releitura_region_targets():
    user = get_current_user_from_request()
    if not user:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    role = norm_role(user.get('role'))
    # Configuração global de alvos por região (mapeia região -> matrícula/base).
    # É uma configuração administrativa usada para roteamento/visibilidade de métricas.
    # Diretoria e Gerência precisam conseguir atualizar, e Desenvolvedor mantém acesso
    # para suporte/testes.
    if role not in ('diretoria', 'gerencia', 'desenvolvedor'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403

    if request.method == 'GET':
        mapping = get_releitura_region_targets()
        # resolve user_ids
        out = {}
        for region, matricula in mapping.items():
            uid = get_user_id_by_matricula(matricula) if matricula else None
            out[region] = {'matricula': matricula, 'user_id': uid, 'configured': bool(uid)}
        return jsonify({'success': True, 'targets': out})

    data = request.json or {}
    # accept either {region: matricula} or {"regions": {...}}
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
# Releitura: não roteados (gerência)
# -------------------------------

# Alias de compatibilidade (frontend antigo)
@app.route('/api/region-targets', methods=['GET', 'POST'])
def releitura_region_targets_alias():
    return releitura_region_targets()

@app.route('/api/releitura/unrouted', methods=['GET'])
def api_releitura_unrouted():
    user = get_current_user_from_request()
    if not user:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    role = norm_role(user.get('role'))
    if role not in ('gerencia', 'diretoria'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    date_str = request.args.get('date')
    return jsonify({'success': True, 'items': get_releitura_unrouted(date_str)})


# -------------------------------
# Releitura: reset (somente releitura)
# -------------------------------
@app.route('/api/releitura/reset', methods=['POST'])
def api_releitura_reset():
    user = get_current_user_from_request()
    if not user:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    role = norm_role(user.get('role'))
    # Somente DESENVOLVEDOR pode zerar o banco
    if role != 'desenvolvedor':
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    reset_releitura_global()
    return jsonify({'success': True, 'message': 'Releitura zerada com sucesso'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)