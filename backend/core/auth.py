"""
Módulo de autenticação segura com bcrypt
Arquivo: backend/core/auth.py
"""
import bcrypt
import sqlite3
from pathlib import Path
from typing import Optional, Dict

DB_PATH = Path(__file__).parent.parent / 'data' / 'vigilacore.db'


def hash_password(password: str) -> str:
    """
    Cria um hash seguro da senha usando bcrypt
    
    Args:
        password: Senha em texto plano
        
    Returns:
        Hash da senha em formato string
    """
    # Converte a senha para bytes
    password_bytes = password.encode('utf-8')
    
    # Gera o salt e cria o hash
    salt = bcrypt.gensalt(rounds=12)  # 12 rounds = bom equilíbrio segurança/performance
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Retorna como string para armazenar no banco
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha corresponde ao hash armazenado
    
    Args:
        password: Senha em texto plano fornecida pelo usuário
        hashed_password: Hash armazenado no banco de dados
        
    Returns:
        True se a senha está correta, False caso contrário
    """
    try:
        password_bytes = password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        print(f"Erro ao verificar senha: {e}")
        return False


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Autentica um usuário verificando username e senha
    
    Args:
        username: Nome de usuário
        password: Senha em texto plano
        
    Returns:
        Dicionário com dados do usuário se autenticado, None caso contrário
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Busca o usuário pelo username
    cursor.execute(
        'SELECT id, username, password, role FROM users WHERE username = ?',
        (username,)
    )
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return None
    
    user_id, username_db, hashed_password, role = user

    # Verifica a senha (bcrypt). Se o banco tiver senha legada em texto puro,
    # fazemos fallback, autenticamos e fazemos upgrade para hash.
    if isinstance(hashed_password, str) and hashed_password.startswith("$2"):
        ok = verify_password(password, hashed_password)
    else:
        ok = (password == hashed_password)
        if ok:
            try:
                # upgrade para bcrypt
                conn2 = sqlite3.connect(str(DB_PATH))
                cur2 = conn2.cursor()
                cur2.execute('UPDATE users SET password = ? WHERE id = ?', (hash_password(password), user_id))
                conn2.commit()
                conn2.close()
            except Exception:
                pass

    if ok:
        return {
            "id": user_id,
            "username": username_db,
            "role": role
        }

    return None



def register_user(username: str, password: str, role: str = 'analistas') -> bool:
    """
    Registra um novo usuário com senha hasheada
    
    Args:
        username: Nome de usuário
        password: Senha em texto plano
        role: Papel do usuário (analistas/gerencia/diretoria)
        
    Returns:
        True se registrado com sucesso, False se usuário já existe
    """
    try:
        # Hash da senha
        hashed_password = hash_password(password)
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            (username, hashed_password, role)
        )
        
        conn.commit()
        conn.close()
        return True
        
    except sqlite3.IntegrityError:
        # Usuário já existe
        return False
    except Exception as e:
        print(f"Erro ao registrar usuário: {e}")
        return False


def update_user_password(username: str, new_password: str) -> bool:
    """
    Atualiza a senha de um usuário
    
    Args:
        username: Nome de usuário
        new_password: Nova senha em texto plano
        
    Returns:
        True se atualizado com sucesso, False caso contrário
    """
    try:
        hashed_password = hash_password(new_password)
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE users SET password = ? WHERE username = ?',
            (hashed_password, username)
        )
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return rows_affected > 0
        
    except Exception as e:
        print(f"Erro ao atualizar senha: {e}")
        return False