import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'data' / 'vigilacore.db'

def get_time_from_iso(iso_str):
    try:
        return datetime.fromisoformat(iso_str)
    except ValueError:
        return None
    
def releituras_pendentes():
    """
    Retorna o número de leituras pendentes (status = 0) na tabela 'leituras'
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM leituras WHERE status = 0")
    result = cursor.fetchone()
    
    conn.close()
    
    return result[0] if result else 0

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
        ts = get_time_from_iso(row[0])
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
        ts = get_time_from_iso(result)
        if ts:
            return ts.strftime('%H:%M')
    return None 

def get_dashboard_metrics():
    """Retorna todas as métricas do dashboard (dados honestos, sem fabricação)"""
    
    aging = calculate_aging_buckets()
    last_collection = get_last_collection_time()
    
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
        "last_collection": last_collection,  # Indicador de confiança
        "metrics": {
            "pendentes": pendentes,
            "total": total,
            "concluidas": concluidas
        },
        "aging": aging,  # Backlog aging
    }