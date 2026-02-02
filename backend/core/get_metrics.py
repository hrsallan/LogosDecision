import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import json

# Reuso da lógica de vencimentos já utilizada na aba Releituras
from core.database import get_releitura_due_chart_data

DB_PATH = Path(__file__).parent.parent / 'data' / 'vigilacore.db'

def get_time_from_iso(iso_str):
    """Converte string ISO para datetime"""
    try:
        return datetime.fromisoformat(iso_str)
    except ValueError:
        return None

# ==========================================
# MÉTRICAS GERAIS DO SISTEMA
# ==========================================

def get_system_overview(user_id):
    """
    Retorna visão geral do sistema para o usuário
    
    Returns:
        dict: Estatísticas gerais do sistema
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Total de releituras
    cursor.execute("SELECT COUNT(*) FROM releituras WHERE user_id = ?", (user_id,))
    total_releituras = cursor.fetchone()[0]
    
    # Releituras pendentes
    cursor.execute("SELECT COUNT(*) FROM releituras WHERE user_id = ? AND status = 'PENDENTE'", (user_id,))
    releituras_pendentes = cursor.fetchone()[0]
    
    # Releituras concluídas
    cursor.execute("SELECT COUNT(*) FROM releituras WHERE user_id = ? AND status = 'CONCLUIDA'", (user_id,))
    releituras_concluidas = cursor.fetchone()[0]
    
    # Total de porteiras (via resultados_leitura)
    cursor.execute("SELECT SUM(Total_Leituras), SUM(Leituras_Nao_Executadas) FROM resultados_leitura WHERE user_id = ?", (user_id,))
    row_porteira = cursor.fetchone()
    total_porteiras = int(row_porteira[0] or 0)
    porteiras_pendentes = int(row_porteira[1] or 0)
    
    # Total de uploads realizados
    cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT timestamp FROM history_releitura WHERE user_id = ?
            UNION ALL
            SELECT timestamp FROM history_porteira WHERE user_id = ?
        )
    """, (user_id, user_id))
    total_uploads = cursor.fetchone()[0]
    
    conn.close()
    
    # Calcular percentuais
    percentual_releituras = (releituras_concluidas / total_releituras * 100) if total_releituras > 0 else 0
    percentual_porteiras = ((total_porteiras - porteiras_pendentes) / total_porteiras * 100) if total_porteiras > 0 else 0
    
    return {
        'total_releituras': total_releituras,
        'releituras_pendentes': releituras_pendentes,
        'releituras_concluidas': releituras_concluidas,
        'percentual_releituras_concluidas': round(percentual_releituras, 2),
        'total_porteiras': total_porteiras,
        'porteiras_pendentes': porteiras_pendentes,
        'porteiras_concluidas': total_porteiras - porteiras_pendentes,
        'percentual_porteiras_concluidas': round(percentual_porteiras, 2),
        'total_uploads': total_uploads
    }


def get_activity_timeline(user_id, days=7):
    """
    Retorna linha do tempo de atividades do usuário nos últimos N dias
    
    Args:
        user_id: ID do usuário
        days: Número de dias para análise
        
    Returns:
        list: Lista de atividades por dia
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    date_limit = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Buscar histórico de uploads
    cursor.execute("""
        SELECT 
            DATE(timestamp) as data,
            module as tipo,
            COUNT(*) as quantidade,
            SUM(count) as total_registros
        FROM (
            SELECT timestamp, module, count FROM history_releitura WHERE user_id = ? AND timestamp >= ?
            UNION ALL
            SELECT timestamp, module, count FROM history_porteira WHERE user_id = ? AND timestamp >= ?
        )
        GROUP BY data, tipo
        ORDER BY data DESC
    """, (user_id, date_limit, user_id, date_limit))
    
    timeline = []
    for row in cursor.fetchall():
        timeline.append({
            'data': row[0],
            'tipo': row[1],
            'uploads': row[2],
            'registros': row[3]
        })
    
    conn.close()
    return timeline


def get_performance_by_hour(user_id):
    """
    Retorna análise de performance por hora do dia
    
    Returns:
        dict: Estatísticas por hora
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            hora,
            AVG(total) as media_total,
            AVG(pendentes) as media_pendentes,
            AVG(realizadas) as media_realizadas,
            COUNT(*) as snapshots
        FROM grafico_historico
        WHERE user_id = ?
        GROUP BY hora
        ORDER BY hora
    """, (user_id,))
    
    performance = {}
    for row in cursor.fetchall():
        hora = row[0]
        performance[hora] = {
            'media_total': round(row[1], 2) if row[1] else 0,
            'media_pendentes': round(row[2], 2) if row[2] else 0,
            'media_realizadas': round(row[3], 2) if row[3] else 0,
            'snapshots': row[4]
        }
    
    conn.close()
    return performance


# ==========================================
# MÉTRICAS DE RELEITURAS
# ==========================================

def get_releituras_stats(user_id):
    """
    Retorna estatísticas detalhadas sobre releituras
    
    Returns:
        dict: Estatísticas de releituras
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Estatísticas gerais
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'PENDENTE' THEN 1 ELSE 0 END) as pendentes,
            SUM(CASE WHEN status = 'CONCLUIDA' THEN 1 ELSE 0 END) as concluidas
        FROM releituras
        WHERE user_id = ?
    """, (user_id,))
    
    stats = cursor.fetchone()
    
    # Distribuição por razão
    cursor.execute("""
        SELECT razao, COUNT(*) as quantidade
        FROM releituras
        WHERE user_id = ?
        GROUP BY razao
        ORDER BY quantidade DESC
    """, (user_id,))
    
    distribuicao_razao = [{'razao': r[0], 'quantidade': r[1]} for r in cursor.fetchall()]
    
    # Distribuição por vencimento
    cursor.execute("""
        SELECT 
            CASE 
                WHEN vencimento <= date('now') THEN 'Vencidas'
                WHEN vencimento <= date('now', '+3 days') THEN 'Próximas 3 dias'
                WHEN vencimento <= date('now', '+7 days') THEN 'Próxima semana'
                ELSE 'Futuras'
            END as categoria,
            COUNT(*) as quantidade
        FROM releituras
        WHERE user_id = ? AND status = 'PENDENTE'
        GROUP BY categoria
    """, (user_id,))
    
    distribuicao_vencimento = [{'categoria': r[0], 'quantidade': r[1]} for r in cursor.fetchall()]
    
    # Top 10 ULs com mais releituras
    cursor.execute("""
        SELECT ul, COUNT(*) as quantidade
        FROM releituras
        WHERE user_id = ?
        GROUP BY ul
        ORDER BY quantidade DESC
        LIMIT 10
    """, (user_id,))
    
    top_uls = [{'ul': r[0], 'quantidade': r[1]} for r in cursor.fetchall()]
    
    conn.close()
    
    return {
        'total': stats[0] if stats else 0,
        'pendentes': stats[1] if stats else 0,
        'concluidas': stats[2] if stats else 0,
        'distribuicao_razao': distribuicao_razao,
        'distribuicao_vencimento': distribuicao_vencimento,
        'top_uls': top_uls
    }


def get_releituras_trend(user_id, days=30):
    """
    Retorna tendência de releituras ao longo do tempo
    
    Args:
        days: Número de dias para análise
        
    Returns:
        dict: Dados de tendência
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    date_limit = (datetime.now() - timedelta(days=days)).date().isoformat()
    
    cursor.execute("""
        SELECT 
            data,
            AVG(pendentes) as media_pendentes,
            AVG(realizadas) as media_realizadas,
            AVG(total) as media_total
        FROM grafico_historico
        WHERE user_id = ? AND module = 'releitura' AND data >= ?
        GROUP BY data
        ORDER BY data
    """, (user_id, date_limit))
    
    trend = []
    for row in cursor.fetchall():
        trend.append({
            'data': row[0],
            'media_pendentes': round(row[1], 2) if row[1] else 0,
            'media_realizadas': round(row[2], 2) if row[2] else 0,
            'media_total': round(row[3], 2) if row[3] else 0
        })
    
    conn.close()
    return trend


# ==========================================
# MÉTRICAS DE PORTEIRA
# ==========================================

def get_porteira_stats(user_id, ciclo=None):
    """
    Retorna estatísticas detalhadas sobre a porteira
    
    Args:
        user_id: ID do usuário
        ciclo: Ciclo para filtrar (opcional)
    
    Returns:
        dict: Estatísticas da porteira
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Construir filtro de ciclo
    ciclo_filter = ""
    params_base = [user_id]
    
    if ciclo:
        # Definir lógica de ciclo diretamente aqui
        CYCLE_RAZOES = {
            "97": [90, 91],
            "98": [92, 93],
            "99": [89, 94],
        }
        RURAL_ALWAYS_INCLUDE = [96]
        
        c = str(ciclo).strip()
        allowed = list(CYCLE_RAZOES.get(c, []))
        if c.isdigit():
            allowed.append(int(c))
        allowed += list(RURAL_ALWAYS_INCLUDE)
        
        if not allowed:
            allowed = list(RURAL_ALWAYS_INCLUDE)
        
        placeholders = ",".join(["?"] * len(allowed))
        ciclo_filter = f" AND (CAST(substr(UL, -2) AS INTEGER) < 89 OR CAST(substr(UL, -2) AS INTEGER) IN ({placeholders}))"
        params_base.extend([int(x) for x in allowed])
    
    # Totalizadores gerais
    query = f"""
        SELECT
            SUM(Total_Leituras) as total_leituras,
            SUM(Leituras_Nao_Executadas) as leituras_nao_exec,
            SUM(Releituras_Totais) as total_releituras,
            SUM(Releituras_Nao_Executadas) as releituras_nao_exec,
            COUNT(DISTINCT UL) as total_uls
        FROM resultados_leitura
        WHERE user_id = ?{ciclo_filter}
    """
    cursor.execute(query, params_base)
    stats = cursor.fetchone()
    
    # Distribuição por razão
    query = f"""
        SELECT 
            Razao,
            SUM(Leituras_Nao_Executadas) as total_nao_exec,
            COUNT(*) as quantidade_uls
        FROM resultados_leitura
        WHERE user_id = ? AND Leituras_Nao_Executadas > 0{ciclo_filter}
        GROUP BY Razao
        ORDER BY total_nao_exec DESC
    """
    cursor.execute(query, params_base)
    
    distribuicao_razao = [
        {'razao': r[0], 'nao_executadas': r[1], 'uls': r[2]} 
        for r in cursor.fetchall()
    ]
    
    # ULs com maior percentual de não execução
    query = f"""
        SELECT 
            UL,
            Razao,
            Porcentagem_Nao_Executada,
            Total_Leituras,
            Leituras_Nao_Executadas
        FROM resultados_leitura
        WHERE user_id = ? AND Porcentagem_Nao_Executada > 0{ciclo_filter}
        ORDER BY Porcentagem_Nao_Executada DESC
        LIMIT 10
    """
    cursor.execute(query, params_base)
    
    uls_criticas = [
        {
            'ul': r[0],
            'razao': r[1],
            'percentual': round(r[2], 2),
            'total_leituras': r[3],
            'nao_executadas': r[4]
        } 
        for r in cursor.fetchall()
    ]
    
    # Performance por tipo de UL
    query = f"""
        SELECT 
            COALESCE(Tipo_UL, 'Não Especificado') as tipo,
            COUNT(*) as quantidade,
            AVG(Porcentagem_Nao_Executada) as media_nao_exec
        FROM resultados_leitura
        WHERE user_id = ?{ciclo_filter}
        GROUP BY tipo
        ORDER BY media_nao_exec DESC
    """
    cursor.execute(query, params_base)
    
    performance_tipo = [
        {'tipo': r[0], 'quantidade': r[1], 'media_nao_exec': round(r[2], 2) if r[2] else 0}
        for r in cursor.fetchall()
    ]
    
    conn.close()
    
    # Calcular métricas derivadas
    total_leituras = stats[0] if stats[0] else 0
    leituras_nao_exec = stats[1] if stats[1] else 0
    leituras_executadas = total_leituras - leituras_nao_exec
    percentual_execucao = (leituras_executadas / total_leituras * 100) if total_leituras > 0 else 0
    
    total_releituras = stats[2] if stats[2] else 0
    releituras_nao_exec = stats[3] if stats[3] else 0
    releituras_executadas = total_releituras - releituras_nao_exec
    percentual_releituras = (releituras_executadas / total_releituras * 100) if total_releituras > 0 else 0
    
    return {
        'total_leituras': int(total_leituras),
        'leituras_executadas': int(leituras_executadas),
        'leituras_nao_executadas': int(leituras_nao_exec),
        'percentual_execucao': round(percentual_execucao, 2),
        'total_releituras': int(total_releituras),
        'releituras_executadas': int(releituras_executadas),
        'releituras_nao_executadas': int(releituras_nao_exec),
        'percentual_releituras_executadas': round(percentual_releituras, 2),
        'total_uls': stats[4] if stats[4] else 0,
        'distribuicao_razao': distribuicao_razao,
        'uls_criticas': uls_criticas,
        'performance_tipo': performance_tipo
    }


def get_porteira_efficiency_score(user_id, ciclo=None):
    """
    Calcula score de eficiência da porteira (0-100)
    
    Args:
        user_id: ID do usuário
        ciclo: Ciclo para filtrar (opcional)
    
    Returns:
        dict: Score e componentes
    """
    stats = get_porteira_stats(user_id, ciclo=ciclo)
    
    # Componentes do score
    score_leituras = stats['percentual_execucao']
    score_releituras = stats['percentual_releituras_executadas']
    
    # Penalidade por ULs críticas (>20% não executadas)
    uls_criticas_count = len([u for u in stats['uls_criticas'] if u['percentual'] > 20])
    penalidade_criticas = min(uls_criticas_count * 2, 20)  # Máximo 20 pontos de penalidade
    
    # Score final (média ponderada)
    score_final = (score_leituras * 0.6 + score_releituras * 0.4) - penalidade_criticas
    score_final = max(0, min(100, score_final))  # Limitar entre 0-100
    
    # Classificação
    if score_final >= 90:
        classificacao = "Excelente"
        cor = "#10b981"
    elif score_final >= 75:
        classificacao = "Bom"
        cor = "#3b82f6"
    elif score_final >= 60:
        classificacao = "Regular"
        cor = "#f59e0b"
    else:
        classificacao = "Crítico"
        cor = "#ef4444"
    
    return {
        'score': round(score_final, 2),
        'classificacao': classificacao,
        'cor': cor,
        'componentes': {
            'score_leituras': round(score_leituras, 2),
            'score_releituras': round(score_releituras, 2),
            'penalidade_criticas': penalidade_criticas,
            'uls_criticas': uls_criticas_count
        }
    }


# ==========================================
# MÉTRICAS COMPARATIVAS
# ==========================================

def get_comparative_metrics(user_id, days=7):
    """
    Retorna métricas comparativas entre períodos
    
    Args:
        days: Número de dias para comparação
        
    Returns:
        dict: Métricas comparativas
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().date()
    period_end = today.isoformat()
    period_start = (today - timedelta(days=days)).isoformat()
    previous_period_end = (today - timedelta(days=days)).isoformat()
    previous_period_start = (today - timedelta(days=days*2)).isoformat()
    
    # Métricas do período atual
    cursor.execute("""
        SELECT 
            AVG(total) as media_total,
            AVG(pendentes) as media_pendentes,
            AVG(realizadas) as media_realizadas
        FROM grafico_historico
        WHERE user_id = ? AND data BETWEEN ? AND ?
    """, (user_id, period_start, period_end))
    
    current = cursor.fetchone()
    
    # Métricas do período anterior
    cursor.execute("""
        SELECT 
            AVG(total) as media_total,
            AVG(pendentes) as media_pendentes,
            AVG(realizadas) as media_realizadas
        FROM grafico_historico
        WHERE user_id = ? AND data BETWEEN ? AND ?
    """, (user_id, previous_period_start, previous_period_end))
    
    previous = cursor.fetchone()
    
    conn.close()
    
    # Calcular variações
    def calc_variation(current_val, previous_val):
        if not previous_val or previous_val == 0:
            return 0
        return ((current_val - previous_val) / previous_val) * 100
    
    current_total = current[0] if current and current[0] else 0
    current_pendentes = current[1] if current and current[1] else 0
    current_realizadas = current[2] if current and current[2] else 0
    
    previous_total = previous[0] if previous and previous[0] else 0
    previous_pendentes = previous[1] if previous and previous[1] else 0
    previous_realizadas = previous[2] if previous and previous[2] else 0
    
    return {
        'periodo_atual': {
            'media_total': round(current_total, 2),
            'media_pendentes': round(current_pendentes, 2),
            'media_realizadas': round(current_realizadas, 2)
        },
        'periodo_anterior': {
            'media_total': round(previous_total, 2),
            'media_pendentes': round(previous_pendentes, 2),
            'media_realizadas': round(previous_realizadas, 2)
        },
        'variacoes': {
            'total': round(calc_variation(current_total, previous_total), 2),
            'pendentes': round(calc_variation(current_pendentes, previous_pendentes), 2),
            'realizadas': round(calc_variation(current_realizadas, previous_realizadas), 2)
        }
    }


# ==========================================
# FUNÇÃO PRINCIPAL DE MÉTRICAS
# ==========================================

def get_dashboard_metrics(user_id, ciclo=None):
    """
    Retorna todas as métricas necessárias para o dashboard
    
    Args:
        user_id: ID do usuário
        ciclo: Ciclo para filtrar (opcional)
        
    Returns:
        dict: Todas as métricas consolidadas
    """
    # Gráfico de prazos (vencimento) igual ao da aba Releituras.
    due_labels, due_values = get_releitura_due_chart_data(user_id)

    return {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'ciclo': ciclo,
        'overview': get_system_overview(user_id),
        'releituras': get_releituras_stats(user_id),
        'releituras_trend': get_releituras_trend(user_id, days=30),
        'releituras_due_chart': {'labels': due_labels, 'values': due_values},
        'porteira': get_porteira_stats(user_id, ciclo=ciclo),
        'porteira_efficiency': get_porteira_efficiency_score(user_id, ciclo=ciclo),
        'performance_hourly': get_performance_by_hour(user_id),
        'activity_timeline': get_activity_timeline(user_id, days=7),
        'comparative': get_comparative_metrics(user_id, days=7)
    }


# ==========================================
# FUNÇÕES DE COMPATIBILIDADE
# ==========================================

def releituras_pendentes(user_id=None):
    """
    Retorna o número de leituras pendentes (compatibilidade)
    
    Returns:
        int: Número de leituras pendentes
    """
    if user_id is None:
        # Fallback para comportamento antigo
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM releituras WHERE status = 'PENDENTE'")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    
    overview = get_system_overview(user_id)
    return overview['releituras_pendentes']
