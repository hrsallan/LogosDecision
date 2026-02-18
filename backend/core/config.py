"""core.config

Configurações e helpers compartilhados do projeto LOGOS DECISION.

Motivação:
- Centralizar a resolução de caminhos (raiz do projeto, DB, etc.)
- Evitar duplicação de DB_PATH espalhado em múltiplos módulos
- Garantir migração automática do banco antigo (vigilacore.db) -> novo (logos_decision.db)

Observação:
- Mantém compatibilidade com o nome antigo do banco e variáveis de ambiente legadas.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def find_project_root() -> Path:
    """Localiza a raiz do projeto subindo na árvore de diretórios."""
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        # Marcadores mais confiáveis
        if (parent / "frontend").exists() and (parent / "backend").exists():
            return parent
        if (parent / ".env").exists() and (parent / "data").exists():
            return parent
    # Fallback: core/ -> backend/ -> raiz
    return here.parents[2]


def get_db_path() -> Path:
    """Retorna o caminho do SQLite do projeto.

    Prioridade:
    1) LOGOS_DECISION_DB_PATH (novo)
    2) VIGILACORE_DB_PATH (legado)
    3) DB_PATH (genérico)
    4) backend/data/logos_decision.db (padrão)

    Migração:
    - Se o banco novo não existir, mas o antigo existir, tenta renomear (ou copiar)
      o arquivo vigilacore.db para logos_decision.db automaticamente.
    """
    env = os.getenv("LOGOS_DECISION_DB_PATH") or os.getenv("VIGILACORE_DB_PATH") or os.getenv("DB_PATH")
    if env:
        return Path(env)

    root = find_project_root()
    data_dir = root / "backend" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    new_db = data_dir / "logos_decision.db"
    old_db = data_dir / "vigilacore.db"

    if new_db.exists():
        return new_db

    if old_db.exists():
        try:
            old_db.rename(new_db)
            return new_db
        except Exception:
            # Em Windows pode falhar se houver lock: faz cópia
            try:
                shutil.copy2(old_db, new_db)
                return new_db
            except Exception:
                return old_db

    return new_db


# Constante conveniente (avaliada no import)
DB_PATH = get_db_path()
