import sqlite3
from core.auth import hash_password, authenticate_user as secure_authenticate
from core.crypto_utils import encrypt_text, decrypt_text
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()

DB_PATH = Path(__file__).parent.parent / 'data' / 'vigilacore.db'

# --- Ciclos Rurais (Porteira) ---
CYCLE_RAZOES = {
    "97": [90, 91],
    "98": [92, 93],
    "99": [89, 94],
}
RURAL_ALWAYS_INCLUDE = [96]


def _porteira_cycle_where(ciclo: str | None, prefix: str = "WHERE"):
    """Retorna (where_sql, params) para filtrar Porteira por ciclo.
    O filtro é feito pelo sufixo (2 últimos dígitos) da UL.
    """
    if not ciclo:
        return "", tuple()
    c = str(ciclo).strip()
    allowed = list(CYCLE_RAZOES.get(c, []))
    if c.isdigit():
        allowed.append(int(c))
    allowed += list(RURAL_ALWAYS_INCLUDE)

    if not allowed:
        allowed = list(RURAL_ALWAYS_INCLUDE)
    placeholders = ",".join(["?"] * len(allowed))

    where = (
        f"{prefix} (CAST(substr(UL, -2) AS INTEGER) < 89 "
        f"OR CAST(substr(UL, -2) AS INTEGER) IN ({placeholders}))"
    )
    return where, tuple(int(x) for x in allowed)


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Tabela de usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            portal_user TEXT,
            portal_password TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Garantir colunas de credenciais do portal (migração segura)
    cursor.execute("PRAGMA table_info(users)")
    cols = {row[1] for row in cursor.fetchall()}
    if "portal_user" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN portal_user TEXT")
    if "portal_password" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN portal_password TEXT")


    # Releituras - com user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS releituras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ul TEXT,
            instalacao TEXT,
            endereco TEXT,
            razao TEXT,
            vencimento TEXT,
            reg TEXT DEFAULT '03',
            status TEXT DEFAULT 'PENDENTE',
            upload_time TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Histórico de uploads - Releitura
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history_releitura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            module TEXT,
            count INTEGER,
            file_hash TEXT,
            timestamp TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Porteiras - com user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS porteiras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ul TEXT,
            instalacao TEXT,
            status TEXT DEFAULT 'PENDENTE',
            upload_time TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Histórico de uploads - Porteira
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history_porteira (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            module TEXT,
            count INTEGER,
            file_hash TEXT,
            timestamp TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Gráfico histórico (snapshots por hora) - com user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grafico_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            module TEXT NOT NULL,
            data DATE NOT NULL,
            hora TEXT NOT NULL,
            timestamp_upload TIMESTAMP NOT NULL,
            total INTEGER NOT NULL,
            pendentes INTEGER NOT NULL,
            realizadas INTEGER NOT NULL,
            file_hash TEXT,
            UNIQUE(user_id, module, data, hora),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Resultados de leitura (porteira) - com user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resultados_leitura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            Conjunto_Contrato TEXT,
            UL TEXT,
            Tipo_UL TEXT,
            Razao TEXT,
            Total_Leituras REAL,
            Leituras_Nao_Executadas REAL,
            Porcentagem_Nao_Executada REAL,
            Releituras_Totais REAL,
            Releituras_Nao_Executadas REAL,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Criar usuário admin padrão via variáveis de ambiente
    admin_username = os.getenv('ADMIN_USERNAME')
    admin_password = os.getenv('ADMIN_PASSWORD')

    if admin_username and admin_password:
        cursor.execute("SELECT id FROM users WHERE username = ?", (admin_username,))
        if not cursor.fetchone():
            hashed_password = hash_password(admin_password)
            cursor.execute("""
                INSERT INTO users (username, password, role)
                VALUES (?, ?, 'admin')
            """, (admin_username, hashed_password))
            print(f"✅ Usuário admin '{admin_username}' criado com sucesso!")

    conn.commit()
    conn.close()


# Usar a função segura de autenticação do módulo auth.py
authenticate_user = secure_authenticate


def register_user(username, password, role='user'):
    """Registra um novo usuário com senha hasheada usando bcrypt"""
    try:
        hashed_password = hash_password(password)
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, hashed_password, role))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def get_user_by_id(user_id):
    """Retorna os dados do usuário pelo ID"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, role FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def set_portal_credentials(user_id: int, portal_user: str, portal_password_plain: str) -> None:
    """Salva as credenciais do portal para o usuário.

    portal_password é armazenada criptografada (Fernet).
    """
    if not portal_user:
        raise ValueError("portal_user é obrigatório")
    if portal_password_plain is None or portal_password_plain == "":
        raise ValueError("portal_password é obrigatório")

    enc = encrypt_text(portal_password_plain)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET portal_user = ?, portal_password = ? WHERE id = ?",
        (portal_user, enc, int(user_id)),
    )
    conn.commit()
    conn.close()


def clear_portal_credentials(user_id: int) -> None:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET portal_user = NULL, portal_password = NULL WHERE id = ?",
        (int(user_id),),
    )
    conn.commit()
    conn.close()


def get_portal_credentials(user_id: int) -> dict | None:
    """Retorna {portal_user, portal_password} descriptografado para uso interno.

    Retorna None se não estiver configurado.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT portal_user, portal_password FROM users WHERE id = ?",
        (int(user_id),),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    pu = row["portal_user"]
    pp = row["portal_password"]
    if not pu or not pp:
        return None

    # If the Fernet key was rotated/lost, old encrypted values cannot be decrypted.
    # In that case, reset the stored credentials for this user so they can re-register,
    # instead of crashing the scraping flow.
    try:
        plain = decrypt_text(pp)
    except Exception:
        try:
            clear_portal_credentials(int(user_id))
        except Exception:
            pass
        return None

    return {"portal_user": pu, "portal_password": plain}


def get_portal_credentials_status(user_id: int) -> dict:
    """Retorna status seguro para o frontend (sem vazar a senha)."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT portal_user, portal_password FROM users WHERE id = ?",
        (int(user_id),),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {"configured": False}

    pu = row["portal_user"]
    pp = row["portal_password"]
    if not pu or not pp:
        return {"configured": False, "portal_user": pu or ""}

    # Validate decryptability without exposing the password.
    try:
        _ = decrypt_text(pp)
        ok = True
    except Exception:
        ok = False
        try:
            clear_portal_credentials(int(user_id))
        except Exception:
            pass

    return {"configured": ok, "portal_user": pu or ""}



def reset_database(user_id):
    """Reseta apenas os dados do usuário especificado"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('DELETE FROM releituras WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM history_releitura WHERE user_id = ?', (user_id,))
    cursor.execute("DELETE FROM grafico_historico WHERE user_id = ? AND module = 'releitura'", (user_id,))
    conn.commit()
    conn.close()
    print(f"[USER {user_id}] Banco de releituras zerado com sucesso.")


def _save_grafico_snapshot(module: str, total: int, pendentes: int, realizadas: int, file_hash: str | None, timestamp_iso: str, user_id: int):
    """Salva 1 ponto do gráfico por hora (consolida por (user_id, module, data, hora))."""
    try:
        ts = datetime.fromisoformat(timestamp_iso)
    except Exception:
        ts = datetime.now()

    data_ref = ts.date().isoformat()
    hora_ref = f"{ts.hour:02d}:00"

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO grafico_historico (user_id, module, data, hora, timestamp_upload, total, pendentes, realizadas, file_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, module, data, hora) DO UPDATE SET
            timestamp_upload = excluded.timestamp_upload,
            total = excluded.total,
            pendentes = excluded.pendentes,
            realizadas = excluded.realizadas,
            file_hash = excluded.file_hash
    ''', (user_id, module, data_ref, hora_ref, timestamp_iso, int(total), int(pendentes), int(realizadas), file_hash))

    conn.commit()
    conn.close()


def is_file_duplicate(file_hash, module, user_id):
    """Verifica se o arquivo já foi processado por este usuário"""
    if not file_hash:
        return False
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    table = 'history_releitura' if module == 'releitura' else 'history_porteira'
    cursor.execute(f'SELECT id FROM {table} WHERE user_id = ? AND file_hash = ?', (user_id, file_hash))

    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def save_releitura_data(details, file_hash, user_id):
    """Salva dados de releitura para o usuário especificado usando merge inteligente (otimizado)."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # Performance: uma transação única + batch operations
    cursor.execute("BEGIN")

    # Pega instalações existentes (somente o necessário)
    cursor.execute('SELECT instalacao, status FROM releituras WHERE user_id = ?', (user_id,))
    existing = {row[0]: row[1] for row in cursor.fetchall()}

    new_instalacoes = set()
    inserts = []
    updates = []

    for item in details:
        instalacao = item['inst']
        new_instalacoes.add(instalacao)

        endereco = item.get('endereco', '')
        reg = item.get('reg', '03')
        ul = item['ul']
        razao = ul[:2]
        venc = item.get('venc', '')

        if instalacao in existing:
            # mantém CONCLUÍDA
            if existing[instalacao] == 'CONCLUÍDA':
                continue
            updates.append((ul, endereco, razao, venc, reg, now, user_id, instalacao))
        else:
            inserts.append((user_id, ul, instalacao, endereco, razao, venc, reg, now))

    if updates:
        cursor.executemany('''
            UPDATE releituras
            SET ul = ?, endereco = ?, razao = ?, vencimento = ?, reg = ?, upload_time = ?
            WHERE user_id = ? AND instalacao = ?
        ''', updates)

    if inserts:
        cursor.executemany('''
            INSERT INTO releituras (user_id, ul, instalacao, endereco, razao, vencimento, reg, status, upload_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDENTE', ?)
        ''', inserts)

    # Instalações removidas do relatório: marca como concluída se estavam pendentes
    instalacoes_removidas = set(existing.keys()) - new_instalacoes
    removed_to_close = [(user_id, inst) for inst in instalacoes_removidas if existing.get(inst) == 'PENDENTE']
    if removed_to_close:
        cursor.executemany('''
            UPDATE releituras
            SET status = 'CONCLUÍDA'
            WHERE user_id = ? AND instalacao = ?
        ''', removed_to_close)

    # Histórico do upload
    cursor.execute('''
        INSERT INTO history_releitura (user_id, module, count, file_hash, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, 'releitura', len(details), file_hash, now))

    conn.commit()

    # Métricas + snapshot (após commit)
    cursor.execute('SELECT COUNT(*) FROM releituras WHERE user_id = ?', (user_id,))
    total = int(cursor.fetchone()[0] or 0)

    cursor.execute("SELECT COUNT(*) FROM releituras WHERE user_id = ? AND status = 'PENDENTE'", (user_id,))
    pendentes = int(cursor.fetchone()[0] or 0)

    realizadas = max(total - pendentes, 0)

    conn.close()
    _save_grafico_snapshot('releitura', total, pendentes, realizadas, file_hash, now, user_id)
    return

def save_porteira_data(details, file_hash, user_id):
    """Salva dados de porteira para o usuário especificado (otimizado)."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    cursor.execute("BEGIN")

    # Pega instalações existentes para evitar SELECT por linha
    cursor.execute('SELECT instalacao FROM porteiras WHERE user_id = ?', (user_id,))
    existing = {row[0] for row in cursor.fetchall()}

    inserts = []
    for item in details:
        inst = item['inst']
        if inst in existing:
            continue
        inserts.append((user_id, item['ul'], inst, 'PENDENTE', now))

    if inserts:
        cursor.executemany('''
            INSERT INTO porteiras (user_id, ul, instalacao, status, upload_time)
            VALUES (?, ?, ?, ?, ?)
        ''', inserts)

    cursor.execute('''
        INSERT INTO history_porteira (user_id, module, count, file_hash, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, 'porteira', len(details), file_hash, now))

    conn.commit()

    # Snapshot para gráfico (sem abrir nova conexão)
    cursor.execute('SELECT COUNT(*) FROM porteiras WHERE user_id = ?', (user_id,))
    total = int(cursor.fetchone()[0] or 0)
    cursor.execute("SELECT COUNT(*) FROM porteiras WHERE user_id = ? AND status = 'PENDENTE'", (user_id,))
    pendentes = int(cursor.fetchone()[0] or 0)
    realizadas = max(total - pendentes, 0)

    conn.close()
    _save_grafico_snapshot('porteira', total, pendentes, realizadas, file_hash, now, user_id)

def update_installation_status(installation_list, new_status, module, user_id):
    """Atualiza status de instalações para o usuário especificado"""
    if not installation_list:
        return
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    table_name = 'releituras' if module == 'releitura' else 'porteiras'
    placeholders = ','.join('?' * len(installation_list))

    cursor.execute(f'''
        UPDATE {table_name}
        SET status = ?
        WHERE user_id = ? AND instalacao IN ({placeholders})
    ''', (new_status, user_id, *installation_list))

    conn.commit()
    conn.close()


def get_releitura_details(user_id):
    """Retorna detalhes das releituras do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ul, instalacao, endereco, razao, vencimento, reg, status 
        FROM releituras 
        WHERE user_id = ? AND status = 'PENDENTE'
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()

    details = []
    for r in rows:
        item = {"ul": r[0], "inst": r[1], "endereco": r[2], "razao": r[3], "venc": r[4], "reg": r[5], "status": r[6]}
        details.append(item)

    def sort_key(item):
        try:
            return (datetime.strptime(item['venc'], '%d/%m/%Y'), item['reg'])
        except ValueError:
            return (datetime(2099, 12, 31), "ZZ")

    details.sort(key=sort_key)
    return details[:100]


def get_releitura_metrics(user_id):
    """Retorna métricas de releitura do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM releituras WHERE user_id = ?', (user_id,))
    total = int(cursor.fetchone()[0] or 0)

    cursor.execute("SELECT vencimento FROM releituras WHERE user_id = ? AND status = 'PENDENTE'", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    pendentes = len(rows)
    realizadas = max(total - pendentes, 0)

    ref = datetime.now() - timedelta(hours=3)
    today = ref.date()

    atrasadas = 0
    for (venc,) in rows:
        v = (venc or "").strip()
        try:
            d = datetime.strptime(v, "%d/%m/%Y").date()
            if d < today:
                atrasadas += 1
        except Exception:
            pass

    return {"total": total, "pendentes": pendentes, "realizadas": realizadas, "atrasadas": atrasadas}


def get_porteira_metrics(user_id):
    """Retorna métricas de porteira do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM porteiras WHERE user_id = ?', (user_id,))
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM porteiras WHERE user_id = ? AND status = 'PENDENTE'", (user_id,))
    pendentes = cursor.fetchone()[0]
    conn.close()

    return {"total": total, "pendentes": pendentes}


def get_releitura_chart_data(user_id, date_str=None):
    """Retorna dados do gráfico de releitura do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
        SELECT hora, total
        FROM grafico_historico
        WHERE user_id = ? AND module = 'releitura' AND data = COALESCE(?, DATE('now','localtime'))
        ORDER BY hora ASC
    ''', (user_id, date_str))
    rows = cursor.fetchall()
    conn.close()

    hourly_data = {f"{h:02d}h": 0 for h in range(7, 19)}
    for hora, total in rows:
        try:
            h = int(str(hora).split(':')[0])
            hora_label = f"{h:02d}h"
            if hora_label in hourly_data:
                hourly_data[hora_label] = int(total)
        except Exception:
            continue

    return list(hourly_data.keys()), list(hourly_data.values())


def get_releitura_due_chart_data(user_id, date_str=None):
    """Retorna dados do gráfico de vencimento de releituras do usuário"""
    try:
        if date_str:
            ref = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            ref = datetime.now()
    except Exception:
        ref = datetime.now()

    ref = ref - timedelta(hours=3)
    days = [(ref.date() + timedelta(days=delta)) for delta in range(-1, 6)]

    labels = [d.strftime("%d/%m") for d in days]
    key_full = [d.strftime("%d/%m/%Y") for d in days]
    counts = {k: 0 for k in key_full}

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT vencimento FROM releituras WHERE user_id = ? AND status = 'PENDENTE'", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    for (venc,) in rows:
        v = (venc or "").strip()
        if v in counts:
            counts[v] += 1

    values = [int(counts[k]) for k in key_full]
    return labels, values


def get_porteira_chart_data(user_id, date_str=None):
    """Retorna dados do gráfico de porteira do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
        SELECT hora, total
        FROM grafico_historico
        WHERE user_id = ? AND module = 'porteira' AND data = COALESCE(?, DATE('now','localtime'))
        ORDER BY hora ASC
    ''', (user_id, date_str))
    rows = cursor.fetchall()
    conn.close()

    hourly_data = {f"{h:02d}h": 0 for h in range(7, 19)}
    for hora, total in rows:
        try:
            h = int(str(hora).split(':')[0])
            hora_label = f"{h:02d}h"
            if hora_label in hourly_data:
                hourly_data[hora_label] = int(total)
        except Exception:
            continue

    return list(hourly_data.keys()), list(hourly_data.values())


def get_porteira_table_data(user_id, ciclo: str | None = None):
    """Retorna todos os dados da tabela resultados_leitura do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    where_parts = ["user_id = ?"]
    params = [user_id]

    cycle_where, cycle_params = _porteira_cycle_where(ciclo, prefix="AND")
    if cycle_where:
        where_parts.append(cycle_where.replace("AND ", "", 1))
        params.extend(cycle_params)

    where_clause = "WHERE " + " AND ".join(where_parts)

    cursor.execute(f'''
        SELECT
            Conjunto_Contrato,
            UL,
            COALESCE(Tipo_UL, '') as Tipo_UL,
            Razao,
            Total_Leituras,
            Leituras_Nao_Executadas,
            Porcentagem_Nao_Executada,
            Releituras_Totais,
            Releituras_Nao_Executadas
        FROM resultados_leitura
        {where_clause}
        ORDER BY UL
    ''', params)

    rows = cursor.fetchall()
    conn.close()

    return [dict(r) for r in rows]


def get_porteira_totals(user_id, ciclo: str | None = None):
    """Retorna os totalizadores da tabela resultados_leitura do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    where_parts = ["user_id = ?"]
    params = [user_id]

    cycle_where, cycle_params = _porteira_cycle_where(ciclo, prefix="AND")
    if cycle_where:
        where_parts.append(cycle_where.replace("AND ", "", 1))
        params.extend(cycle_params)

    where_clause = "WHERE " + " AND ".join(where_parts)

    cursor.execute(f'''
        SELECT
            SUM(Total_Leituras) as total_leituras,
            SUM(Leituras_Nao_Executadas) as leituras_nao_exec,
            SUM(Releituras_Totais) as total_releituras,
            SUM(Releituras_Nao_Executadas) as releituras_nao_exec
        FROM resultados_leitura
        {where_clause}
    ''', params)

    row = cursor.fetchone()
    conn.close()

    return {
        'total_leituras': int(row[0] or 0),
        'leituras_nao_exec': int(row[1] or 0),
        'total_releituras': int(row[2] or 0),
        'releituras_nao_exec': int(row[3] or 0)
    }


def save_porteira_table_data(data_list, user_id):
    """Salva dados na tabela resultados_leitura do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Limpa dados antigos DESTE USUÁRIO
    cursor.execute('DELETE FROM resultados_leitura WHERE user_id = ?', (user_id,))

    # Insere novos dados
    for data in data_list:
        cursor.execute('''
            INSERT INTO resultados_leitura 
            (user_id, Conjunto_Contrato, UL, Tipo_UL, Razao, Total_Leituras, Leituras_Nao_Executadas, 
             Porcentagem_Nao_Executada, Releituras_Totais, Releituras_Nao_Executadas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            data.get('Conjunto_Contrato'),
            data.get('UL'),
            data.get('Tipo_UL'),
            data.get('Razao'),
            data.get('Total_Leituras'),
            data.get('Leituras_Nao_Executadas'),
            data.get('Porcentagem_Nao_Executada'),
            data.get('Releituras_Totais'),
            data.get('Releituras_Nao_Executadas')
        ))

    conn.commit()
    conn.close()


def get_porteira_chart_summary(user_id, ciclo: str | None = None):
    """Retorna dados agregados para o gráfico de barras da porteira do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    where_parts = ["user_id = ?"]
    params = [user_id]

    cycle_where, cycle_params = _porteira_cycle_where(ciclo, prefix="AND")
    if cycle_where:
        where_parts.append(cycle_where.replace("AND ", "", 1))
        params.extend(cycle_params)

    where_clause = "WHERE " + " AND ".join(where_parts)

    cursor.execute(f'''
        SELECT
            SUM(Total_Leituras) as total_leituras,
            SUM(Leituras_Nao_Executadas) as leituras_nao_exec,
            SUM(Releituras_Totais) as total_releituras,
            SUM(Releituras_Nao_Executadas) as releituras_nao_exec
        FROM resultados_leitura
        {where_clause}
    ''', params)

    row = cursor.fetchone()
    conn.close()

    if not row or row[0] is None:
        return {"labels": [], "datasets": []}

    total = int(row[0] or 0)
    nao = int(row[1] or 0)
    execu = max(total - nao, 0)

    rel_total = int(row[2] or 0)
    rel_nao = int(row[3] or 0)
    rel_execu = max(rel_total - rel_nao, 0)

    return {
        "labels": ["Leituras", "Releituras"],
        "datasets": [
            {"label": "Executadas", "data": [execu, rel_execu]},
            {"label": "Não executadas", "data": [nao, rel_nao]},
        ]
    }


def get_porteira_nao_executadas_chart(user_id, ciclo: str | None = None):
    """Retorna dados para o gráfico de leituras não executadas por razão do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    where_parts = ["user_id = ?", "Leituras_Nao_Executadas > 0"]
    params = [user_id]

    cycle_where, cycle_params = _porteira_cycle_where(ciclo, prefix="AND")
    if cycle_where:
        where_parts.append(cycle_where.replace("AND ", "", 1))
        params.extend(cycle_params)

    where_clause = "WHERE " + " AND ".join(where_parts)

    cursor.execute(f'''
        SELECT 
            Razao,
            SUM(Leituras_Nao_Executadas) as total_nao_exec
        FROM resultados_leitura
        {where_clause}
        GROUP BY Razao
        ORDER BY Razao
    ''', params)

    rows = cursor.fetchall()
    conn.close()

    labels = []
    values = []

    for razao, total in rows:
        labels.append(f"Razão {razao}")
        values.append(int(total))

    if not labels:
        labels = [f"Razão {i:02d}" for i in range(1, 8)]
        values = [0] * 7

    return labels, values


def reset_porteira_database(user_id):
    """Limpa apenas os dados da porteira do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute('DELETE FROM resultados_leitura WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM porteiras WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM history_porteira WHERE user_id = ?', (user_id,))
    cursor.execute("DELETE FROM grafico_historico WHERE user_id = ? AND module = 'porteira'", (user_id,))

    conn.commit()
    conn.close()

    print(f"✅ Dados da Porteira do usuário {user_id} zerados com sucesso!")


def save_file_history(module, count, file_hash, user_id):
    """Salva histórico de upload de arquivo do usuário"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    if module == 'porteira':
        cursor.execute('''
            INSERT INTO history_porteira (user_id, module, count, file_hash, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, module, count, file_hash, datetime.now()))
    else:
        cursor.execute('''
            INSERT INTO history_releitura (user_id, module, count, file_hash, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, module, count, file_hash, datetime.now()))

    conn.commit()
    conn.close()