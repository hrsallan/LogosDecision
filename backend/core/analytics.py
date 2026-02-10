import os
import pandas as pd
import re
import hashlib
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple

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


def validate_report_type(file_path: str) -> Tuple[str, str]:
    """
    Valida qual tipo de relatório é o arquivo baseado em strings características.
    
    Returns:
        Tuple[tipo, mensagem]
        tipo: "RELEITURAS", "PORTEIRA", ou "UNKNOWN"
    """
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Strings características do relatório Porteira
        porteira_markers = [
            b'Acompanhamento de Resultados',
            b'Conjunto de Contrato',
            b'Total',
            b'Leituras'
        ]
        
        # Strings características do relatório Releituras
        releituras_markers = [
            b'Releitura',
            b'Instalacao',
            b'Endereco',
            b'Vencimento'
        ]
        
        porteira_score = sum(1 for marker in porteira_markers if marker in content)
        releituras_score = sum(1 for marker in releituras_markers if marker in content)
        
        if porteira_score >= 3:
            return "PORTEIRA", f"Relatório identificado como PORTEIRA (score: {porteira_score}/4)"
        elif releituras_score >= 2:
            return "RELEITURAS", f"Relatório identificado como RELEITURAS (score: {releituras_score}/4)"
        else:
            return "UNKNOWN", "Tipo de relatório não identificado"
            
    except Exception as e:
        return "UNKNOWN", f"Erro ao validar: {e}"


def deep_scan_excel(file_path):
    """
    ⚠️ ATENÇÃO: Esta função processa o relatório de RELEITURAS NÃO EXECUTADAS.
    Para o relatório de "Acompanhamento de Resultados" (Porteira), use deep_scan_porteira_excel().
    """
    try:
        # Validar tipo de relatório
        report_type, msg = validate_report_type(file_path)
        print(f"🔍 {msg}")
        
        if report_type == "PORTEIRA":
            print("⚠️ AVISO: Este arquivo parece ser do tipo PORTEIRA, não RELEITURAS!")
            print("   Use a função deep_scan_porteira_excel() em vez desta.")
            return None
        elif report_type == "UNKNOWN":
            print("⚠️ AVISO: Tipo de relatório não identificado. Tentando processar mesmo assim...")
        normalized_path = _to_xlsx_if_needed(file_path)
        engine = "openpyxl" if str(normalized_path).lower().endswith(".xlsx") else None
        
        df_raw = pd.read_excel(normalized_path, header=None, engine=engine)
        data_matrix = df_raw.values
        details = []
        
        re_ul = re.compile(r'^\d{8}$')
        re_inst = re.compile(r'^\d{10}$')
        re_data = re.compile(r'\d{2}/\d{2}/\d{4}')
        
        stats = {
            'total_linhas': len(data_matrix),
            'linhas_validas': 0,
            'sem_ul': 0,
            'sem_instalacao': 0,
            'sem_data': 0,
            'cabecalhos': 0
        }

        i = 0
        while i < len(data_matrix):
            row = data_matrix[i]
            
            ul_val = str(row[0]).strip() if pd.notna(row[0]) else None
            inst_val = str(row[4]).strip() if pd.notna(row[4]) and len(row) > 4 else None
            endereco_val = str(row[10]).strip() if pd.notna(row[10]) and len(row) > 10 else None
            data_val = str(row[26]).strip() if pd.notna(row[26]) and len(row) > 26 else None
            reg_val = str(row[9]).strip() if pd.notna(row[9]) and len(row) > 9 else "03"
            
            # Pular cabeçalhos
            if reg_val.lower() == 'reg.':
                stats['cabecalhos'] += 1
                i += 1
                continue
            
            # Validar campos obrigatórios
            has_ul = re_ul.match(ul_val or '')
            has_inst = re_inst.match(inst_val or '')
            has_data = re_data.match(data_val or '')
            
            if not has_ul:
                stats['sem_ul'] += 1
            if not has_inst:
                stats['sem_instalacao'] += 1
            if not has_data:
                stats['sem_data'] += 1
            
            if has_ul and has_inst and has_data:
                stats['linhas_validas'] += 1
                details.append({
                    'ul': ul_val if ul_val else "---",
                    'inst': inst_val if inst_val else "---",
                    'venc': data_val if data_val else "---",
                    'reg': reg_val if reg_val else "03",
                    'endereco': endereco_val if endereco_val and endereco_val.lower() not in ['nan', 'none', 'endereco'] else ""
                })
            
            i += 1
        
        # Log estatísticas
        print(f"\n📊 Estatísticas de Processamento (RELEITURAS):")
        for key, value in stats.items():
            print(f"   • {key}: {value}")
        
        return details
        
    except Exception as e:
        print(f"❌ Erro ao analisar Excel de Releitura: {e}")
        import traceback
        traceback.print_exc()
        return None


def load_localidade_reference(ref_path: Path) -> Dict[str, Dict[str, str]]:
    """
    Carrega arquivo de referência de localidades.
    
    CORRIGIDO: Remove espaços dos nomes das colunas e usa UL regional como chave.
    
    Returns:
        Dict[ul_regional, {'localidade': str, 'supervisao': str, 'regiao': str}]
    """
    localidade_map = {}
    
    if not ref_path.exists():
        print(f"⚠️ Arquivo de referência não encontrado: {ref_path}")
        return localidade_map
    
    try:
        df_ref = pd.read_excel(ref_path)
        
        # Limpar nomes das colunas (remover espaços extras)
        df_ref.columns = [str(col).strip() for col in df_ref.columns]
        
        print(f"📋 Colunas disponíveis no arquivo de referência: {list(df_ref.columns)}")
        
        # Mapear nomes de colunas possíveis
        col_mapping = {}
        for col in df_ref.columns:
            col_lower = col.lower()
            if 'ul' in col_lower and not col_mapping.get('ul'):
                col_mapping['ul'] = col
            elif 'localidade' in col_lower and not col_mapping.get('localidade'):
                col_mapping['localidade'] = col
            elif 'supervisao' in col_lower or 'supervisão' in col_lower and not col_mapping.get('supervisao'):
                col_mapping['supervisao'] = col
            elif 'regiao' in col_lower or 'região' in col_lower and not col_mapping.get('regiao'):
                col_mapping['regiao'] = col
        
        print(f"🔍 Mapeamento de colunas: {col_mapping}")
        
        if 'ul' not in col_mapping:
            print("❌ Coluna 'UL' não encontrada no arquivo de referência!")
            return localidade_map
        
        for _, row in df_ref.iterrows():
            try:
                # Extrair UL regional (4 dígitos do meio)
                ul_full = str(row[col_mapping['ul']]).strip()
                if len(ul_full) >= 6:
                    # Para UL de 8 dígitos, pegar dígitos 3-6 (índices 2-5)
                    ul_regional = ul_full[2:6] if len(ul_full) == 8 else ul_full[-4:]
                else:
                    ul_regional = ul_full.zfill(4)
                
                info = {
                    'localidade': str(row.get(col_mapping.get('localidade', ''), 'N/A')).strip(),
                    'supervisao': str(row.get(col_mapping.get('supervisao', ''), 'N/A')).strip(),
                    'regiao': str(row.get(col_mapping.get('regiao', ''), 'N/A')).strip()
                }
                
                localidade_map[ul_regional] = info
                
            except Exception as e:
                print(f"⚠️ Erro ao processar linha: {e}")
                continue
        
        print(f"✅ Carregado arquivo de referência: {len(localidade_map)} localidades mapeadas")
        
        # Mostrar alguns exemplos
        if localidade_map:
            print(f"\n🔍 Exemplos de mapeamento (primeiros 5):")
            for i, (key, value) in enumerate(list(localidade_map.items())[:5]):
                print(f"   {i+1}. UL Regional {key}: {value['localidade']} ({value['supervisao']})")
        
        return localidade_map
        
    except Exception as e:
        print(f"❌ Erro ao carregar arquivo de referência: {e}")
        import traceback
        traceback.print_exc()
        return localidade_map


def deep_scan_porteira_excel(file_path, ciclo=None):
    """
    Analisa o relatório de "Acompanhamento de Resultados de Leitura" (Porteira).
    
    VERSÃO CORRIGIDA:
    - Valida tipo de relatório
    - Usa UL regional (dígitos 3-6) para mapeamento
    - Melhora logging e estatísticas
    - Remove hardcoding de nomes de colunas
    """
    try:
        # ==================== VALIDAR TIPO DE RELATÓRIO ====================
        report_type, msg = validate_report_type(file_path)
        print(f"🔍 {msg}")
        
        if report_type == "RELEITURAS":
            print("⚠️ AVISO: Este arquivo parece ser do tipo RELEITURAS, não PORTEIRA!")
            print("   Use a função deep_scan_excel() em vez desta.")
            return None
        elif report_type == "UNKNOWN":
            print("⚠️ AVISO: Tipo de relatório não identificado. Tentando processar mesmo assim...")
        
        # ==================== CARREGAR ARQUIVO DE REFERÊNCIA ====================
        ref_path = Path(__file__).parent.parent.parent / "REFERENCIA_LOCALIDADE_TR_4680006773.xlsx"
        localidade_map = load_localidade_reference(ref_path)
        
        # ==================== DEFINIR LOCALIDADES VÁLIDAS POR CICLO ====================
        CICLO_LOCALIDADES = {
            "97": set(list(range(1, 89)) + [90, 91, 96, 97]), # CICLO 97: Localidades 01-88 + 90, 91, 96, 97
            "98": set(list(range(1, 89)) + [92, 93, 96, 98]), # CICLO 98: Localidades 01-88 + 92, 93, 96, 98
            "99": set(list(range(1, 89)) + [89, 94, 96, 99]),  # CICLO 99: Localidades 01-88 + 89, 94, 96, 99
        }
        
        # ==================== PROCESSAR ARQUIVO EXCEL ====================
        normalized_path = _to_xlsx_if_needed(file_path)
        engine = "openpyxl" if str(normalized_path).lower().endswith(".xlsx") else None
        df_raw = pd.read_excel(normalized_path, header=None, engine=engine)

        data_rows = []
        current_conjunto_contrato = "N/A"

        # Índices das colunas no arquivo Excel
        # Observação importante (relatório "Acompanhamento de Resultados de Leitura"):
        #   - "Leituras a Exec." (col 3) = TOTAL PROGRAMADO (planejado)
        #   - "Total" (col 13) = TOTAL EXECUTADO (realizado)
        #   - "ñ exec." (col 16) = NÃO EXECUTADO
        # O bug da UI (% > 100 e "não executadas" > "total") ocorria porque
        # a coluna 13 (executadas) estava sendo interpretada como "total".
        COL_UL = 0
        COL_TIPO_UL = 1
        COL_LEIT_PLANEJADAS = 3
        COL_LEIT_EXECUTADAS = 13
        COL_NAO_EXEC = 16
        COL_IMPEDIMENTOS = 23  # "C/Imp" no relatório
        COL_REL_EXEC = 49
        COL_REL_NAO_EXEC = 50
        COL_REL_TOTAL = 52

        # Estatísticas detalhadas
        stats = {
            'total_linhas_arquivo': len(df_raw),
            'linhas_processadas': 0,
            'linhas_validas': 0,
            'filtradas_por_ciclo': 0,
            'ul_invalida': 0,
            'razao_invalida': 0,
            'sem_mapeamento': 0,
            'conjuntos_unicos': set(),
            'conjuntos_sem_mapeamento': set(),
            'ul_regionais_encontradas': set()
        }

        for i in range(len(df_raw)):
            row = df_raw.iloc[i]
            first_cell = row.iloc[COL_UL]

            # Detectar mudança de Conjunto de Contrato
            if isinstance(first_cell, str) and "Conjunto de Contrato:" in first_cell:
                conjunto_novo = first_cell.split(":")[-1].strip()
                current_conjunto_contrato = conjunto_novo
                stats['conjuntos_unicos'].add(conjunto_novo)
                continue

            # Obter valor da UL
            ul_val = str(first_cell).strip() if pd.notna(first_cell) else ""

            # Pular linhas de totais e vazias
            if not ul_val or "Sub-Total" in ul_val or "Total Geral" in ul_val:
                continue

            # Limpar UL e validar
            ul_clean = ul_val.replace(".0", "")
            if not ul_clean.isdigit() or len(ul_clean) != 8:
                stats['ul_invalida'] += 1
                continue

            stats['linhas_processadas'] += 1

            # ==================== EXTRAIR LOCALIDADE DA UL ====================
            localidade_ul = ul_clean[-2:]  # Últimos 2 dígitos
            
            # ==================== FILTRAR POR CICLO ====================
            if ciclo and ciclo in CICLO_LOCALIDADES:
                try:
                    localidade_ul_num = int(localidade_ul)
                    if localidade_ul_num not in CICLO_LOCALIDADES[ciclo]:
                        stats['filtradas_por_ciclo'] += 1
                        continue
                except ValueError:
                    continue

            # ==================== EXTRAIR UL REGIONAL (DÍGITOS 3-6) ====================
            ul_regional = ul_clean[2:6]
            stats['ul_regionais_encontradas'].add(ul_regional)

            # ==================== EXTRAIR TIPO UL ====================
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

            # ==================== BUSCAR REGIÃO NO MAPEAMENTO ====================
            # CORRIGIDO: Usa UL regional em vez dos últimos 4 dígitos do Conjunto
            regiao_info = localidade_map.get(ul_regional)
            
            if not regiao_info:
                stats['sem_mapeamento'] += 1
                stats['conjuntos_sem_mapeamento'].add(current_conjunto_contrato)
                # Usar valores padrão
                regiao_info = {
                    'localidade': 'Desconhecida',
                    'supervisao': 'N/A',
                    'regiao': 'N/A'
                }

            # ==================== VALIDAR RAZÃO ====================
            razao = ul_clean[:2]
            if not razao.isdigit():
                stats['razao_invalida'] += 1
                continue
            
            # CORRIGIDO: Expandir range ou apenas avisar
            razao_int = int(razao)
            if razao_int < 1 or razao_int > 18:
                # Avisar mas não descartar
                print(f"⚠️ Razão fora do range esperado: {razao} (UL: {ul_clean})")

            # ==================== EXTRAIR MÉTRICAS ====================
            def _num(idx):
                try:
                    v = row.iloc[idx]
                    if pd.isna(v): return 0.0
                    return float(v)
                except Exception: return 0.0

            leituras_planejadas = _num(COL_LEIT_PLANEJADAS)
            leituras_executadas = _num(COL_LEIT_EXECUTADAS)
            leituras_nao_exec = _num(COL_NAO_EXEC)

            # Se por qualquer motivo a coluna planejada vier vazia/0,
            # mas existirem executadas/não executadas, recompor o total.
            if (leituras_planejadas or 0) <= 0 and ((leituras_executadas or 0) > 0 or (leituras_nao_exec or 0) > 0):
                leituras_planejadas = (leituras_executadas or 0) + (leituras_nao_exec or 0)

            releituras_total = _num(COL_REL_TOTAL)
            releituras_nao_exec = _num(COL_REL_NAO_EXEC)
            impedimentos = _num(COL_IMPEDIMENTOS)

            # ==================== ADICIONAR LINHA ====================
            stats['linhas_validas'] += 1
            data_rows.append({
                "Conjunto_Contrato": current_conjunto_contrato,
                "UL": ul_clean,
                "UL_Regional": ul_regional,
                "Tipo_UL": tipo_ul_val,
                "Localidade_UL": localidade_ul,
                "Nome_Localidade": regiao_info['localidade'],
                "Regiao": regiao_info.get('regiao', regiao_info.get('supervisao', 'N/A')),
                "Supervisao": regiao_info.get('supervisao', 'N/A'),
                "Razao": razao.zfill(2),
                # Total planejado (para que % não executada faça sentido)
                "Total_Leituras": leituras_planejadas,
                "Leituras_Nao_Executadas": leituras_nao_exec,
                "Releituras_Totais": releituras_total,
                "Releituras_Nao_Executadas": releituras_nao_exec,
                "Impedimentos": impedimentos,
            })


        # ==================== LOG DE PROCESSAMENTO DETALHADO ====================
        print(f"\n{'='*80}")
        print(f"📊 ESTATÍSTICAS DE PROCESSAMENTO DETALHADAS")
        print(f"{'='*80}")
        print(f"📁 Arquivo: {Path(file_path).name}")
        print(f"🎯 Ciclo: {ciclo if ciclo else 'Todos'}")
        print(f"\n📈 Processamento:")
        print(f"   • Total de linhas no arquivo: {stats['total_linhas_arquivo']}")
        print(f"   • Linhas processadas (ULs válidas): {stats['linhas_processadas']}")
        print(f"   • Linhas finais (após filtros): {stats['linhas_validas']}")
        print(f"\n🚫 Filtros Aplicados:")
        print(f"   • Filtradas por ciclo {ciclo}: {stats['filtradas_por_ciclo']}")
        print(f"   • UL inválida (não 8 dígitos): {stats['ul_invalida']}")
        print(f"   • Razão inválida: {stats['razao_invalida']}")
        print(f"   • Sem mapeamento de localidade: {stats['sem_mapeamento']}")
        print(f"\n📍 Mapeamento:")
        print(f"   • Conjuntos de Contrato únicos: {len(stats['conjuntos_unicos'])}")
        print(f"   • ULs Regionais encontradas: {len(stats['ul_regionais_encontradas'])}")
        print(f"   • Conjuntos sem mapeamento: {len(stats['conjuntos_sem_mapeamento'])}")
        
        if stats['conjuntos_sem_mapeamento']:
            print(f"\n⚠️  Conjuntos sem mapeamento (primeiros 10):")
            for conj in list(stats['conjuntos_sem_mapeamento'])[:10]:
                print(f"      - {conj}")
        
        if stats['ul_regionais_encontradas']:
            print(f"\n🔍 ULs Regionais encontradas (primeiros 10):")
            for ul_reg in list(stats['ul_regionais_encontradas'])[:10]:
                info = localidade_map.get(ul_reg, {'localidade': 'NÃO MAPEADA'})
                print(f"      - {ul_reg}: {info['localidade']}")
        
        print(f"{'='*80}\n")

        if not data_rows:
            print("❌ Nenhum dado foi extraído do arquivo!")
            return []

        # ==================== AGRUPAR E CALCULAR PORCENTAGENS ====================
        df = pd.DataFrame(data_rows)
        df_grouped = df.groupby(
            ["Conjunto_Contrato", "UL", "UL_Regional", "Tipo_UL", "Razao", "Localidade_UL", 
             "Nome_Localidade", "Regiao", "Supervisao"], 
            as_index=False
        ).agg({
            "Total_Leituras": "sum",
            "Leituras_Nao_Executadas": "sum",
            "Releituras_Totais": "sum",
            "Releituras_Nao_Executadas": "sum",
            "Impedimentos": "sum",
        })

        # Percentual de não executada = (não executadas / total planejado) * 100
        # (Agora o denominador está correto.)
        df_grouped["Porcentagem_Nao_Executada"] = (
            (df_grouped["Leituras_Nao_Executadas"] / df_grouped["Total_Leituras"]) * 100
        ).replace([pd.NA, float("inf")], 0).fillna(0).round(2)

        # ==================== RETORNAR LISTA DE DICIONÁRIOS ====================
        details = []
        for _, r in df_grouped.iterrows():
            details.append({
                "Conjunto_Contrato": str(r["Conjunto_Contrato"]),
                "UL": str(r["UL"]),
                "UL_Regional": str(r["UL_Regional"]),
                "Tipo_UL": str(r.get("Tipo_UL", "")),
                "Localidade_UL": str(r["Localidade_UL"]),
                "Nome_Localidade": str(r["Nome_Localidade"]),
                "Regiao": str(r["Regiao"]),
                "Supervisao": str(r["Supervisao"]),
                "Razao": str(r["Razao"]).zfill(2),
                "Total_Leituras": float(r["Total_Leituras"]),
                "Leituras_Nao_Executadas": float(r["Leituras_Nao_Executadas"]),
                "Porcentagem_Nao_Executada": float(r["Porcentagem_Nao_Executada"]),
                "Releituras_Totais": float(r["Releituras_Totais"]),
                "Releituras_Nao_Executadas": float(r["Releituras_Nao_Executadas"]),
                "Impedimentos": float(r.get("Impedimentos", 0)),
            })

        print(f"✅ Processamento concluído: {len(details)} registros gerados\n")
        return details

    except Exception as e:
        print(f"❌ Erro ao analisar Excel da Porteira: {e}")
        import traceback
        traceback.print_exc()
        return None
