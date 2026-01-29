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
    
    Returns:
        int: Número de leituras pendentes
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM leituras WHERE status = 0")
    result = cursor.fetchone()
    
    conn.close()
    
    return result[0] if result else 0