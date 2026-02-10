"""
Módulo Principal da Aplicação VigilaCore (Backend)

Este arquivo inicializa a aplicação Flask, configura as rotas da API, gerencia
a autenticação, processa uploads de arquivos e coordena a lógica de negócios
entre o frontend e o banco de dados.

Responsabilidades principais:
1. Configuração do Flask e CORS.
2. Autenticação de usuários (Login/Registro) via JWT.
3. Rotas para upload e processamento de arquivos Excel (Releitura e Porteira).
4. Rotas para consulta de métricas, gráficos e tabelas.
5. Integração com o Scheduler para tarefas automáticas.
"""

import os
from pathlib import Path

# Tentativa de carregar variáveis de ambiente do arquivo .env
try:
    from dotenv import load_dotenv  # type: ignore
    # Carrega variáveis do arquivo .env na raiz do projeto (VigilaCore/.env)
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
except Exception:
    # Se python-dotenv não estiver instalado, o app continua rodando com variáveis do sistema
    pass

import os
import sqlite3
import unicodedata
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import jwt
from datetime import datetime, timedelta, timezone

# Importações dos módulos do núcleo (Core)
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

# Configuração da chave secreta para JWT
SECRET_KEY = os.environ.get("JWT_SECRET", "segredo-super-seguro")

# Configuração de caminhos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_PATH = Path(__file__).resolve().parent / 'data' / 'vigilacore.db'

# Inicialização do Flask
app = Flask(__name__)

# Configuração do CORS (Cross-Origin Resource Sharing)
# Permite que o frontend (geralmente em outra porta/domínio) acesse a API.
# Expondo headers necessários para autenticação JWT.
CORS(
    app,
    resources={r"/api/*": {"origins": "*"}},
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)


# -------------------------------------------------------
# Tratamento de Preflight CORS
# -------------------------------------------------------
@app.before_request
def _handle_preflight_options():
    """
    Responde rapidamente a requisições OPTIONS (preflight CORS).
    Se retornarmos 401/403 no OPTIONS, o browser acusa 'Failed to fetch'.
    Retorna 204 (No Content) e deixa o Flask-CORS anexar os headers.
    """
    if request.method == 'OPTIONS':
        return ('', 204)

# -------------------------------------------------------
# Funções Utilitárias: Autenticação JWT
# -------------------------------------------------------
def get_user_id_from_token():
    """
    Extrai o ID do usuário do token JWT presente no cabeçalho Authorization.
    Retorna None se o token for inválido ou ausente.
    """
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
    """
    Retorna o objeto do usuário atual (id, username, role) a partir do token JWT.
    Busca os detalhes completos no banco de dados.
    """
    uid = get_user_id_from_token()
    if not uid:
        return None
    return get_user_by_id(uid)


def norm_role(v: str | None) -> str:
    """
    Normaliza o nome da role (cargo) do usuário.
    Converte para minúsculas, remove acentos e espaços.
    Ex: 'Gerência' -> 'gerencia'.
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
    Útil para operações em lote (ex: distribuir dados para todos).
    """
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


# -------------------------------------------------------
# Rotas de Autenticação
# -------------------------------------------------------
@app.route('/api/register', methods=['POST'])
def register():
    """
    Rota para registro de novos usuários.
    Valida permissões para criação de usuários privilegiados (Gerência/Diretoria).
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
        # remove acentos (ex.: gerência -> gerencia)
        s = ''.join(
            c for c in unicodedata.normalize('NFKD', s)
            if not unicodedata.combining(c)
        )
        # tolerar espaços
        s = s.replace(' ', '')
        return s

    role_raw = _normalize_role(data.get('role'))

    # Definição de níveis de acesso
    public_roles = {'analistas', 'supervisor'}
    privileged_roles = {'diretoria', 'gerencia', 'desenvolvedor'}
    all_roles = public_roles | privileged_roles

    # Bootstrap: verifica se é o primeiro usuário privilegiado (instalação inicial)
    def bootstrap_privileged_allowed():
        import sqlite3
        from core.database import DB_PATH
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE LOWER(role) IN ('diretoria','gerencia','desenvolvedor')")
        n = (cur.fetchone() or [0])[0]
        conn.close()
        return n == 0

    # Lógica de validação de role
    if not role_raw:
        role = 'analistas' # Padrão
    elif role_raw not in all_roles:
        return jsonify({
            'success': False,
            'msg': 'role inválido',
            'allowed': sorted(list(all_roles)),
        }), 400
    elif role_raw in public_roles:
        role = role_raw
    else:
        # Tentativa de criar um usuário privilegiado
        current_user = get_current_user_from_request()
        if not current_user:
            if bootstrap_privileged_allowed():
                # Permite criar o primeiro admin sem estar logado
                role = role_raw
            else:
                return jsonify({
                'success': False,
                'msg': 'role privilegiado requer autenticação (Bearer token)',
                'allowed_public': sorted(list(public_roles)),
                'requested': role_raw,
                }), 403
        else:
            # Usuário autenticado: verificar se pode criar outros admins
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
        # Erro operacional (ex.: banco travado)
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
    """
    Rota de login.
    Autentica credenciais e retorna um token JWT válido por 24 horas.
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
# Rotas Protegidas: Credenciais do Portal SGL
# -------------------------------------------------------
@app.route('/api/user/portal-credentials', methods=['GET'])
def portal_credentials_status():
    """
    Verifica o status das credenciais do Portal CEMIG SGL.
    Para diretoria/desenvolvedor, verifica se a gerência possui credenciais configuradas.
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    user_id = int(user.get('id'))
    role = norm_role(user.get('role'))

    # Status do próprio usuário
    status = get_portal_credentials_status(user_id)

    # Regra de negócio: Credencial é centralizada na Gerência.
    # Se o usuário for diretoria/dev e não tiver credencial própria, usa a do gerente.
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
    """
    Salva ou atualiza as credenciais do Portal SGL para o usuário atual.
    """
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
    """
    Remove as credenciais do Portal SGL do usuário atual.
    """
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    try:
        clear_portal_credentials(int(user_id))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# -------------------------------------------------------
# Rotas Protegidas: Perfil do Usuário
# -------------------------------------------------------
@app.get('/api/user/me')
def user_me():
    """Retorna os dados do usuário logado."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401
    return jsonify(user)



# -------------------------------------------------------
# Rotas de Negócio: Releitura e Porteira
# -------------------------------------------------------

# Healthcheck
@app.get('/api/ping')
def api_ping():
    """Endpoint simples para verificar se a API está online."""
    return jsonify({'ok': True})

@app.route('/api/status/releitura', methods=['GET'])
def status_releitura():
    """
    Retorna métricas, gráficos e detalhes sobre Releituras.

    Lógica diferenciada por perfil:
    - Analistas/Supervisores: Veem apenas seus dados (isolamento).
    - Gerência/Diretoria/Dev: Veem dados agregados por região (roteamento).

    Args:
        region (query param): Filtro de região ('Araxá', 'Uberaba', 'Frutal', 'all').
        date (query param): Data específica para consulta (opcional).
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    user_id = int(user['id'])
    role = norm_role(user.get('role'))

    date_str = request.args.get('date')
    region = (request.args.get('region') or 'all').strip()

    # Perfil Comum: Visão limitada à própria base
    if role not in ('gerencia', 'diretoria', 'desenvolvedor'):
        labels, values = get_releitura_chart_data(user_id, date_str)
        metrics = get_releitura_metrics(user_id, date_str)
        due_labels, due_values = get_releitura_due_chart_data(user_id, date_str)
        details = get_releitura_details(user_id, date_str)
        try:
            unrouted_count = count_releitura_unrouted(user_id, date_str)
        except Exception:
            unrouted_count = 0

        # Resumo da região do usuário para exibição no frontend
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

    # Perfil Gerencial: Agregação de dados de múltiplos usuários (targets)
    targets = get_releitura_region_targets()
    print(f"[DEBUG Releitura] Targets configurados: {targets}")
    
    # Mapeia Região -> ID do Usuário Responsável
    region_user_ids = {}
    for rname in ('Araxá','Uberaba','Frutal'):
        matricula = targets.get(rname)
        uid = get_user_id_by_matricula(matricula) if matricula else None
        print(f"[DEBUG Releitura] Região {rname} -> Matrícula: {matricula} -> User ID: {uid}")
        region_user_ids[rname]=uid

    manager_username = (os.environ.get("RELEITURA_MANAGER_USERNAME") or "GRTRI").strip()
    manager_id = get_user_id_by_username(manager_username) or user_id
    print(f"[DEBUG Releitura] Manager: {manager_username} -> ID: {manager_id}")

    # Função auxiliar para agregar dados de gráficos
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

        labels_sorted = sorted(combined.keys())
        return labels_sorted, [combined[k] for k in labels_sorted]

    # Conecta ao banco para agregação de métricas
    import sqlite3
    from core.database import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    selected_ids=[]
    if region=='all':
        selected_ids=[uid for uid in region_user_ids.values() if uid]
    else:
        selected_ids=[region_user_ids.get(region)] if region_user_ids.get(region) else []

    # Manager não entra aqui, pois ele detém apenas os não-roteados (consulta separada)

    if not selected_ids:
        metrics={"total":0,"pendentes":0,"realizadas":0,"atrasadas":0}
        labels, values = [], []
        due_labels, due_values = [], []
        details=[]
    else:
        ph=",".join(["?"]*len(selected_ids))
        today=datetime.now().strftime("%d/%m/%Y")
        
        # Consultas SQL com filtro de data opcional
        if date_str:
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND DATE(upload_time)=DATE(?)", tuple(selected_ids)+(date_str,))
            total=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE' AND DATE(upload_time)=DATE(?)", tuple(selected_ids)+(date_str,))
            pend=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='CONCLUÍDA' AND DATE(upload_time)=DATE(?)", tuple(selected_ids)+(date_str,))
            real=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE' AND vencimento <> '' AND vencimento < ? AND DATE(upload_time)=DATE(?)", tuple(selected_ids)+(today,date_str))
            atr=cur.fetchone()[0]
            metrics={"total":total,"pendentes":pend,"realizadas":real,"atrasadas":atr}

            cur.execute(f"SELECT status, ul, instalacao, endereco, razao, vencimento, reg, upload_time, region, route_status, route_reason, ul_regional, localidade FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE' AND DATE(upload_time)=DATE(?) ORDER BY upload_time DESC LIMIT 500", tuple(selected_ids)+(date_str,))
        else:
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph})", tuple(selected_ids))
            total=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE'", tuple(selected_ids))
            pend=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='CONCLUÍDA'", tuple(selected_ids))
            real=cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM releituras WHERE user_id IN ({ph}) AND status='PENDENTE' AND vencimento <> '' AND vencimento < ?", tuple(selected_ids)+(today,))
            atr=cur.fetchone()[0]
            metrics={"total":total,"pendentes":pend,"realizadas":real,"atrasadas":atr}

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

    # Calcula resumo individual por região para os cards do dashboard
    regions_summary={}
    for rname, uid in region_user_ids.items():
        if not uid:
            print(f"[DEBUG Releitura] Região {rname} não configurada (uid=None)")
            regions_summary[rname]={"configured":False,"total":0,"pendentes":0,"realizadas":0,"atrasadas":0}
            continue
        
        cur2 = sqlite3.connect(str(DB_PATH)).cursor()
        
        if date_str:
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND DATE(upload_time)=DATE(?)", (uid, date_str))
            t=cur2.fetchone()[0]
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='PENDENTE' AND DATE(upload_time)=DATE(?)", (uid, date_str))
            p=cur2.fetchone()[0]
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='CONCLUÍDA' AND DATE(upload_time)=DATE(?)", (uid, date_str))
            rd=cur2.fetchone()[0]
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='PENDENTE' AND vencimento <> '' AND vencimento < ? AND DATE(upload_time)=DATE(?)", (uid, today, date_str))
            a=cur2.fetchone()[0]
        else:
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=?", (uid,))
            t=cur2.fetchone()[0]
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='PENDENTE'", (uid,))
            p=cur2.fetchone()[0]
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='CONCLUÍDA'", (uid,))
            rd=cur2.fetchone()[0]
            cur2.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND status='PENDENTE' AND vencimento <> '' AND vencimento < ?", (uid, today))
            a=cur2.fetchone()[0]
        
        cur2.connection.close()
        regions_summary[rname]={"configured":True,"total":t,"pendentes":p,"realizadas":rd,"atrasadas":a}

    # Contagem de itens não roteados (atribuídos ao Gerente)
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    if date_str:
        cur.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND route_status='UNROUTED' AND DATE(upload_time)=DATE(?)", (manager_id, date_str))
    else:
        cur.execute("SELECT COUNT(*) FROM releituras WHERE user_id=? AND route_status='UNROUTED'", (manager_id,))
    unrouted_count=cur.fetchone()[0]
    conn.close()

    print(f"[DEBUG Releitura] Resumo final das regiões: {regions_summary}")

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
    """Retorna dados iniciais para a página Porteira (gráficos e métricas)."""
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
    """Zera o banco de dados de Releitura (GLOBAL). Somente para Desenvolvedor."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({"success": False, "error": "Usuário não autenticado"}), 401

    if norm_role(user.get('role')) != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    reset_releitura_global()
    return jsonify({"success": True, "message": "Banco de releituras zerado (GLOBAL)."})

@app.route('/api/reset/porteira', methods=['POST'])
def reset_porteira():
    """Zera o banco de dados de Porteira (GLOBAL). Somente para Desenvolvedor."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({"success": False, "error": "Usuário não autenticado"}), 401

    if norm_role(user.get('role')) != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    reset_porteira_global()
    return jsonify({"success": True, "message": "Banco de porteira zerado (GLOBAL)."})

@app.route('/api/upload', methods=['POST'])
def upload_releitura():
    """
    Processa upload manual de arquivo Excel de Releitura.
    - Salva arquivo temporário.
    - Processa dados.
    - Evita duplicatas via hash.
    - Realiza roteamento regional.
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
    Processa upload manual de arquivo Excel de Porteira.
    - Salva dados na tabela resultados_leitura.
    - Distribui dados para todos os usuários (lógica de tabela única).
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
    """
    Aciona sincronização automática (via Scraping) de Releitura.
    - Baixa o relatório do Portal CEMIG.
    - Processa e roteia os dados por região (targets).
    - Salva no banco.
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({"success": False, "error": "Usuário não autenticado"}), 401

    role = norm_role(user.get('role'))
    if role != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    try:
        # Sempre usa credenciais da Gerência para baixar
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
        details_v2 = route_releituras(details)

        # Estrutura auxiliar para compatibilidade com lógica existente
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

        # Salva dados roteados
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
                # Se não tem dono, vai para o gerente como UNROUTED
                for it in items:
                    it["route_status"] = "UNROUTED"
                    it["route_reason"] = "REGIAO_SEM_MATRICULA"
                    it["region"] = region

                if not is_file_duplicate(file_hash, 'releitura', manager_id):
                    save_releitura_data(items, file_hash, manager_id)
                    summary[region]["status"] = "UNROUTED_TO_MANAGER"
                else:
                    summary[region]["status"] = "DUPLICADO"

        # Salva dados não roteados
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
    Aciona sincronização automática (via Scraping) de Porteira.
    """
    user = get_current_user_from_request()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401

    if norm_role(user.get('role')) != 'desenvolvedor':
        return jsonify({"success": False, "error": "Acesso negado"}), 403

    user_id = int(user['id'])

    try:
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

    if is_file_duplicate(file_hash, 'porteira', user_id):
        return jsonify({"success": False, "error": "DUPLICADO", "message": "Este relatório já foi processado anteriormente."})

    # Distribui para todos os usuários
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
    """Retorna dados resumidos para os gráficos de Porteira."""
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
    """
    Retorna os dados da tabela principal de Porteira.
    Suporta filtros por ciclo e região.
    """
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
            due = get_due_date(int(y), int(m), int(r))
            data_str = due.strftime('%d/%m/%Y') if due else '--/--'

            key = f"{r:02d}"
            raw = quantities.get(key) or {}
            osb = int(round(float(raw.get("osb", 0) or 0)))
            cnv = int(round(float(raw.get("cnv", 0) or 0)))
            qtd = int(round(float(raw.get("quantidade", 0) or 0)))

            atraso = 1 if (qtd > 0 and due and today > due) else 0

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
                'osb': (int(osb) if has_data else None),
                'cnv': (int(cnv) if has_data else None),
                'quantidade': (int(qtd) if has_data else None),
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
    """Retorna dados para o gráfico de 'Não Executadas' da Porteira."""
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
    """
    Lista todas as localidades de uma região específica.
    Respeita o filtro de ciclo para mostrar apenas ULs relevantes.
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
# Endpoint do Scheduler
# -------------------------------------------------------
@app.route('/api/scheduler/status', methods=['GET'])
def scheduler_status():
    """Retorna status atual do scheduler automático."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    
    scheduler = get_scheduler()
    status = scheduler.get_status()
    return jsonify(status)

@app.route('/api/scheduler/toggle', methods=['POST'])
def scheduler_toggle():
    """Liga/desliga o scheduler (apenas diretoria/gerência)."""
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401
    
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
# Inicialização Automática
# -------------------------------------------------------
with app.app_context():
    init_db()
    # Inicializar scheduler automático se possível
    try:
        init_scheduler()
    except Exception as e:
        print(f"⚠️ Scheduler não iniciado: {e}")


# -------------------------------------------------------
# Releitura: Configuração de Targets por Região
# -------------------------------------------------------
@app.route('/api/releitura/region-targets', methods=['GET', 'POST'])
def releitura_region_targets():
    """
    Gerencia o mapeamento entre Regiões e Matrículas (usuários responsáveis).
    Permite definir quem é o "dono" de cada base (Araxá, Uberaba, Frutal).
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


# -------------------------------------------------------
# Releitura: Itens não roteados (Auditoria)
# -------------------------------------------------------

# Alias de compatibilidade
@app.route('/api/region-targets', methods=['GET', 'POST'])
def releitura_region_targets_alias():
    return releitura_region_targets()

@app.route('/api/releitura/unrouted', methods=['GET'])
def api_releitura_unrouted():
    """Retorna itens que não puderam ser roteados para nenhuma região (caem na Gerência)."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    role = norm_role(user.get('role'))
    if role not in ('gerencia', 'diretoria'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    date_str = request.args.get('date')
    return jsonify({'success': True, 'items': get_releitura_unrouted(date_str)})


@app.route('/api/releitura/reset', methods=['POST'])
def api_releitura_reset():
    """Zera apenas os dados de Releitura."""
    user = get_current_user_from_request()
    if not user:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    role = norm_role(user.get('role'))
    if role != 'desenvolvedor':
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    reset_releitura_global()
    return jsonify({'success': True, 'message': 'Releitura zerada com sucesso'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
