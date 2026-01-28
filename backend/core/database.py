import sqlite3
from core.auth import hash_password, authenticate_user as secure_authenticate
import os
from pathlib import Path
from datetime import datetime, timedelta

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
    cursor.execute("PRAGMA table_info(resultados_leitura)")
    rl_cols = [c[1] for c in cursor.fetchall()]
    if 'Tipo_UL' not in rl_cols:
        try:
            cursor.execute("ALTER TABLE resultados_leitura ADD COLUMN Tipo_UL TEXT DEFAULT ''")
        except Exception:
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
            print(f"Usuário admin '{admin_username}' criado com sucesso!")

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
