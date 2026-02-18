"""
Módulo de Criptografia Utilitária

Fornece funções para criptografar e descriptografar dados sensíveis (como senhas do portal)
usando criptografia simétrica (Fernet).
"""

from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _derive_key_from_secret(secret: str) -> bytes:
    """
    Deriva uma chave base64 de 32 bytes segura para URL a partir de uma string secreta.
    Usada para gerar uma chave Fernet determinística a partir de uma senha ou segredo.
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def get_fernet() -> Fernet:
    """
    Retorna uma instância singleton do Fernet (motor de criptografia).
    Tenta obter a chave de variáveis de ambiente específicas, ou faz fallback
    para derivar da chave JWT_SECRET.
    """
    key = os.getenv("LOGOS_DECISION_FERNET_KEY") or os.getenv("VIGILACORE_FERNET_KEY") or os.getenv("PORTAL_CRED_KEY")
    if key:
        key_b = key.encode("utf-8")
        return Fernet(key_b)

    # Fallback para JWT_SECRET (estável se o JWT_SECRET for persistente)
    secret = os.getenv("JWT_SECRET", "segredo-super-seguro")
    return Fernet(_derive_key_from_secret(secret))


def encrypt_text(plain: str) -> str:
    """
    Criptografa um texto plano.

    Args:
        plain: Texto a ser criptografado.

    Returns:
        String contendo o token criptografado.
    """
    if plain is None:
        return ""
    token = get_fernet().encrypt(plain.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(token: str) -> str:
    """
    Descriptografa um token criptografado.

    Args:
        token: String criptografada.

    Returns:
        Texto plano original.

    Raises:
        RuntimeError: Se a chave for inválida ou os dados estiverem corrompidos.
    """
    if not token:
        return ""
    try:
        plain = get_fernet().decrypt(token.encode("utf-8"))
        return plain.decode("utf-8")
    except InvalidToken:
        # Chave mudou ou dados corrompidos
        raise RuntimeError("Não foi possível descriptografar: chave inválida ou dados corrompidos.")
