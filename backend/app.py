from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime
from core.analytics import deep_scan_excel, get_file_hash, deep_scan_porteira_excel
from core.database import init_db, save_releitura_data, save_porteira_data, get_releitura_chart_data, get_releitura_due_chart_data, get_porteira_chart_data, get_releitura_metrics, get_porteira_metrics, get_releitura_details, is_file_duplicate, reset_database, get_porteira_table_data, get_porteira_totals, get_porteira_chart_summary, save_porteira_table_data, get_porteira_nao_executadas_chart, reset_porteira_database
from core.auth import authenticate_user, register_user
app = Flask(__name__)
CORS(app)

VERSION = "1.0.1"
init_db()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = authenticate_user(username, password)
    if user:
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False, "message": "Usuário ou senha inválidos"}), 401

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if register_user(username, password):
        return jsonify({"success": True, "message": "Usuário registrado com sucesso"})
    return jsonify({"success": False, "message": "Usuário já existe"}), 400

@app.route('/api/status/releitura', methods=['GET'])
def status_releitura():
    date_str = request.args.get('date')
    labels, values = get_releitura_chart_data(date_str)
    due_labels, due_values = get_releitura_due_chart_data(date_str)
    metrics = get_releitura_metrics()
    details = get_releitura_details()
    return jsonify({
        "status": "online",
        "version": VERSION,
        "server_time": datetime.now().strftime("%H:%M:%S"),
        "metrics": metrics,
        "chart": {"labels": labels, "values": values},
        "due_chart": {"labels": due_labels, "values": due_values},
        "details": details
    })

@app.route('/api/status/porteira', methods=['GET'])
def status_porteira():
    date_str = request.args.get('date')
    labels, values = get_porteira_chart_data(date_str)
    metrics = get_porteira_metrics()
    return jsonify({
        "status": "online",
        "version": VERSION,
        "server_time": datetime.now().strftime("%H:%M:%S"),
        "metrics": metrics,
        "chart": {"labels": labels, "values": values},
        "details": []
    })

@app.route('/api/reset', methods=['POST'])
def reset():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')

    user = authenticate_user(username, password)
    if not user or user.get('role') != 'admin':
        return jsonify({"success": False, "message": "Acesso negado."}), 403

    reset_database()
    return jsonify({"success": True, "message": "Banco de dados zerado."})


@app.route('/api/sync/releitura', methods=['POST'])
def sync_releitura_portal():
    """Baixa o relatório do portal e atualiza a Releitura (mantém upload manual)."""
    try:
        # Lazy import: scraper deps may not be installed
        from core.portal_scraper import download_releitura_excel

        # Optional overrides via querystring
        unidade_de = request.args.get('unidade_de')
        unidade_ate = request.args.get('unidade_ate')

        file_path = download_releitura_excel(unidade_de=unidade_de, unidade_ate=unidade_ate)
        file_hash = get_file_hash(file_path)

        if is_file_duplicate(file_hash, 'releitura'):
            return jsonify({
                "success": False,
                "error": "DUPLICADO",
                "message": "Este relatório (portal) já foi processado anteriormente."
            }), 200

        details = deep_scan_excel(file_path)
        if details is None:
            return jsonify({"success": False, "error": "Deep-Scan failed"}), 500

        save_releitura_data(details, file_hash)

        labels, values = get_releitura_chart_data()
        due_labels, due_values = get_releitura_due_chart_data()
        metrics = get_releitura_metrics()
        all_details = get_releitura_details()

        return jsonify({
            "success": True,
            "source": "portal",
            "downloaded_file": os.path.basename(file_path),
            "count": len(details),
            "sync_time": datetime.now().strftime("%Hh%M"),
            "metrics": metrics,
            "chart": {"labels": labels, "values": values},
            "due_chart": {"labels": due_labels, "values": due_values},
            "details": all_details
        })
    except Exception as e:
        print(f"[ERRO SYNC RELEITURA {VERSION}] {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/sync/porteira', methods=['POST'])
def sync_porteira_portal():
    """Baixa o relatório do portal e atualiza a Porteira (mantém upload manual)."""
    try:
        from core.portal_scraper import download_porteira_excel

        unidade_de = request.args.get('unidade_de')
        unidade_ate = request.args.get('unidade_ate')
        report_date = request.args.get('report_date')  # YYYY-MM-DD (opcional)

        file_path = download_porteira_excel(
            unidade_de=unidade_de,
            unidade_ate=unidade_ate,
            report_date=report_date,
        )
        file_hash = get_file_hash(file_path)

        if is_file_duplicate(file_hash, 'porteira'):
            return jsonify({
                "success": False,
                "error": "DUPLICADO",
                "message": "Este relatório (portal) já foi processado anteriormente."
            }), 200

        details = deep_scan_porteira_excel(file_path)
        if details is None:
            return jsonify({"success": False, "error": "Deep-Scan failed"}), 500

        if len(details) == 0:
            return jsonify({"success": False, "error": "Nenhum dado válido encontrado no arquivo"}), 500

        save_porteira_table_data(details)

        from core.database import save_file_history
        save_file_history('porteira', len(details), file_hash)

        # Em alguns ambientes, pós-processamentos (gráficos/consultas) podem falhar
        # mesmo com o relatório já salvo no DB. Nesses casos, retornamos sucesso
        # e deixamos a UI recarregar via /api/porteira/*.
        chart_data = {"labels": [], "datasets": []}
        labels, values = [], []
        totals = {"total_leituras": 0, "leituras_nao_exec": 0, "total_releituras": 0, "releituras_nao_exec": 0}
        warning = None
        try:
            chart_data = get_porteira_chart_summary()
            labels, values = get_porteira_nao_executadas_chart()
            totals = get_porteira_totals()
        except Exception as _e:
            warning = f"Post-processamento falhou: {_e}"

        return jsonify({
            "success": True,
            "source": "portal",
            "downloaded_file": os.path.basename(file_path),
            "count": len(details),
            "sync_time": datetime.now().strftime("%Hh%M"),
            "chart": chart_data,
            "nao_exec_chart": {"labels": labels, "values": values},
            "totals": totals,
            "warning": warning
        })

    except Exception as e:
        print(f"[ERRO SYNC PORTEIRA {VERSION}] {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload():
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({"success": False, "error": "No file"}), 400
            
        temp_path = os.path.join(os.getcwd(), 'data', 'temp_' + file.filename)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        file.save(temp_path)
        
        file_hash = get_file_hash(temp_path)
        module = request.args.get('module', 'releitura')
        
        if is_file_duplicate(file_hash, module):
            return jsonify({
                "success": False, 
                "error": "DUPLICADO", 
                "message": "Este relatorio ja foi processado anteriormente."
            }), 200
        
        details = deep_scan_excel(temp_path)
        
        if details is not None:
            if module == 'releitura':
                save_releitura_data(details, file_hash)
                labels, values = get_releitura_chart_data()
                due_labels, due_values = get_releitura_due_chart_data()
                metrics = get_releitura_metrics()
                all_details = get_releitura_details()
            else:
                save_porteira_data(details, file_hash)
                labels, values = get_porteira_chart_data()
                metrics = get_porteira_metrics()
                all_details = []

            return jsonify({
                "success": True,
                "count": len(details),
                "sync_time": datetime.now().strftime("%Hh%M"),
                "metrics": metrics,
                "chart": {"labels": labels, "values": values},
                "due_chart": {"labels": due_labels, "values": due_values},
                "details": all_details
            })
        
        return jsonify({"success": False, "error": "Deep-Scan failed"}), 500

    except Exception as e:
        print(f"[ERRO APP {VERSION}] {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/porteira/chart', methods=['GET'])
def porteira_chart():
    """Retorna dados do gráfico de barras da porteira"""
    try:
        ciclo = request.args.get('ciclo')
        data = get_porteira_chart_summary(ciclo=ciclo)
        return jsonify(data)
    except Exception as e:
        print(f"[ERRO PORTEIRA CHART] {e}")
        return jsonify({"labels": [], "datasets": []}), 500

@app.route('/api/porteira/table', methods=['GET'])
def porteira_table():
    """Retorna todos os dados da tabela de porteira"""
    try:
        ciclo = request.args.get('ciclo')
        rows = get_porteira_table_data(ciclo=ciclo)
        totals = get_porteira_totals(ciclo=ciclo)
        
        return jsonify({
            "success": True,
            "data": rows,
            "totals": totals
        })
    except Exception as e:
        print(f"[ERRO PORTEIRA TABLE] {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/porteira/nao-executadas-chart', methods=['GET'])
def porteira_nao_executadas_chart():
    """Retorna dados para o gráfico de não executadas por razão"""
    try:
        ciclo = request.args.get('ciclo')
        labels, values = get_porteira_nao_executadas_chart(ciclo=ciclo)
        return jsonify({
            "labels": labels,
            "values": values
        })
    except Exception as e:
        print(f"[ERRO PORTEIRA NÃO EXECUTADAS CHART] {e}")
        return jsonify({"labels": [], "values": []}), 500

@app.route('/api/upload/porteira', methods=['POST'])
def upload_porteira():
    """Upload de arquivo Excel para porteira"""
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({"success": False, "error": "Nenhum arquivo enviado"}), 400
        
        temp_path = os.path.join(os.getcwd(), 'data', 'temp_porteira_' + file.filename)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        file.save(temp_path)
        
        file_hash = get_file_hash(temp_path)
        
        if is_file_duplicate(file_hash, 'porteira'):
            return jsonify({
                "success": False,
                "error": "DUPLICADO",
                "message": "Este relatório já foi processado anteriormente."
            }), 200
        
        details = deep_scan_porteira_excel(temp_path)
        
        if details and len(details) > 0:
            save_porteira_table_data(details)
            
            # Salvar no histórico
            from core.database import save_file_history
            save_file_history('porteira', len(details), file_hash)
            
            chart_data = get_porteira_chart_summary()
            labels, values = get_porteira_nao_executadas_chart()
            totals = get_porteira_totals()
            
            return jsonify({
                "success": True,
                "count": len(details),
                "sync_time": datetime.now().strftime("%Hh%M"),
                "chart": chart_data,
                "nao_exec_chart": {"labels": labels, "values": values},
                "totals": totals
            })
        
        return jsonify({"success": False, "error": "Nenhum dado válido encontrado no arquivo"}), 500
        
    except Exception as e:
        print(f"[ERRO UPLOAD PORTEIRA] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/reset/porteira', methods=['POST'])
def reset_porteira():
    """Zera o banco de dados da porteira"""
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    user = authenticate_user(username, password)
    if not user or user.get('role') != 'admin':
        return jsonify({"success": False, "message": "Acesso negado. Apenas administradores."}), 403
    
    reset_porteira_database()
    return jsonify({"success": True, "message": "Banco de dados da Porteira zerado com sucesso!"})

if __name__ == '__main__':
    print(f"VigilaCore {VERSION} - Auto-Migration Active")
    app.run(host='0.0.0.0', port=5000, debug=False)