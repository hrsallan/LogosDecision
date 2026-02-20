"""
Módulo de Autenticação e Segurança

Este módulo gerencia a lógica de autenticação de usuários, hash de senhas
e verificação de credenciais. Utiliza a biblioteca bcrypt para segurança robusta.
"""

import bcrypt
import sqlite3
from typing import Optional, Dict

# Caminho absoluto para o banco de dados
from core.config import DB_PATH


def hash_password(password: str) -> str:
    """
    Cria um hash seguro da senha usando o algoritmo bcrypt.
    
    Argumentos:
        password (str): Senha em texto plano.
        
    Retorna:
        str: Hash seguro da senha.
    """
    # Converte a senha para bytes (necessário para o bcrypt)
    password_bytes = password.encode('utf-8')
    
    # Gera o salt e cria o hash (12 rounds é um bom equilíbrio entre segurança e performance)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Retorna como string para facilitar o armazenamento no banco
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifica se uma senha em texto plano corresponde ao hash armazenado.
    
    Argumentos:
        password (str): Senha em texto plano fornecida pelo usuário.
        hashed_password (str): Hash armazenado no banco de dados.
        
    Retorna:
        bool: True se a senha estiver correta, False caso contrário.
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
    Autentica um usuário verificando suas credenciais no banco de dados.
    Suporta migração automática de senhas legadas (texto plano) para bcrypt.
    
    Argumentos:
        username (str): Nome de usuário.
        password (str): Senha em texto plano.
        
    Retorna:
        dict | None: Dicionário com dados do usuário (id, username, role) se autenticado,
                     ou None caso a autenticação falhe.
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

    # Verifica a senha
    # Se o hash começa com $2, é um hash bcrypt válido.
    if isinstance(hashed_password, str) and hashed_password.startswith("$2"):
        ok = verify_password(password, hashed_password)
    else:
        # Fallback para senhas legadas (texto plano)
        ok = (password == hashed_password)
        if ok:
            try:
                # Upgrade automático para bcrypt (segurança)
                print(f"[SECURITY] Atualizando senha do usuário {username_db} para bcrypt...")
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
    Registra um novo usuário no sistema.
    
    Argumentos:
        username (str): Nome de usuário desejado.
        password (str): Senha em texto plano.
        role (str): Papel/Cargo do usuário (ex: 'analistas', 'gerencia', 'diretoria').
        
    Retorna:
        bool: True se o registro for bem-sucedido, False se o usuário já existir.
    """
    try:
        # Gera o hash seguro da senha
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
        # Erro de integridade geralmente significa username duplicado
        return False
    except Exception as e:
        print(f"Erro ao registrar usuário: {e}")
        return False


def update_user_password(username: str, new_password: str) -> bool:
    """
    Atualiza a senha de um usuário existente.
    
    Argumentos:
        username (str): Nome de usuário.
        new_password (str): Nova senha em texto plano.
        
    Retorna:
        bool: True se atualizado com sucesso, False caso contrário.
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
