import os
import pandas as pd
import re
import hashlib
import tempfile
import subprocess
from pathlib import Path

def get_file_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def _to_xlsx_if_needed(path_str: str) -> str:
    """
    Se o arquivo for .xls e não houver xlrd, converte para .xlsx via LibreOffice (soffice),
    e retorna o caminho do arquivo convertido.
    """
    p = Path(path_str)
    if p.suffix.lower() != ".xls":
        return path_str

    # Tentar ler via xlrd primeiro
    try:
        import xlrd  # type: ignore
        return path_str
    except Exception:
        pass

    # Fallback: converter via soffice
    out_dir = Path(tempfile.mkdtemp(prefix="vigila_xls2xlsx_"))
    try:
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(out_dir), str(p)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        converted = out_dir / (p.stem + ".xlsx")
        if converted.exists():
            return str(converted)
    except Exception:
        return path_str

    return path_str

def deep_scan_excel(file_path):
    try:
        normalized_path = _to_xlsx_if_needed(file_path)
        engine = "openpyxl" if str(normalized_path).lower().endswith(".xlsx") else None
        
        df_raw = pd.read_excel(normalized_path, header=None, engine=engine)
        data_matrix = df_raw.values
        details = []
        
        re_ul = re.compile(r'^\d{8}$')
        re_inst = re.compile(r'^\d{10}$')
        re_data = re.compile(r'\d{2}/\d{2}/\d{4}')

        i = 0
        while i < len(data_matrix):
            row = data_matrix[i]
            
            ul_val = str(row[0]).strip() if pd.notna(row[0]) else None
            inst_val = str(row[4]).strip() if pd.notna(row[4]) and len(row) > 4 else None
            endereco_val = str(row[10]).strip() if pd.notna(row[10]) and len(row) > 10 else None
            data_val = str(row[26]).strip() if pd.notna(row[26]) and len(row) > 26 else None
            reg_val = str(row[9]).strip() if pd.notna(row[9]) and len(row) > 9 else "03"
            
            if re_ul.match(ul_val or '') and re_inst.match(inst_val or '') and re_data.match(data_val or ''):
                if reg_val.lower() == 'reg.':
                    i += 1
                    continue
                    
                details.append({
                    'ul': ul_val if ul_val else "---",
                    'inst': inst_val if inst_val else "---",
                    'venc': data_val if data_val else "---",
                    'reg': reg_val if reg_val else "03",
                    'endereco': endereco_val if endereco_val and endereco_val.lower() not in ['nan', 'none', 'endereco'] else ""
                })
            
            i += 1

        return details
        
    except Exception as e:
        print(f"❌ Erro ao analisar Excel de Releitura: {e}")
        return None

def deep_scan_porteira_excel(file_path):
    """
    Analisa o relatório de "Acompanhamento de Resultados de Leitura" (Porteira)
    baixado do portal CEMIG SGL e extrai as métricas por Conjunto de Contrato + UL.
    """
    try:
        normalized_path = _to_xlsx_if_needed(file_path)
        engine = "openpyxl" if str(normalized_path).lower().endswith(".xlsx") else None
        df_raw = pd.read_excel(normalized_path, header=None, engine=engine)

        data_rows = []
        current_conjunto_contrato = "N/A"

        COL_UL = 0
        COL_TIPO_UL = 1
        COL_TOTAL_LEIT = 13
        COL_NAO_EXEC = 16
        COL_REL_NAO_EXEC = 50
        COL_REL_TOTAL = 52

        for i in range(len(df_raw)):
            row = df_raw.iloc[i]
            first_cell = row.iloc[0]

            if isinstance(first_cell, str) and "Conjunto de Contrato:" in first_cell:
                current_conjunto_contrato = first_cell.split(":")[-1].strip()
                continue

            ul_val = str(first_cell).strip() if pd.notna(first_cell) else ""

            if not ul_val or "Sub-Total" in ul_val or "Total Geral" in ul_val:
                continue

            ul_clean = ul_val.replace(".0", "")
            if not ul_clean.isdigit() or len(ul_clean) != 8:
                continue

            tipo_ul_val = ""
            try:
                if len(row) > COL_TIPO_UL and pd.notna(row.iloc[COL_TIPO_UL]):
                    tipo_ul_val = str(row.iloc[COL_TIPO_UL]).strip()
                if not tipo_ul_val:
                    for j in range(min(12, len(row))):
                        v = row.iloc[j]
                        if pd.isna(v): continue
                        s = str(v).strip().upper()
                        if s in ("CNV", "OSB"):
                            tipo_ul_val = s
                            break
                        m = re.search(r"\b(CNV|OSB)\b", s)
                        if m:
                            tipo_ul_val = m.group(1)
                            break
            except Exception:
                tipo_ul_val = tipo_ul_val or ""

            razao = ul_clean[:2]
            if not razao.isdigit():
                continue
            if int(razao) < 1 or int(razao) > 18:
                continue

            def _num(idx):
                try:
                    v = row.iloc[idx]
                    if pd.isna(v): return 0.0
                    return float(v)
                except Exception: return 0.0

            total_leituras = _num(COL_TOTAL_LEIT)
            leituras_nao_exec = _num(COL_NAO_EXEC)
            releituras_total = _num(COL_REL_TOTAL)
            releituras_nao_exec = _num(COL_REL_NAO_EXEC)

            data_rows.append({
                "Conjunto_Contrato": current_conjunto_contrato,
                "UL": ul_clean,
                "Tipo_UL": tipo_ul_val,
                "Razao": razao.zfill(2),
                "Total_Leituras": total_leituras,
                "Leituras_Nao_Executadas": leituras_nao_exec,
                "Releituras_Totais": releituras_total,
                "Releituras_Nao_Executadas": releituras_nao_exec,
            })

        if not data_rows:
            return []

        df = pd.DataFrame(data_rows)
        df_grouped = df.groupby(["Conjunto_Contrato", "UL", "Tipo_UL", "Razao"], as_index=False).agg({
            "Total_Leituras": "sum",
            "Leituras_Nao_Executadas": "sum",
            "Releituras_Totais": "sum",
            "Releituras_Nao_Executadas": "sum",
        })

        df_grouped["Porcentagem_Nao_Executada"] = (
            (df_grouped["Leituras_Nao_Executadas"] / df_grouped["Total_Leituras"]) * 100
        ).replace([pd.NA, float("inf")], 0).fillna(0).round(2)

        details = []
        for _, r in df_grouped.iterrows():
            details.append({
                "Conjunto_Contrato": str(r["Conjunto_Contrato"]),
                "UL": str(r["UL"]),
                "Tipo_UL": str(r.get("Tipo_UL", "")),
                "Razao": str(r["Razao"]).zfill(2),
                "Total_Leituras": float(r["Total_Leituras"]),
                "Leituras_Nao_Executadas": float(r["Leituras_Nao_Executadas"]),
                "Porcentagem_Nao_Executada": float(r["Porcentagem_Nao_Executada"]),
                "Releituras_Totais": float(r["Releituras_Totais"]),
                "Releituras_Nao_Executadas": float(r["Releituras_Nao_Executadas"]),
            })

        return details

    except Exception as e:
        print(f"❌ Erro ao analisar Excel da Porteira: {e}")
        return None
