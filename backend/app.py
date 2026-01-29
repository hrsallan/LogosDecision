import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import jwt
from datetime import datetime
from datetime import timedelta


from core.database import (
    init_db, register_user, authenticate_user, get_user_by_id,
    save_releitura_data, save_porteira_data,
    get_releitura_chart_data, get_releitura_metrics, get_releitura_details,
    get_releitura_due_chart_data, reset_database, is_file_duplicate, save_file_history,
    get_porteira_chart_data, get_porteira_metrics, reset_porteira_database,
    save_porteira_table_data, get_porteira_table_data, get_porteira_totals,
    get_porteira_chart_summary, get_porteira_nao_executadas_chart
)

SECRET_KEY = os.environ.get("JWT_SECRET", "segredo-super-seguro")

app = Flask(__name__)
CORS(app)

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
            "exp": (datetime.now(datetime.timezone.utc) + timedelta(hours=24)).timestamp()
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        return jsonify({"success": True, "token": token})
    return jsonify({"success": False, "msg": "Credenciais inválidas"}), 401

# -------------------------------------------------------
# Rotas protegidas: Sempre exigem autenticação
# -------------------------------------------------------

# Metricas para o Dashboard Geral

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
    temp_path = os.path.join(os.getcwd(), 'data', 'temp_' + file.filename)
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    file.save(temp_path)
    # Aqui você implementaria get_file_hash, deep_scan_excel etc
    file_hash = "FINGIR_HASH"
    details = []  # COLOQUE AQUI o processamento do Excel
    # Exemplo: details = deep_scan_excel(temp_path)

    if is_file_duplicate(file_hash, 'releitura', user_id):
        return jsonify({"success": False, "error": "DUPLICADO", "message": "Este relatório já foi processado anteriormente."})

    save_releitura_data(details, file_hash, user_id)
    save_file_history('releitura', len(details), file_hash, user_id)
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

    temp_path = os.path.join(os.getcwd(), 'data', 'temp_porteira_' + file.filename)
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    file.save(temp_path)
    file_hash = "FINGIR_HASH"
    details = []  # details = deep_scan_porteira_excel(temp_path)

    if is_file_duplicate(file_hash, 'porteira', user_id):
        return jsonify({"success": False, "error": "DUPLICADO", "message": "Este relatório já foi processado anteriormente."})

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
    data = get_porteira_table_data(user_id, ciclo=ciclo)
    return jsonify(data)


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
# Inicialização automática do banco se necessário
# -------------------------------------------------------
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)