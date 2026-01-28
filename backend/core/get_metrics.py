import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'data' / 'vigilacore.db'

def get_timestamp_from_iso(iso_string):
    """Converte string ISO para datetime"""
    try:
        return datetime.fromisoformat(iso_string)
    except:
        return None

def calculate_sla_percentage():
    """Calcula % de pendências dentro do SLA (com base em vencimento)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM releituras WHERE status = "PENDENTE"')
    total_pendentes = cursor.fetchone()[0]
    
    if total_pendentes == 0:
        conn.close()
        return None  # Sem dados = sem métrica
    
    # Pendências que ainda estão dentro do SLA (vencimento >= hoje)
    today = datetime.now().strftime('%d/%m/%Y')
    cursor.execute('''
        SELECT COUNT(*) FROM releituras 
        WHERE status = "PENDENTE" AND vencimento >= ?
    ''', (today,))
    dentro_sla = cursor.fetchone()[0]
    
    conn.close()
    sla_pct = int((dentro_sla / total_pendentes) * 100) if total_pendentes > 0 else 0
    return sla_pct

def calculate_aging_buckets():
    """Calcula backlog aging: 0-2h / 2-6h / 6h+"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT upload_time FROM releituras 
        WHERE status = "PENDENTE"
        ORDER BY upload_time ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    now = datetime.now()
    aging_0_2 = 0
    aging_2_6 = 0
    aging_6plus = 0
    
    for row in rows:
        ts = get_timestamp_from_iso(row[0])
        if ts:
            hours_ago = (now - ts).total_seconds() / 3600
            if hours_ago < 2:
                aging_0_2 += 1
            elif hours_ago < 6:
                aging_2_6 += 1
            else:
                aging_6plus += 1
    
    return {
        "aging_0_2": aging_0_2,
        "aging_2_6": aging_2_6,
        "aging_6plus": aging_6plus,
        "total": aging_0_2 + aging_2_6 + aging_6plus
    }

def get_last_collection_time():
    """Retorna a hora da última coleta de dados (último upload)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT MAX(upload_time) FROM releituras
    ''')
    result = cursor.fetchone()[0]
    conn.close()
    
    if result:
        ts = get_timestamp_from_iso(result)
        if ts:
            return ts.strftime('%H:%M')
    
    return None  # Sem dados

def get_flow_data_24h():
    """Retorna dados de entradas vs resoluções por hora (últimas 24h)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Entradas: registros criados por hora (upload_time)
    # Usar datetime() para converter timestamp ISO
    cursor.execute('''
        SELECT strftime('%H', datetime(upload_time)) as hora, COUNT(*) as count
        FROM releituras
        GROUP BY hora
        ORDER BY hora ASC
    ''')
    entradas_raw = cursor.fetchall()
    
    # Resoluções: registros marcados como CONCLUIDA por hora
    cursor.execute('''
        SELECT strftime('%H', datetime(upload_time)) as hora, COUNT(*) as count
        FROM releituras
        WHERE status = "CONCLUIDA"
        GROUP BY hora
        ORDER BY hora ASC
    ''')
    resolucoes_raw = cursor.fetchall()
    
    conn.close()
    
    # Montar dicionários por hora
    entradas_dict = {f"{int(h):02d}h": c for h, c in entradas_raw}
    resolucoes_dict = {f"{int(h):02d}h": c for h, c in resolucoes_raw}
    
    # Garantir 24 horas (0h a 23h)
    labels = [f"{h:02d}h" for h in range(24)]
    entradas = [entradas_dict.get(label, 0) for label in labels]
    resolucoes = [resolucoes_dict.get(label, 0) for label in labels]
    
    return labels, entradas, resolucoes

def get_comparison_data():
    """Retorna comparativos: vs ontem e vs média 7d"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Pendentes hoje
    today = datetime.now().strftime('%d/%m/%Y')
    cursor.execute('''
        SELECT COUNT(*) FROM releituras 
        WHERE status = "PENDENTE"
    ''')
    pendentes_hoje = cursor.fetchone()[0]
    
    # Pendentes ontem (aproximado: criados há 24-48h)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%d/%m/%Y')
    cursor.execute('''
        SELECT COUNT(*) FROM releituras 
        WHERE status = "PENDENTE" AND upload_time >= datetime('now', '-2 days')
        AND upload_time < datetime('now', '-1 day')
    ''')
    pendentes_ontem = cursor.fetchone()[0]
    
    # Média 7 dias
    cursor.execute('''
        SELECT AVG(daily_count) FROM (
            SELECT DATE(upload_time) as day, COUNT(*) as daily_count
            FROM releituras
            WHERE upload_time >= datetime('now', '-7 days')
            GROUP BY day
        )
    ''')
    media_7d = cursor.fetchone()[0] or 0
    
    # Resolvidas hoje
    cursor.execute('''
        SELECT COUNT(*) FROM releituras 
        WHERE status = "CONCLUIDA" AND DATE(upload_time) = DATE('now')
    ''')
    resolvidas_hoje = cursor.fetchone()[0]
    
    # Resolvidas ontem
    cursor.execute('''
        SELECT COUNT(*) FROM releituras 
        WHERE status = "CONCLUIDA" AND DATE(upload_time) = DATE('now', '-1 day')
    ''')
    resolvidas_ontem = cursor.fetchone()[0]
    
    conn.close()
    
    # Calcular variações
    var_pendentes = pendentes_hoje - pendentes_ontem
    var_pendentes_str = f"↑{var_pendentes}" if var_pendentes > 0 else f"↓{abs(var_pendentes)}" if var_pendentes < 0 else "→"
    
    var_resolvidas = resolvidas_hoje - resolvidas_ontem
    var_resolvidas_str = f"↑{var_resolvidas}" if var_resolvidas > 0 else f"↓{abs(var_resolvidas)}" if var_resolvidas < 0 else "→"
    
    return {
        "pendentes_hoje": pendentes_hoje,
        "var_pendentes": var_pendentes_str,
        "resolvidas_hoje": resolvidas_hoje,
        "var_resolvidas": var_resolvidas_str,
        "media_7d": int(media_7d) if media_7d else 0
    }

def get_dashboard_metrics():
    """Retorna todas as métricas do dashboard (dados honestos, sem fabricação)"""
    
    sla_pct = calculate_sla_percentage()
    aging = calculate_aging_buckets()
    last_collection = get_last_collection_time()
    flow_labels, entradas, resolucoes = get_flow_data_24h()
    comparisons = get_comparison_data()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM releituras')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM releituras WHERE status = "PENDENTE"')
    pendentes = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM releituras WHERE status = "CONCLUIDA"')
    concluidas = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "status": "online",
        "last_collection": last_collection,  
        "metrics": {
            "sla_percent": sla_pct, 
            "sla_percent_display": f"{sla_pct}%" if sla_pct is not None else "N/A",
            "pendentes": pendentes,
            "pendentes_comp": comparisons["var_pendentes"],
            "resolvidas_hoje": comparisons["resolvidas_hoje"],
            "resolvidas_comp": comparisons["var_resolvidas"],
            "total": total,
            "concluidas": concluidas
        },
        "aging": aging,  # Backlog aging
        "flow": {
            "labels": flow_labels,
            "entradas": entradas,
            "resolucoes": resolucoes
        },
    }
