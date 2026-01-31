import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import jwt
from datetime import datetime, timedelta, timezone
from core.analytics import deep_scan_excel, deep_scan_porteira_excel, get_file_hash
from core.portal_scraper import download_releitura_excel, download_porteira_excel
from core.database import (
    init_db, register_user, authenticate_user, get_user_by_id,
    save_releitura_data, save_porteira_data,
    get_releitura_chart_data, get_releitura_metrics, get_releitura_details,
    get_releitura_due_chart_data, reset_database, is_file_duplicate, save_file_history,
    get_porteira_chart_data, get_porteira_metrics, reset_porteira_database,
    save_porteira_table_data, get_porteira_table_data, get_porteira_totals,
    get_porteira_chart_summary, get_porteira_nao_executadas_chart,
    set_portal_credentials, get_portal_credentials, get_portal_credentials_status, clear_portal_credentials
)
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

# -------------------------------------------------------
# Rotas públicas (registro, login, arquivos estáticos)
# -------------------------------------------------------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if register_user(username, password):
        return jsonify({"success": True})
    return jsonify({"success": False, "msg": "Usuário já existe"}), 409

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
    clear_portal_credentials(user_id)
    return jsonify({"success": True})

# -------------------------------------------------------
# Rotas protegidas: Sempre exigem autenticação
# -------------------------------------------------------

# Metricas para o Dashboard Geral
@app.route('/api/dashboard/metrics', methods=['GET'])
def dashboard_metrics():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    
    try:
        ciclo = request.args.get('ciclo')
        metrics = get_dashboard_metrics(user_id, ciclo=ciclo)
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
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    date_str = request.args.get('date')
    labels, values = get_releitura_chart_data(user_id, date_str)
    metrics = get_releitura_metrics(user_id)
    due_labels, due_values = get_releitura_due_chart_data(user_id, date_str)
    details = get_releitura_details(user_id)

    return jsonify({
        "status": "online",
        "metrics": metrics,
        "chart": {"labels": labels, "values": values},
        "due_chart": {"labels": due_labels, "values": due_values},
        "details": details
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
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    reset_database(user_id)
    return jsonify({"success": True, "message": "Banco de releituras zerado para este usuário."})

@app.route('/api/reset/porteira', methods=['POST'])
def reset_porteira():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    reset_porteira_database(user_id)
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

    save_releitura_data(details, file_hash, user_id)
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


    save_porteira_data(details, file_hash, user_id)
    save_file_history('porteira', len(details), file_hash, user_id)
    labels, values = get_porteira_chart_data(user_id)
    metrics = get_porteira_metrics(user_id)
    all_details = []  # normal para porteira

    return jsonify({
        "success": True,
        "metrics": metrics,
        "chart": {"labels": labels, "values": values},
        "details": all_details
    })



@app.route('/api/sync/releitura', methods=['POST'])
def sync_releitura():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    try:
        creds = get_portal_credentials(user_id)
        if not creds:
            user = get_user_by_id(user_id)
            is_admin = bool(user and (user.get("role") == "admin"))
            if is_admin:
                env_user = (os.environ.get("PORTAL_USERNAME") or os.environ.get("PORTAL_USER") or "").strip()
                env_pass = os.environ.get("PORTAL_PASSWORD") or ""
                if env_user and env_pass:
                    creds = {"portal_user": env_user, "portal_password": env_pass}
                else:
                    return jsonify({"success": False, "error": "Admin sem credenciais do portal cadastradas. Configure em 'Área do Usuário' ou defina PORTAL_USERNAME e PORTAL_PASSWORD no .env."}), 400
            else:
                return jsonify({"success": False, "error": "Credenciais do portal não configuradas. Vá em 'Área do Usuário' e cadastre seu portal."}), 400
        downloaded_path = download_releitura_excel(portal_user=creds['portal_user'], portal_pass=creds['portal_password'])
        if not downloaded_path or not os.path.exists(downloaded_path):
            return jsonify({"success": False, "error": "Relatório não foi baixado (arquivo inexistente)."}), 500

    except Exception as e:
        return jsonify({"success": False, "error": "Falha ao baixar relatório (releitura).", "detail": str(e)}), 500

    file_hash = get_file_hash(downloaded_path)
    details = deep_scan_excel(downloaded_path) or []
    if not details:
        return jsonify({"success": False, "error": "Falha ao processar o Excel baixado (releitura) ou arquivo vazio."}), 400

    if is_file_duplicate(file_hash, 'releitura', user_id):
        return jsonify({"success": False, "error": "DUPLICADO", "message": "Este relatório já foi processado anteriormente."})

    save_releitura_data(details, file_hash, user_id)
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


@app.route('/api/sync/porteira', methods=['POST'])
def sync_porteira():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    try:
        creds = get_portal_credentials(user_id)
        if not creds:
            user = get_user_by_id(user_id)
            is_admin = bool(user and (user.get("role") == "admin"))
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
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    ciclo = request.args.get('ciclo')
    labels, values = get_porteira_nao_executadas_chart(user_id, ciclo=ciclo)
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
    """Liga/desliga o scheduler (apenas admin)"""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    
    # Verificar se é admin
    user = get_user_by_id(user_id)
    if not user or user.get('role') != 'admin':
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)