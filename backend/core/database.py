import sqlite3
from core.auth import hash_password, authenticate_user as secure_authenticate
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv  # ADICIONE ESTA LINHA

# Carregar variáveis do .env
load_dotenv()  # ADICIONE ESTA LINHA

DB_PATH = Path(__file__).parent.parent / 'data' / 'vigilacore.db'

# --- Ciclos Rurais (Porteira) ---
# IMPORTANTE:
# Neste projeto, o filtro de ciclos da "Porteira" deve ser aplicado pelos
# DOIS ÚLTIMOS DÍGITOS da UL (e não pelo campo Razao do relatório).
#
# Regras:
# - Base: ULs com sufixo 01..88 sempre entram
# - Rural: ULs com sufixo >= 89 entram conforme ciclo selecionado (97/98/99)
# - A UL de sufixo 96 entra sempre (independente do ciclo)
CYCLE_RAZOES = {
    "97": [90, 91],
    "98": [92, 93],
    "99": [89, 94],
}
RURAL_ALWAYS_INCLUDE = [96]

def _porteira_cycle_where(ciclo: str | None):
    """Retorna (where_sql, params) para filtrar Porteira por ciclo.
    O filtro é feito pelo sufixo (2 últimos dígitos) da UL.

    - Base: sufixo 01..88 sempre entra
    - Rural: sufixo >= 89 entra apenas se estiver no ciclo selecionado
      (ex.: ciclo 97 => 90,91,97 e 96 sempre)
    """
    if not ciclo:
        return "", tuple()
    c = str(ciclo).strip()
    allowed = list(CYCLE_RAZOES.get(c, []))
    # o próprio ciclo também entra (97/98/99)
    if c.isdigit():
        allowed.append(int(c))
    # e o 96 entra sempre
    allowed += list(RURAL_ALWAYS_INCLUDE)

    # Se ciclo inválido, mantém apenas o 96 (base sempre entra via condição)
    if not allowed:
        allowed = list(RURAL_ALWAYS_INCLUDE)
    placeholders = ",".join(["?"] * len(allowed))

    # sufixo_ul = últimos 2 dígitos da UL (UL armazenada como TEXT)
    # Base (01..88) entra sempre
    # Rural entra apenas se sufixo_ul estiver na lista allowed
    where = (
        f"WHERE (CAST(substr(UL, -2) AS INTEGER) < 89 "
        f"OR CAST(substr(UL, -2) AS INTEGER) IN ({placeholders}))"
    )
    return where, tuple(int(x) for x in allowed)

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS releituras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ul TEXT,
            instalacao TEXT,
            endereco TEXT,
            razao TEXT,
            vencimento TEXT,
            reg TEXT DEFAULT '03',
            status TEXT DEFAULT 'PENDENTE',
            upload_time TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history_releitura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module TEXT,
            count INTEGER,
            file_hash TEXT,
            timestamp TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS porteiras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ul TEXT,
            instalacao TEXT,
            status TEXT DEFAULT 'PENDENTE',
            upload_time TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history_porteira (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module TEXT,
            count INTEGER,
            file_hash TEXT,
            timestamp TIMESTAMP
        )
    ''')

    # Histórico leve para gráficos (snapshot por upload/hora)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grafico_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module TEXT NOT NULL,
            data DATE NOT NULL,
            hora TEXT NOT NULL,
            timestamp_upload TIMESTAMP NOT NULL,
            total INTEGER NOT NULL,
            pendentes INTEGER NOT NULL,
            realizadas INTEGER NOT NULL,
            file_hash TEXT,
            UNIQUE(module, data, hora)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resultados_leitura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Conjunto_Contrato TEXT,
            UL TEXT,
            Tipo_UL TEXT,
            Razao TEXT,
            Total_Leituras REAL,
            Leituras_Nao_Executadas REAL,
            Porcentagem_Nao_Executada REAL,
            Releituras_Totais REAL,
            Releituras_Nao_Executadas REAL,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migração leve: garantir coluna Tipo_UL para a Porteira (CNV/OSB).
    # Projetos antigos criavam resultados_leitura sem essa coluna.
    cursor.execute("PRAGMA table_info(resultados_leitura)")
    rl_cols = [c[1] for c in cursor.fetchall()]
    if 'Tipo_UL' not in rl_cols:
        try:
            cursor.execute("ALTER TABLE resultados_leitura ADD COLUMN Tipo_UL TEXT DEFAULT ''")
        except Exception:
            # Se falhar por qualquer motivo, seguimos (a UI ainda funciona sem o campo)
            pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Criar usuário admin padrão via variáveis de ambiente (SEGURO)
    # Configure ADMIN_USERNAME e ADMIN_PASSWORD no arquivo .env
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

    cursor.execute("PRAGMA table_info(releituras)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'razao' not in columns:
        cursor.execute("ALTER TABLE releituras ADD COLUMN razao TEXT")
    if 'endereco' not in columns:
        cursor.execute("ALTER TABLE releituras ADD COLUMN endereco TEXT")
    if 'reg' not in columns:
        cursor.execute("ALTER TABLE releituras ADD COLUMN reg TEXT DEFAULT '03'")
    
    conn.commit()
    conn.close()


# Usar a função segura de autenticação do módulo auth.py
# A função authenticate_user agora usa bcrypt para verificar senhas
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


def reset_database():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('DELETE FROM releituras')
    cursor.execute('DELETE FROM history_releitura')
    cursor.execute('DELETE FROM porteiras')
    cursor.execute('DELETE FROM history_porteira')
    cursor.execute('DELETE FROM grafico_historico')
    conn.commit()
    conn.close()
    print("[1.0.1] Banco de dados zerado com sucesso.")


def _save_grafico_snapshot(module: str, total: int, pendentes: int, realizadas: int, file_hash: str | None, timestamp_iso: str):
    """Salva 1 ponto do gráfico por hora (consolida por (module,data,hora))."""
    try:
        ts = datetime.fromisoformat(timestamp_iso)
    except Exception:
        ts = datetime.now()

    # Consolidar por hora (HH:00)
    data_ref = ts.date().isoformat()
    hora_ref = f"{ts.hour:02d}:00"

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO grafico_historico (module, data, hora, timestamp_upload, total, pendentes, realizadas, file_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(module, data, hora) DO UPDATE SET
            timestamp_upload = excluded.timestamp_upload,
            total = excluded.total,
            pendentes = excluded.pendentes,
            realizadas = excluded.realizadas,
            file_hash = excluded.file_hash
    ''', (module, data_ref, hora_ref, timestamp_iso, int(total), int(pendentes), int(realizadas), file_hash))

    conn.commit()
    conn.close()

def is_file_duplicate(file_hash, module):
    if not file_hash:
        return False
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    table = 'history_releitura' if module == 'releitura' else 'history_porteira'
    cursor.execute(f'SELECT id FROM {table} WHERE file_hash = ?', (file_hash,))
    
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def save_releitura_data(details, file_hash):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    # Limpar apenas o ESTADO ATUAL (mantém históricos)
    cursor.execute('DELETE FROM releituras')
    conn.commit()
    
    # Inserir TODOS os registros (03 e Z3 separadamente)
    for item in details:
        endereco = item.get('endereco', '')
        reg = item.get('reg', '03')
        
        # Sempre inserir - não atualizar
        cursor.execute('''
            INSERT INTO releituras (ul, instalacao, endereco, razao, vencimento, reg, upload_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (item['ul'], item['inst'], endereco, item['ul'][:2], item['venc'], reg, now))

    cursor.execute('''
        INSERT INTO history_releitura (module, count, file_hash, timestamp)
        VALUES (?, ?, ?, ?)
    ''', ('releitura', len(details), file_hash, now))

    # Snapshot para gráfico (1 ponto por hora)
    total = len(details)
    pendentes = len(details)  # no upload, tudo entra como pendente
    realizadas = 0
    # Salva após o commit do estado atual para manter consistência
    conn.commit()
    conn.close()
    _save_grafico_snapshot('releitura', total, pendentes, realizadas, file_hash, now)
    return


def save_porteira_data(details, file_hash):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    for item in details:
        cursor.execute('SELECT id FROM porteiras WHERE instalacao = ?', (item['inst'],))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO porteiras (ul, instalacao, status, upload_time)
                VALUES (?, ?, ?, ?)
            ''', (item['ul'], item['inst'], 'PENDENTE', now))

    cursor.execute('''
        INSERT INTO history_porteira (module, count, file_hash, timestamp)
        VALUES (?, ?, ?, ?)
    ''', ('porteira', len(details), file_hash, now))

    conn.commit()
    conn.close()

    # Snapshot para gráfico (estado atual após o upload)
    conn2 = sqlite3.connect(str(DB_PATH))
    cur2 = conn2.cursor()
    cur2.execute('SELECT COUNT(*) FROM porteiras')
    total = cur2.fetchone()[0]
    cur2.execute("SELECT COUNT(*) FROM porteiras WHERE status = 'PENDENTE'")
    pendentes = cur2.fetchone()[0]
    conn2.close()
    realizadas = total - pendentes
    _save_grafico_snapshot('porteira', total, pendentes, realizadas, file_hash, now)

def update_installation_status(installation_list, new_status, module):
    if not installation_list:
        return
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    table_name = 'releituras' if module == 'releitura' else 'porteiras'
    placeholders = ','.join('?' * len(installation_list))
    
    cursor.execute(f'''
        UPDATE {table_name}
        SET status = ?
        WHERE instalacao IN ({placeholders})
    ''', (new_status, *installation_list))
    
    conn.commit()
    conn.close()

def get_releitura_details():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('SELECT ul, instalacao, endereco, razao, vencimento, reg, status FROM releituras WHERE status = "PENDENTE"')
    rows = cursor.fetchall()
    conn.close()
    
    today = datetime.now() - timedelta(hours=3)
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

def get_releitura_metrics():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM releituras')
    total = int(cursor.fetchone()[0] or 0)

    cursor.execute("SELECT vencimento FROM releituras WHERE status = 'PENDENTE'")
    rows = cursor.fetchall()
    conn.close()

    pendentes = len(rows)
    realizadas = max(total - pendentes, 0)

    # Atrasadas = pendentes cujo vencimento (dd/mm/YYYY) é menor que a data de hoje
    ref = datetime.now() - timedelta(hours=3)  # consistência com o restante do projeto
    today = ref.date()

    atrasadas = 0
    for (venc,) in rows:
        v = (venc or "").strip()
        try:
            d = datetime.strptime(v, "%d/%m/%Y").date()
            if d < today:
                atrasadas += 1
        except Exception:
            # se não der pra interpretar, ignora
            pass

    return {"total": total, "pendentes": pendentes, "realizadas": realizadas, "atrasadas": atrasadas}


def get_porteira_metrics():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM porteiras')
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM porteiras WHERE status = 'PENDENTE'")
    pendentes = cursor.fetchone()[0]
    conn.close()
    
    return {"total": total, "pendentes": pendentes}

def get_releitura_chart_data(date_str=None):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    # Pega os snapshots do DIA (por padrão, hoje)
    cursor.execute('''
SELECT hora, total
        FROM grafico_historico
        WHERE module = 'releitura' AND data = COALESCE(?, DATE('now','localtime'))
        ORDER BY hora ASC
    ''', (date_str,))
    rows = cursor.fetchall()
    conn.close()

    hourly_data = {f"{h:02d}h": 0 for h in range(7, 19)}
    for hora, total in rows:
        try:
            h = int(str(hora).split(':')[0])
            hora_label = f"{h:02d}h"
            if hora_label in hourly_data:
                # 1 ponto por hora (último snapshot vence por causa do upsert)
                hourly_data[hora_label] = int(total)
        except Exception:
            continue

    return list(hourly_data.keys()), list(hourly_data.values())


def get_releitura_due_chart_data(date_str=None):
    """Contagem de releituras PENDENTES por data de vencimento (janela de 7 dias).
    Janela: dia anterior ao 'date_str' (ou hoje) + o próprio dia + 5 dias à frente.
    Labels: dd/mm
    """
    # Data de referência (snapshot)
    try:
        if date_str:
            ref = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            ref = datetime.now()
    except Exception:
        ref = datetime.now()

    # Consistência com o restante do projeto (horário local aproximado)
    ref = ref - timedelta(hours=3)

    days = [(ref.date() + timedelta(days=delta)) for delta in range(-1, 6)]  # -1..+5 (7 dias)

    labels = [d.strftime("%d/%m") for d in days]
    key_full = [d.strftime("%d/%m/%Y") for d in days]
    counts = {k: 0 for k in key_full}

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT vencimento FROM releituras WHERE status = 'PENDENTE'")
    rows = cursor.fetchall()
    conn.close()

    for (venc,) in rows:
        v = (venc or "").strip()
        if v in counts:
            counts[v] += 1

    values = [int(counts[k]) for k in key_full]
    return labels, values

def get_porteira_chart_data(date_str=None):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
SELECT hora, total
        FROM grafico_historico
        WHERE module = 'porteira' AND data = COALESCE(?, DATE('now','localtime'))
        ORDER BY hora ASC
    ''', (date_str,))
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

def get_porteira_table_data(ciclo: str | None = None):
    """Retorna todos os dados da tabela resultados_leitura"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    where, params = _porteira_cycle_where(ciclo)

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
        {where}
        ORDER BY UL
    ''', params)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(r) for r in rows]

def get_porteira_totals(ciclo: str | None = None):
    """Retorna os totalizadores da tabela resultados_leitura"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    where, params = _porteira_cycle_where(ciclo)

    cursor.execute(f'''
        SELECT
            SUM(Total_Leituras) as total_leituras,
            SUM(Leituras_Nao_Executadas) as leituras_nao_exec,
            SUM(Releituras_Totais) as total_releituras,
            SUM(Releituras_Nao_Executadas) as releituras_nao_exec
        FROM resultados_leitura
        {where}
    ''', params)
    
    row = cursor.fetchone()
    conn.close()
    
    return {
        'total_leituras': int(row[0] or 0),
        'leituras_nao_exec': int(row[1] or 0),
        'total_releituras': int(row[2] or 0),
        'releituras_nao_exec': int(row[3] or 0)
    }

def save_porteira_table_data(data_list):
    """Salva dados na tabela resultados_leitura"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Limpa dados antigos
    cursor.execute('DELETE FROM resultados_leitura')
    
    # Insere novos dados
    for data in data_list:
        # Suporta versões antigas do banco (sem Tipo_UL)
        try:
            cursor.execute('''
                INSERT INTO resultados_leitura 
                (Conjunto_Contrato, UL, Tipo_UL, Razao, Total_Leituras, Leituras_Nao_Executadas, 
                 Porcentagem_Nao_Executada, Releituras_Totais, Releituras_Nao_Executadas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
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
        except Exception:
            cursor.execute('''
                INSERT INTO resultados_leitura 
                (Conjunto_Contrato, UL, Razao, Total_Leituras, Leituras_Nao_Executadas, 
                 Porcentagem_Nao_Executada, Releituras_Totais, Releituras_Nao_Executadas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('Conjunto_Contrato'),
                data.get('UL'),
                data.get('Razao'),
                data.get('Total_Leituras'),
                data.get('Leituras_Nao_Executadas'),
                data.get('Porcentagem_Nao_Executada'),
                data.get('Releituras_Totais'),
                data.get('Releituras_Nao_Executadas')
            ))
    
    conn.commit()
    conn.close()

def get_porteira_chart_summary(ciclo: str | None = None):
    """Retorna dados agregados para o gráfico de barras da porteira"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    where, params = _porteira_cycle_where(ciclo)

    cursor.execute(f'''
        SELECT
            SUM(Total_Leituras) as total_leituras,
            SUM(Leituras_Nao_Executadas) as leituras_nao_exec,
            SUM(Releituras_Totais) as total_releituras,
            SUM(Releituras_Nao_Executadas) as releituras_nao_exec
        FROM resultados_leitura
        {where}
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

def get_porteira_nao_executadas_chart(ciclo: str | None = None):
    """
    Retorna dados para o gráfico de leituras não executadas por razão
    Similar ao gráfico de vencimento das releituras
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    where = "WHERE Leituras_Nao_Executadas > 0"
    params: tuple = ()
    cycle_where, cycle_params = _porteira_cycle_where(ciclo)
    if cycle_where:
        # cycle_where vem como "WHERE (...)" -> transformar em "AND (...)"
        where += " AND " + cycle_where.replace("WHERE", "", 1).strip()
        params = cycle_params

    cursor.execute(f'''
        SELECT 
            Razao,
            SUM(Leituras_Nao_Executadas) as total_nao_exec
        FROM resultados_leitura
        {where}
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
    
    # Se não houver dados, retornar estrutura vazia
    if not labels:
        labels = [f"Razão {i:02d}" for i in range(1, 8)]
        values = [0] * 7
    
    return labels, values

def reset_porteira_database():
    """Limpa apenas os dados da tabela de porteira"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM resultados_leitura')
    cursor.execute('DELETE FROM history_porteira')
    cursor.execute("DELETE FROM grafico_historico WHERE module = 'porteira'")
    
    conn.commit()
    conn.close()
    
    print("✅ Dados da Porteira zerados com sucesso!")

def save_file_history(module, count, file_hash):
    """Salva histórico de upload de arquivo"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    if module == 'porteira':
        cursor.execute('''
            INSERT INTO history_porteira (module, count, file_hash, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (module, count, file_hash, datetime.now()))
    else:
        cursor.execute('''
            INSERT INTO history_releitura (module, count, file_hash, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (module, count, file_hash, datetime.now()))
    
    conn.commit()
    conn.close()