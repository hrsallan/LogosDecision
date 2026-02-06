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
from core.database import (
    init_db, register_user, authenticate_user, get_user_by_id,
    list_users,
    save_releitura_data, save_porteira_data,
    get_releitura_chart_data, get_releitura_metrics, get_releitura_details,
    get_releitura_due_chart_data, reset_database, is_file_duplicate, save_file_history,
    get_porteira_chart_data, get_porteira_metrics, reset_porteira_database,
    save_porteira_table_data, get_porteira_table_data, get_porteira_totals,
    get_porteira_chart_summary, get_porteira_nao_executadas_chart,
    set_portal_credentials, get_portal_credentials, get_portal_credentials_status, clear_portal_credentials,
    get_releitura_region_targets, set_releitura_region_targets, get_user_id_by_username, get_user_id_by_matricula,
    get_releitura_unrouted, count_releitura_unrouted, reset_releitura_global
)
from core.releitura_routing_v2 import route_releituras
from core.get_metrics import get_dashboard_metrics
from core.scheduler import init_scheduler, get_scheduler

SECRET_KEY = os.environ.get("JWT_SECRET", "segredo-super-seguro")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

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
                role = role_raw
            else:
                return jsonify({
                'success': False,
                'msg': 'role privilegiado requer autenticação (Bearer token)',
                'allowed_public': sorted(list(public_roles)),
                'requested': role_raw,
                }), 403

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
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    return jsonify(get_portal_credentials_status(user_id))

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

# Metricas para o Dashboard Geral
@app.route('/api/dashboard/metrics', methods=['GET'])
def dashboard_metrics():
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401
    
    try:
        ciclo = request.args.get('ciclo')
        metrics = get_dashboard_metrics(user['id'], ciclo=ciclo)
        # Adiciona contexto útil para o frontend (sem dados sensíveis)
        metrics['viewer'] = user
        return jsonify(metrics), 200
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Erro no dashboard: {error_details}")
        return jsonify({
            "error": "Erro ao buscar métricas", 
            "detail": str(e),
            "type": type(e).__name__
        }), 500


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
    role = (user.get('role') or '').lower()

    date_str = request.args.get('date')
    region = (request.args.get('region') or 'all').strip()

    # Usuário comum: visão normal
    if role not in ('gerencia', 'diretoria', 'desenvolvedor'):
        labels, values = get_releitura_chart_data(user_id, date_str)
        metrics = get_releitura_metrics(user_id)
        due_labels, due_values = get_releitura_due_chart_data(user_id, date_str)
        details = get_releitura_details(user_id)
        try:
            unrouted_count = count_releitura_unrouted(user_id)
        except Exception:
            unrouted_count = 0
        return jsonify({
            "status": "online",
            "metrics": metrics,
            "chart": {"labels": labels, "values": values},
            "due_chart": {"labels": due_labels, "values": due_values},
            "details": details,
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
        cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph})", tuple(selected_ids))
        total=cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE'", tuple(selected_ids))
        pend=cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='CONCLUÍDA'", tuple(selected_ids))
        real=cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE' AND vencimento <> '' AND vencimento < ?", tuple(selected_ids)+(today,))
        atr=cur.fetchone()[0]
        metrics={"total":total,"pendentes":pend,"realizadas":real,"atrasadas":atr}

        # details (limit)
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
        ph2="?"
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

    # Apenas o cargo "desenvolvedor" pode zerar o banco (releituras)
    if str(user.get('role') or '').lower() != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado", "message": "Apenas desenvolvedor pode zerar o banco."}), 403

    reset_database(int(user['id']))
    return jsonify({"success": True, "message": "Banco de releituras zerado para este usuário."})

@app.route('/api/reset/porteira', methods=['POST'])
def reset_porteira():
    user = get_current_user_from_request()
    if not user:
        return jsonify({"success": False, "error": "Usuário não autenticado"}), 401

    # Apenas o cargo "desenvolvedor" pode zerar o banco (porteira)
    if str(user.get('role') or '').lower() != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado", "message": "Apenas desenvolvedor pode zerar o banco."}), 403

    reset_porteira_database(int(user['id']))
    return jsonify({"success": True, "message": "Banco de porteira zerado para este usuário."})

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
    save_porteira_table_data(details, user_id)
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

    role = (user.get('role') or '').lower()
    if role not in ('gerencia', 'diretoria', 'desenvolvedor'):
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
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    try:
        creds = get_portal_credentials(user_id)
        if not creds:
            user = get_user_by_id(user_id)
            is_admin = bool(user and (user.get("role") in ("diretoria", "gerencia")))
            if is_admin:
                env_user = (os.environ.get("PORTAL_USERNAME") or os.environ.get("PORTAL_USER") or "").strip()
                env_pass = os.environ.get("PORTAL_PASSWORD") or ""
                if env_user and env_pass:
                    creds = {"portal_user": env_user, "portal_password": env_pass}
                else:
                    return jsonify({"success": False, "error": "Admin sem credenciais do portal cadastradas. Configure em 'Área do Usuário' ou defina PORTAL_USERNAME e PORTAL_PASSWORD no .env."}), 400
            else:
                return jsonify({"success": False, "error": "Credenciais do portal não configuradas. Vá em 'Área do Usuário' e cadastre seu portal."}), 400
        downloaded_path = download_porteira_excel(portal_user=creds['portal_user'], portal_pass=creds['portal_password'])
        if not downloaded_path or not os.path.exists(downloaded_path):
            return jsonify({"success": False, "error": "Relatório não foi baixado (arquivo inexistente)."}), 500

    except Exception as e:
        return jsonify({"success": False, "error": "Falha ao baixar relatório (porteira).", "detail": str(e)}), 500

    file_hash = get_file_hash(downloaded_path)
    details = deep_scan_porteira_excel(downloaded_path)
    if details is None:
        return jsonify({"success": False, "error": "Falha ao processar o Excel baixado (porteira)."}), 400

    if is_file_duplicate(file_hash, 'porteira', user_id):
        return jsonify({"success": False, "error": "DUPLICADO", "message": "Este relatório já foi processado anteriormente."})

    save_porteira_table_data(details, user_id)
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


@app.route('/api/porteira/chart', methods=['GET'])
def porteira_chart():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    ciclo = request.args.get('ciclo')
    data = get_porteira_chart_summary(user_id, ciclo=ciclo)
    return jsonify(data)


@app.route('/api/porteira/table', methods=['GET'])
def porteira_table():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    ciclo = request.args.get('ciclo')
    rows = get_porteira_table_data(user_id, ciclo=ciclo)
    totals = get_porteira_totals(user_id, ciclo=ciclo)

    return jsonify({
        "success": True,
        "data": rows,
        "totals": totals
    })


@app.route('/api/porteira/nao-executadas-chart', methods=['GET'])
def porteira_nao_executadas_chart():
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    ciclo = request.args.get('ciclo')
    labels, values = get_porteira_nao_executadas_chart(user['id'], ciclo=ciclo)
    return jsonify({
        "labels": labels,
        "values": values
    })

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
    role = (user.get('role') or '').lower()
    if role not in ('gerencia', 'diretoria', 'desenvolvedor'):
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
    role = (user.get('role') or '').lower()
    if role not in ('gerencia', 'diretoria', 'desenvolvedor'):
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
    role = (user.get('role') or '').lower()
    if role not in ('gerencia', 'diretoria', 'desenvolvedor'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    reset_releitura_global()
    return jsonify({'success': True, 'message': 'Releitura zerada com sucesso'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
