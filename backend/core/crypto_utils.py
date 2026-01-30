"""Utilities for encrypting/decrypting sensitive fields (e.g. portal passwords).

We use Fernet (symmetric authenticated encryption).

Key management:
- Preferred: set VIGILACORE_FERNET_KEY in the environment (.env). It must be a valid Fernet key.
  You can generate one with:
      python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
- Fallback: derive a stable key from JWT_SECRET if VIGILACORE_FERNET_KEY is not set.
  This is better than plaintext, but you should set a dedicated Fernet key in production.
"""

from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _derive_key_from_secret(secret: str) -> bytes:
    """Derive a 32-byte urlsafe base64 key from a secret string."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def get_fernet() -> Fernet:
    key = os.getenv("VIGILACORE_FERNET_KEY") or os.getenv("PORTAL_CRED_KEY")
    if key:
        key_b = key.encode("utf-8")
        return Fernet(key_b)

    # Fallback to JWT_SECRET (stable if JWT_SECRET is stable)
    secret = os.getenv("JWT_SECRET", "segredo-super-seguro")
    return Fernet(_derive_key_from_secret(secret))


def encrypt_text(plain: str) -> str:
    if plain is None:
        return ""
    token = get_fernet().encrypt(plain.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(token: str) -> str:
    if not token:
        return ""
    try:
        plain = get_fernet().decrypt(token.encode("utf-8"))
        return plain.decode("utf-8")
    except InvalidToken:
        # Key changed or data corrupted
        raise RuntimeError("Não foi possível descriptografar: chave inválida ou dados corrompidos.")
