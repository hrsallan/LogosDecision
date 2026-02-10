from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Dict, Tuple, Optional
import threading

import pandas as pd


# Cache simples para evitar reabrir o Excel a cada request
__LOCK = threading.Lock()
__CACHE: dict = {
    "path": None,
    "mtime": None,
    "map": {},  # (ano, mes, razao_int) -> date
}


# Abreviações de meses (pt-BR) usadas nas abas do calendário
MONTH_ABBR_TO_NUM = {
    "Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6,
    "Jul": 7, "Ago": 8, "Set": 9, "Out": 10, "Nov": 11, "Dez": 12,
}


def default_calendar_path() -> Path:
    """
    Caminho padrão do calendário.
    Esperado em: <raiz_do_projeto>/data/calendario_leitura.xlsx
    """
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "data" / "calendario_leitura.xlsx"


def _norm(s: str) -> str:
    return (
        str(s or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace(".", "")
        .replace("_", "")
    )


def _find_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    cols = list(df.columns)
    norm_map = {_norm(c): c for c in cols}
    for cand in candidates:
        key = _norm(cand)
        if key in norm_map:
            return norm_map[key]
    # fallback: contains
    for c in cols:
        nc = _norm(c)
        for cand in candidates:
            if _norm(cand) in nc:
                return c
    return None


def _parse_date(v) -> Optional[date]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s or s.lower() in ("nan", "nat"):
        return None
    # formatos comuns: 07.01.2026 / 07/01/2026
    s = s.replace(".", "/")
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date()
    except Exception:
        return None


def _sheet_to_month_year(sheet_name: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Ex.: 'Jan-26' -> (2026, 1)
         'Fev-2026' -> (2026, 2)
    """
    s = str(sheet_name or "").strip()
    if "-" not in s:
        return None, None
    a, b = s.split("-", 1)
    mon = MONTH_ABBR_TO_NUM.get(a.strip()[:3].title())
    year_part = b.strip()
    # aceita '26' ou '2026'
    try:
        y = int(year_part)
        if y < 100:
            y = 2000 + y
        return y, mon
    except Exception:
        return None, mon


def load_calendar_map(path: Optional[Path] = None) -> Dict[Tuple[int, int, int], date]:
    """
    Retorna um mapa (ano, mes, razao) -> data de referência.
    A data de referência é priorizada por 'Cálculo do Faturamento';
    se não houver, usa 'Leitura' conforme orientação do usuário.
    """
    p = Path(path) if path else default_calendar_path()
    if not p.exists():
        return {}

    xl = pd.ExcelFile(str(p))
    mapping: Dict[Tuple[int, int, int], date] = {}

    for sheet in xl.sheet_names:
        ano, mes = _sheet_to_month_year(sheet)
        if not ano or not mes:
            continue

        df = pd.read_excel(str(p), sheet_name=sheet)
        col_razao = _find_col(df, ["Razão", "Razao"])
        col_calc = _find_col(df, ["Cálculo do Faturamento", "Calculo do Faturamento"])
        col_leit = _find_col(df, ["Leitura", " Leitura"])

        if not col_razao:
            continue

        for _, row in df.iterrows():
            try:
                r = row.get(col_razao)
            except Exception:
                r = None
            if r is None or (isinstance(r, float) and pd.isna(r)):
                continue
            try:
                razao_int = int(str(r).replace(".0", "").strip())
            except Exception:
                continue
            if razao_int < 1 or razao_int > 18:
                continue

            ref = None
            if col_calc:
                ref = _parse_date(row.get(col_calc))
            if not ref and col_leit:
                ref = _parse_date(row.get(col_leit))

            if ref:
                mapping[(ano, mes, razao_int)] = ref

    return mapping


def get_due_date(ano: int, mes: int, razao: int, path: Optional[Path] = None) -> Optional[date]:
    """
    Busca a data de referência do calendário para (ano, mes, razao).
    Usa cache por mtime para recarregar quando o arquivo mudar.
    """
    p = Path(path) if path else default_calendar_path()
    if not p.exists():
        return None

    try:
        mtime = p.stat().st_mtime
    except Exception:
        mtime = None

    with __LOCK:
        if __CACHE["path"] != str(p) or __CACHE["mtime"] != mtime or not __CACHE["map"]:
            __CACHE["path"] = str(p)
            __CACHE["mtime"] = mtime
            __CACHE["map"] = load_calendar_map(p)

        mp: Dict[Tuple[int, int, int], date] = __CACHE["map"] or {}
        return mp.get((int(ano), int(mes), int(razao)))
