"""
Módulo de Agendamento Automático (Scheduler)

Gerencia o download e processamento automático de relatórios em intervalos configurados.
Utiliza a biblioteca APScheduler para agendar tarefas em background.

Configuração (.env):
    SCHEDULER_ENABLED=1                  # 1 para ligar, 0 para desligar
    SCHEDULER_START_HOUR=5               # Hora de início (ex: 5h)
    SCHEDULER_END_HOUR=22                # Hora de término (ex: 22h)
    SCHEDULER_INTERVAL_MINUTES=60        # Intervalo entre execuções
    SCHEDULER_MANAGER_USERNAME=GRTRI     # Usuário Gerente (dono das credenciais do portal)
"""

import os
import logging
import threading
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutoScheduler:
    """
    Gerenciador singleton de tarefas agendadas.
    Controla o ciclo de vida do scheduler e a execução sequencial das sincronizações.
    """
    
    def __init__(self):
        self.scheduler = None
        self.enabled = False
        self.start_hour = 5
        self.end_hour = 22
        self.interval_minutes = 60
        self.auto_releitura = True
        self.auto_porteira = True
        self.user_id = None
        self.portal_manager_username = "GRTRI"
        self.is_running = False
        
        # Lock para evitar concorrência de jobs (uma sincronização por vez)
        self._run_lock = threading.Lock()

        # Carregar configurações iniciais
        self._load_config()
    
    def _load_config(self):
        """Lê configurações do arquivo .env e variáveis de ambiente."""
        try:
            current = Path(__file__).resolve()
            for parent in [current] + list(current.parents):
                env_path = parent / ".env"
                if env_path.exists():
                    load_dotenv(dotenv_path=str(env_path))
                    logger.info(f"✅ Arquivo .env carregado de: {env_path}")
                    break
        except Exception as e:
            logger.warning(f"⚠️ Erro ao carregar .env: {e}")
        
        self.enabled = os.getenv("SCHEDULER_ENABLED", "0") == "1"
        self.start_hour = int(os.getenv("SCHEDULER_START_HOUR", "5"))
        self.end_hour = int(os.getenv("SCHEDULER_END_HOUR", "22"))
        self.interval_minutes = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "60"))
        self.auto_releitura = os.getenv("SCHEDULER_AUTO_RELEITURA", "1") == "1"
        self.auto_porteira = os.getenv("SCHEDULER_AUTO_PORTEIRA", "1") == "1"

        self.portal_manager_username = (
            os.getenv("SCHEDULER_MANAGER_USERNAME", self.portal_manager_username).strip()
            or self.portal_manager_username
        )
        
        user_id_str = os.getenv("SCHEDULER_USER_ID")
        if user_id_str and user_id_str.isdigit():
            self.user_id = int(user_id_str)
        
        logger.info(f"📋 Configurações do Scheduler:")
        logger.info(f"   - Habilitado: {self.enabled}")
        logger.info(f"   - Horário: {self._schedule_display()}")
        logger.info(f"   - Intervalo: {self.interval_minutes} minutos")
        logger.info(f"   - Auto Releitura: {self.auto_releitura}")
        logger.info(f"   - Auto Porteira: {self.auto_porteira}")
        logger.info(f"   - User ID Alvo: {self.user_id}")
        logger.info(f"   - Gerente do Portal: {self.portal_manager_username}")

    def _schedule_display(self) -> str:
        """Formata o horário de funcionamento para exibição."""
        end_inclusive = (self.end_hour - 1) % 24
        return f"{self.start_hour:02d}:00 - {end_inclusive:02d}:00"

    
    def _is_within_schedule(self) -> bool:
        """Verifica se o horário atual está dentro da janela permitida."""
        now = datetime.now()
        current_hour = now.hour
        
        if self.start_hour <= self.end_hour:
            # Intervalo intra-dia (ex: 07:00 às 17:00)
            return self.start_hour <= current_hour < self.end_hour
        else:
            # Intervalo que cruza a meia-noite (ex: 22:00 às 06:00)
            return current_hour >= self.start_hour or current_hour < self.end_hour
    
    
    def _build_cron_trigger(self):
        """
        Constrói um gatilho Cron (CronTrigger) para o APScheduler.
        Garante execução em minutos 'redondos' (ex: 09:00, 09:30) em vez de relativos ao start.
        """
        from apscheduler.triggers.cron import CronTrigger

        # Define faixa de horas
        if self.start_hour <= self.end_hour:
            start = self.start_hour
            end_inclusive = max(self.start_hour, self.end_hour - 1)
            hour_expr_base = f"{start}-{end_inclusive}"
        else:
            end_inclusive = self.end_hour - 1
            if end_inclusive >= 0:
                hour_expr_base = f"{self.start_hour}-23,0-{end_inclusive}"
            else:
                hour_expr_base = f"{self.start_hour}-23"

        minutes = int(self.interval_minutes)

        # Caso 1: Intervalo em horas exatas (ex: a cada 1h, 2h...)
        if minutes % 60 == 0:
            step_h = max(1, minutes // 60)
            hour_expr = f"{hour_expr_base}/{step_h}" if step_h > 1 else hour_expr_base
            return CronTrigger(minute=0, second=0, hour=hour_expr)

        # Caso 2: Divisor de hora (ex: 15min, 30min)
        if 60 % minutes == 0:
            minute_expr = f"*/{minutes}" if minutes != 60 else "0"
            return CronTrigger(minute=minute_expr, second=0, hour=hour_expr_base)

        # Fallback: Intervalo genérico
        return CronTrigger(minute=f"*/{minutes}", second=0, hour=hour_expr_base)

    def _get_scheduler_portal_credentials(self):
        """
        Busca as credenciais do Portal atribuídas ao usuário 'Gerente' no banco de dados.
        Retorna (credenciais, user_id_do_gerente).
        """
        try:
            from core.database import get_user_id_by_username, get_portal_credentials
        except Exception as e:
            logger.error(f"❌ Erro de importação DB: {e}")
            return None, None

        manager_username = (self.portal_manager_username or "").strip() or "GRTRI"
        manager_id = get_user_id_by_username(manager_username)
        if not manager_id:
            logger.warning(
                f"⚠️ Scheduler: Usuário gerente '{manager_username}' não encontrado."
            )
            return None, None

        creds = get_portal_credentials(int(manager_id))
        if not creds:
            logger.warning(
                f"⚠️ Scheduler: Credenciais do portal não configuradas para '{manager_username}'."
            )
            return None, int(manager_id)

        return creds, int(manager_id)

    def _execute_releitura_sync(self):
        """Executa a sincronização de Releitura (Regional)."""
        if not self.auto_releitura:
            return

        if not self._is_within_schedule():
            logger.info("⏰ Fora do horário agendado - pulando sync de Releitura")
            return

        logger.info("🔄 Iniciando sync automático de RELEITURA...")

        try:
            # Chama a função de tarefa isolada
            sync_releitura_task()
        except Exception as e:
            logger.error(f"❌ Erro no sync de Releitura: {e}", exc_info=True)

    def _execute_porteira_sync(self):
        """Executa a sincronização de Porteira."""
        if not self.auto_porteira:
            return
        
        if not self._is_within_schedule():
            logger.info("⏰ Fora do horário agendado - pulando sync de Porteira")
            return
        
        logger.info("🔄 Iniciando sync automático de PORTEIRA...")
        
        try:
            from core.portal_scraper import download_porteira_excel
            from core.analytics import get_file_hash, deep_scan_porteira_excel
            from core.database import is_file_duplicate, save_porteira_table_data, save_file_history
            from core.portal_scraper import _default_download_dir

            creds, manager_id = self._get_scheduler_portal_credentials()
            if not creds:
                return

            # Prioriza ID configurado, senão usa ID do gerente
            save_user_id = int(self.user_id) if self.user_id else int(manager_id) if manager_id else None
            if not save_user_id:
                logger.error("❌ Scheduler: Nenhum user_id alvo definido.")
                return

            # Download
            downloaded_path = download_porteira_excel(
                portal_user=creds['portal_user'],
                portal_pass=creds['portal_password'],
                download_dir=str(_default_download_dir()),
            )
            if not downloaded_path or not os.path.exists(downloaded_path):
                logger.error("❌ Falha no download do relatório de porteira")
                return
            
            logger.info(f"✅ Arquivo baixado: {downloaded_path}")
            
            # Processamento
            file_hash = get_file_hash(downloaded_path)
            details = deep_scan_porteira_excel(downloaded_path)
            
            if details is None or not details:
                logger.warning("⚠️ Nenhum dado extraído do Excel de Porteira")
                return
            
            # Verificação de duplicidade
            if is_file_duplicate(file_hash, 'porteira', save_user_id):
                logger.info("ℹ️ Relatório já processado anteriormente (ignorado)")
                return
            
            # Distribuição para todos os usuários (para que cada um veja sua base)
            try:
                import sqlite3
                from core.database import DB_PATH as _DB
                conn = sqlite3.connect(str(_DB))
                cur = conn.cursor()
                cur.execute('SELECT id FROM users')
                all_ids = [int(r[0]) for r in cur.fetchall() if r and r[0] is not None]
                conn.close()
            except Exception:
                all_ids = [int(save_user_id)]

            for _uid in all_ids:
                save_porteira_table_data(details, _uid, file_hash=file_hash)

            # Salva histórico apenas para o usuário alvo/gerente
            save_file_history('porteira', len(details), file_hash, save_user_id)
            logger.info(f"✅ Porteira sincronizada: {len(details)} registros processados")
            
        except Exception as e:
            logger.error(f"❌ Erro no sync de Porteira: {e}", exc_info=True)
    

    def _execute_all_sync(self):
        """
        Executa as sincronizações sequencialmente (Releitura -> Porteira).
        O uso de Lock garante que não haja sobreposição de execuções.
        """
        if not (self.auto_releitura or self.auto_porteira):
            return

        # Tenta adquirir o lock sem bloquear
        if not self._run_lock.acquire(blocking=False):
            logger.warning("⚠️ Sync automático já em execução. Ignorando novo disparo.")
            return

        try:
            logger.info("🧩 Iniciando ciclo de sincronização sequencial...")
            if self.auto_releitura:
                self._execute_releitura_sync()
            if self.auto_porteira:
                self._execute_porteira_sync()
            logger.info("✅ Ciclo de sincronização finalizado.")
        finally:
            try:
                self._run_lock.release()
            except Exception:
                pass

    def start(self):
        """Inicia o agendamento de tarefas."""
        if not self.enabled:
            logger.info("ℹ️ Scheduler desabilitado no .env")
            return
        
        if self.is_running:
            logger.warning("⚠️ Scheduler já está em execução")
            return
        
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError:
            logger.error("❌ APScheduler não instalado.")
            return
        
        self.scheduler = BackgroundScheduler(timezone=os.getenv("SCHEDULER_TIMEZONE", "America/Sao_Paulo"))
        
        trigger = self._build_cron_trigger()

        # Adiciona o job único sequencial
        self.scheduler.add_job(
            self._execute_all_sync,
            trigger=trigger,
            id='auto_sync_sequencial',
            name='Sync Sequencial (Releitura -> Porteira)',
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=300,
        )
        logger.info("✅ Tarefa agendada com sucesso.")

        self.scheduler.start()
        self.is_running = True
        
        logger.info("🚀 Scheduler automático iniciado!")
        logger.info(f"⏰ Horário configurado: {self._schedule_display()}")


    def stop(self):
        """Para o agendamento."""
        if self.scheduler and self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("⏹️ Scheduler parado")
    
    def get_status(self) -> dict:
        """Retorna o estado atual do scheduler para a API."""
        jobs = []
        if self.scheduler and self.is_running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None
                })
        
        return {
            'enabled': self.enabled,
            'running': self.is_running,
            'schedule': self._schedule_display(),
            'interval_minutes': self.interval_minutes,
            'auto_releitura': self.auto_releitura,
            'auto_porteira': self.auto_porteira,
            'user_id': self.user_id,
            'within_schedule': self._is_within_schedule(),
            'jobs': jobs
        }


# Singleton Global
_scheduler_instance = None


def get_scheduler() -> AutoScheduler:
    """Retorna a instância singleton do scheduler."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = AutoScheduler()
    return _scheduler_instance


def init_scheduler():
    """Função auxiliar para inicialização (usada pelo app.py)."""
    scheduler = get_scheduler()
    scheduler.start()
    return scheduler


if __name__ == "__main__":
    # Teste isolado do módulo
    print("🧪 Testando Scheduler...")
    scheduler = get_scheduler()
    print(f"Status: {scheduler.get_status()}")
    
    if scheduler.enabled:
        scheduler.start()
        print("Pressione Ctrl+C para encerrar.")
        try:
            import time
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            scheduler.stop()
            print("\n👋 Encerrado.")
    else:
        print("⚠️ Habilite no .env para testar.")

# -------------------------------
# Tarefa Isolada: Releitura
# -------------------------------
def sync_releitura_task():
    """
    Lógica isolada de sincronização de Releitura.
    Baixa arquivo, roteia e salva no banco.
    """
    try:
        from core.database import get_user_id_by_username, get_portal_credentials, get_releitura_region_targets, get_user_id_by_matricula, save_releitura_data
        from core.portal_scraper import download_releitura_excel
        from core.analytics import deep_scan_excel, get_file_hash
        from core.releitura_routing_v2 import route_releituras
        import os

        manager_username = (os.environ.get("RELEITURA_MANAGER_USERNAME") or "GRTRI").strip()
        manager_id = get_user_id_by_username(manager_username)
        if not manager_id:
            print(f"⚠️ [scheduler] Gerente '{manager_username}' não encontrado. Abortando.")
            return

        creds = get_portal_credentials(manager_id)
        if not creds:
            print(f"⚠️ [scheduler] Credenciais não configuradas para '{manager_username}'.")
            return

        downloaded_path = download_releitura_excel(portal_user=creds['portal_user'], portal_pass=creds['portal_password'])
        if not downloaded_path or not os.path.exists(downloaded_path):
            print("❌ [scheduler] Download falhou.")
            return

        file_hash = get_file_hash(downloaded_path)
        details = deep_scan_excel(downloaded_path)
        
        # Roteamento V2
        details_v2 = route_releituras(details)
        
        routed_map = {"Araxá": [], "Uberaba": [], "Frutal": []}
        unrouted_list = []
        for it in details_v2:
            reg = it.get("region")
            if it.get("route_status") == "ROUTED" and reg in routed_map:
                routed_map[reg].append(it)
            else:
                unrouted_list.append(it)

        targets = get_releitura_region_targets()

        # Distribui para os responsáveis regionais
        for region, items in routed_map.items():
            matricula = targets.get(region)
            uid = get_user_id_by_matricula(matricula) if matricula else None

            if not uid:
                # Sem responsável -> vai para o gerente como UNROUTED
                for it in items:
                    it["route_status"]="UNROUTED"
                    it["route_reason"]="REGIAO_SEM_MATRICULA"
                    it["region"]=region
                if items:
                    save_releitura_data(items, file_hash, manager_id)
                continue

            if items:
                save_releitura_data(items, file_hash, uid)

        # Salva não roteados no gerente
        if unrouted_list:
            save_releitura_data(unrouted_list, file_hash, manager_id)

        print("✅ [scheduler] Releitura sincronizada com sucesso.")
    except Exception as e:
        print(f"❌ [scheduler] Erro no sync de Releitura: {e}")
