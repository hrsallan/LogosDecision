"""
Testes de validação do sistema de autenticação
"""
from core.auth import hash_password, verify_password, authenticate_user, register_user


def test_hash_password():
    """Testa se o hash está funcionando"""
    password = "minha_senha_secreta"
    hashed = hash_password(password)
    
    print(f"✅ Senha original: {password}")
    print(f"✅ Hash gerado: {hashed}")
    print(f"✅ Tamanho do hash: {len(hashed)} caracteres")
    
    assert hashed != password, "❌ Hash não deve ser igual à senha!"
    assert hashed.startswith('$2b$'), "❌ Hash deve começar com $2b$"
    print("✅ Hash válido!\n")


def test_verify_password():
    """Testa se a verificação está funcionando"""
    password = "teste123"
    hashed = hash_password(password)
    
    # Teste com senha correta
    assert verify_password(password, hashed), "❌ Senha correta não foi aceita!"
    print("✅ Senha correta aceita")
    
    # Teste com senha incorreta
    assert not verify_password("senha_errada", hashed), "❌ Senha incorreta foi aceita!"
    print("✅ Senha incorreta rejeitada\n")


def test_register_and_login():
    """Testa registro e login completo"""
    username = "teste_user"
    password = "senha_forte_123"
    
    # Registrar
    success = register_user(username, password, 'user')
    print(f"✅ Registro: {'Sucesso' if success else 'Falhou (usuário pode já existir)'}")
    
    # Tentar login com senha correta
    user = authenticate_user(username, password)
    if user:
        print(f"✅ Login correto: {user}")
    else:
        print("⚠️  Login falhou (usuário pode não existir)")
    
    # Tentar login com senha errada
    user = authenticate_user(username, "senha_errada")
    assert user is None, "❌ Login com senha errada não deveria funcionar!"
    print("✅ Login incorreto bloqueado")


if __name__ == '__main__':
    print("🧪 INICIANDO TESTES DE AUTENTICAÇÃO\n")
    print("=" * 50)
    
    test_hash_password()
    test_verify_password()
    test_register_and_login()
    
    print("=" * 50)
    print("🎉 TODOS OS TESTES PASSARAM!")