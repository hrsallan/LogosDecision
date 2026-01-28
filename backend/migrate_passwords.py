"""
Script de migração de senhas em texto plano para bcrypt
Execute APENAS UMA VEZ após atualizar o código
"""
import sqlite3
from pathlib import Path
from core.auth import hash_password

DB_PATH = Path(__file__).parent / 'data' / 'vigilacore.db'


def migrate_passwords():
    """Migra todas as senhas em texto plano para bcrypt"""
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    print("🔄 Iniciando migração de senhas...")
    
    # Busca todos os usuários
    cursor.execute('SELECT id, username, password FROM users')
    users = cursor.fetchall()
    
    if not users:
        print("⚠️  Nenhum usuário encontrado")
        conn.close()
        return
    
    migrated = 0
    
    for user_id, username, old_password in users:
        # Verifica se já está hasheado (bcrypt hashes começam com $2b$)
        if old_password.startswith('$2b$'):
            print(f"⏭️  {username}: Já está hasheado, pulando...")
            continue
        
        # Hash da senha
        new_password = hash_password(old_password)
        
        # Atualiza no banco
        cursor.execute(
            'UPDATE users SET password = ? WHERE id = ?',
            (new_password, user_id)
        )
        
        print(f"✅ {username}: Senha migrada com sucesso!")
        migrated += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 Migração concluída! {migrated} senha(s) atualizada(s).")


if __name__ == '__main__':
    try:
        migrate_passwords()
    except Exception as e:
        print(f"❌ Erro na migração: {e}")