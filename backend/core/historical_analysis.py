"""
Módulo de Análise Histórica

Responsável por gerar estatísticas agregadas e tendências históricas
baseadas nos dados armazenados no banco de dados.
"""

import sqlite3
from datetime import datetime, timedelta

# Caminho absoluto para o banco de dados
from core.config import DB_PATH


def get_historical_analysis():
    """
    Gera um relatório completo de análise histórica das Releituras.
    Inclui totais, tendências diárias, distribuição por razão e status.

    Returns:
        Dicionário contendo métricas e estruturas de dados para gráficos.
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Totais gerais
    cursor.execute('SELECT COUNT(*) FROM releituras')
    total_all_time = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM releituras WHERE status = "CONCLUIDA"')
    concluidas_all_time = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM releituras WHERE status = "PENDENTE"')
    pendentes_all_time = cursor.fetchone()[0]
    
    # Tendência diária (últimos 30 dias)
    cursor.execute('''
        SELECT DATE(upload_time), COUNT(*) as count
        FROM releituras
        GROUP BY DATE(upload_time)
        ORDER BY DATE(upload_time) DESC
        LIMIT 30
    ''')
    daily_data = cursor.fetchall()
    
    # Distribuição por Razão (Top 10)
    cursor.execute('''
        SELECT razao, COUNT(*) as count, 
               SUM(CASE WHEN status = "CONCLUIDA" THEN 1 ELSE 0 END) as concluidas
        FROM releituras
        GROUP BY razao
        ORDER BY count DESC
        LIMIT 10
    ''')
    razao_distribution = cursor.fetchall()
    
    # Distribuição por Status
    cursor.execute('''
        SELECT status, COUNT(*) as count
        FROM releituras
        GROUP BY status
    ''')
    status_distribution = cursor.fetchall()
    
    # Tempo médio de resolução (em horas)
    cursor.execute('''
        SELECT AVG(CAST((julianday('now') - julianday(upload_time)) * 24 AS INTEGER)) as avg_hours
        FROM releituras
        WHERE status = "CONCLUIDA"
    ''')
    avg_resolution_time = cursor.fetchone()[0] or 0
    
    # Volume recente (7 dias)
    cursor.execute('''
        SELECT COUNT(*) FROM releituras 
        WHERE upload_time >= datetime('now', '-7 days')
    ''')
    last_7_days = cursor.fetchone()[0]
    
    # Volume recente (24 horas)
    cursor.execute('''
        SELECT COUNT(*) FROM releituras 
        WHERE upload_time >= datetime('now', '-1 day')
    ''')
    last_24_hours = cursor.fetchone()[0]
    
    # Itens vencidos (Pendentes com data de vencimento passada)
    cursor.execute('''
        SELECT COUNT(*) FROM releituras 
        WHERE status = "PENDENTE" AND 
        CAST(substr(vencimento, 7, 4) || '-' || substr(vencimento, 4, 2) || '-' || substr(vencimento, 1, 2) AS DATE) < DATE('now')
    ''')
    overdue = cursor.fetchone()[0]
    
    # Quantidade de razões únicas
    cursor.execute('''
        SELECT COUNT(DISTINCT razao) FROM releituras
    ''')
    unique_razoes = cursor.fetchone()[0]
    
    conn.close()
    
    # Processamento dos dados para o frontend
    daily_labels = [d[0] for d in reversed(daily_data)]
    daily_values = [d[1] for d in reversed(daily_data)]
    
    razao_labels = [str(r[0]) for r in razao_distribution]
    razao_values = [r[1] for r in razao_distribution]
    razao_concluidas = [r[2] for r in razao_distribution]
    
    status_dict = {s[0]: s[1] for s in status_distribution}
    
    # Indicador de tendência (seta)
    trend = "↑" if (last_24_hours > 0) else "→"
    trend_pct = ((last_24_hours / max(last_7_days, 1)) * 100) if last_7_days > 0 else 0
    
    return {
        "summary": {
            "total_all_time": total_all_time,
            "concluidas_all_time": concluidas_all_time,
            "pendentes_all_time": pendentes_all_time,
            "avg_resolution_hours": round(avg_resolution_time, 1),
            "overdue": overdue,
            "unique_razoes": unique_razoes,
            "last_7_days": last_7_days,
            "last_24_hours": last_24_hours,
            "trend": trend,
            "trend_pct": round(trend_pct, 1)
        },
        "daily_trend": {
            "labels": daily_labels,
            "values": daily_values
        },
        "razao_distribution": {
            "labels": razao_labels,
            "values": razao_values,
            "concluidas": razao_concluidas
        },
        "status_distribution": status_dict,
        "performance": {
            "completion_rate": round((concluidas_all_time / max(total_all_time, 1)) * 100, 1),
            "pending_rate": round((pendentes_all_time / max(total_all_time, 1)) * 100, 1)
        }
    }
