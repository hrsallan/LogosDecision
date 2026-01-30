"""
Scheduler Automático - VigilaCore
Executa downloads automáticos de relatórios em horários configurados.

Configuração via .env:
    SCHEDULER_ENABLED=1                  # Habilita scheduler (0=desabilitado)
    SCHEDULER_START_HOUR=7               # Hora de início (padrão: 7h)
    SCHEDULER_END_HOUR=17                # Hora de fim (padrão: 17h)
    SCHEDULER_INTERVAL_MINUTES=60        # Intervalo em minutos (padrão: 60 = 1 hora)
    SCHEDULER_AUTO_RELEITURA=1           # Auto-download de releitura (padrão: 1)
    SCHEDULER_AUTO_PORTEIRA=1            # Auto-download de porteira (padrão: 1)
    SCHEDULER_USER_ID=1                  # ID do usuário para salvar dados (obrigatório)
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutoScheduler:
    """Gerenciador de downloads automáticos"""
    
    def __init__(self):
        self.scheduler = None
        self.enabled = False
        self.start_hour = 7
        self.end_hour = 17
        self.interval_minutes = 60
        self.auto_releitura = True
        self.auto_porteira = True
        self.user_id = None
        self.is_running = False
        
        # Carregar configurações do .env
        self._load_config()
    
    def _load_config(self):
        """Carrega configurações do arquivo .env"""
        # Encontrar o .env na raiz do projeto
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
        
        # Ler configurações
        self.enabled = os.getenv("SCHEDULER_ENABLED", "0") == "1"
        self.start_hour = int(os.getenv("SCHEDULER_START_HOUR", "7"))
        self.end_hour = int(os.getenv("SCHEDULER_END_HOUR", "17"))
        self.interval_minutes = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "60"))
        self.auto_releitura = os.getenv("SCHEDULER_AUTO_RELEITURA", "1") == "1"
        self.auto_porteira = os.getenv("SCHEDULER_AUTO_PORTEIRA", "1") == "1"
        
        user_id_str = os.getenv("SCHEDULER_USER_ID")
        if user_id_str and user_id_str.isdigit():
            self.user_id = int(user_id_str)
        
        logger.info(f"📋 Configurações do Scheduler:")
        logger.info(f"   - Habilitado: {self.enabled}")
        logger.info(f"   - Horário: {self.start_hour}h às {self.end_hour}h")
        logger.info(f"   - Intervalo: {self.interval_minutes} minutos")
        logger.info(f"   - Auto Releitura: {self.auto_releitura}")
        logger.info(f"   - Auto Porteira: {self.auto_porteira}")
        logger.info(f"   - User ID: {self.user_id}")
    
    def _is_within_schedule(self) -> bool:
        """Verifica se está dentro do horário configurado"""
        now = datetime.now()
        current_hour = now.hour
        
        # Verificar se está dentro do intervalo de horas
        if self.start_hour <= self.end_hour:
            # Intervalo normal (ex: 7h às 17h)
            return self.start_hour <= current_hour < self.end_hour
        else:
            # Intervalo que cruza meia-noite (ex: 22h às 6h)
            return current_hour >= self.start_hour or current_hour < self.end_hour
    
    def _execute_releitura_sync(self):
        """Executa download e processamento de releitura"""
        if not self.auto_releitura:
            return
        
        if not self._is_within_schedule():
            logger.info("⏰ Fora do horário agendado - pulando sync de releitura")
            return
        
        logger.info("🔄 Iniciando sync automático de RELEITURA...")
        
        try:
            from core.portal_scraper import download_releitura_excel
            from core.analytics import get_file_hash, deep_scan_excel
            from core.database import is_file_duplicate, save_releitura_data
            
            if not self.user_id:
                logger.error("❌ SCHEDULER_USER_ID não configurado no .env")
                return
            
            # Download
            downloaded_path = download_releitura_excel()
            if not downloaded_path or not os.path.exists(downloaded_path):
                logger.error("❌ Falha no download do relatório de releitura")
                return
            
            logger.info(f"✅ Arquivo baixado: {downloaded_path}")
            
            # Processar
            file_hash = get_file_hash(downloaded_path)
            details = deep_scan_excel(downloaded_path) or []
            
            if not details:
                logger.warning("⚠️ Nenhum dado encontrado no Excel de releitura")
                return
            
            # Verificar duplicata
            if is_file_duplicate(file_hash, 'releitura', self.user_id):
                logger.info("ℹ️ Relatório já processado anteriormente (duplicado)")
                return
            
            # Salvar
            save_releitura_data(details, file_hash, self.user_id)
            logger.info(f"✅ Releitura sincronizada: {len(details)} registros processados")
            
        except Exception as e:
            logger.error(f"❌ Erro no sync de releitura: {e}", exc_info=True)
    
    def _execute_porteira_sync(self):
        """Executa download e processamento de porteira"""
        if not self.auto_porteira:
            return
        
        if not self._is_within_schedule():
            logger.info("⏰ Fora do horário agendado - pulando sync de porteira")
            return
        
        logger.info("🔄 Iniciando sync automático de PORTEIRA...")
        
        try:
            from core.portal_scraper import download_porteira_excel
            from core.analytics import get_file_hash, deep_scan_porteira_excel
            from core.database import is_file_duplicate, save_porteira_table_data, save_file_history
            
            if not self.user_id:
                logger.error("❌ SCHEDULER_USER_ID não configurado no .env")
                return
            
            # Download
            downloaded_path = download_porteira_excel()
            if not downloaded_path or not os.path.exists(downloaded_path):
                logger.error("❌ Falha no download do relatório de porteira")
                return
            
            logger.info(f"✅ Arquivo baixado: {downloaded_path}")
            
            # Processar
            file_hash = get_file_hash(downloaded_path)
            details = deep_scan_porteira_excel(downloaded_path)
            
            if details is None or not details:
                logger.warning("⚠️ Nenhum dado encontrado no Excel de porteira")
                return
            
            # Verificar duplicata
            if is_file_duplicate(file_hash, 'porteira', self.user_id):
                logger.info("ℹ️ Relatório já processado anteriormente (duplicado)")
                return
            
            # Salvar
            save_porteira_table_data(details, self.user_id)
            save_file_history('porteira', len(details), file_hash, self.user_id)
            logger.info(f"✅ Porteira sincronizada: {len(details)} registros processados")
            
        except Exception as e:
            logger.error(f"❌ Erro no sync de porteira: {e}", exc_info=True)
    
    def start(self):
        """Inicia o scheduler"""
        if not self.enabled:
            logger.info("ℹ️ Scheduler desabilitado (SCHEDULER_ENABLED=0)")
            return
        
        if self.is_running:
            logger.warning("⚠️ Scheduler já está rodando")
            return
        
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            logger.error("❌ APScheduler não instalado. Execute: pip install apscheduler")
            return
        
        if not self.user_id:
            logger.error("❌ SCHEDULER_USER_ID não configurado no .env - scheduler não iniciado")
            return
        
        self.scheduler = BackgroundScheduler()
        
        # Adicionar job de releitura
        if self.auto_releitura:
            # Executa a cada X minutos dentro do horário configurado
            self.scheduler.add_job(
                self._execute_releitura_sync,
                'interval',
                minutes=self.interval_minutes,
                id='releitura_sync',
                name='Sync Automático - Releitura',
                max_instances=1,
                replace_existing=True
            )
            logger.info(f"✅ Job de RELEITURA agendado (a cada {self.interval_minutes} min)")
        
        # Adicionar job de porteira
        if self.auto_porteira:
            self.scheduler.add_job(
                self._execute_porteira_sync,
                'interval',
                minutes=self.interval_minutes,
                id='porteira_sync',
                name='Sync Automático - Porteira',
                max_instances=1,
                replace_existing=True
            )
            logger.info(f"✅ Job de PORTEIRA agendado (a cada {self.interval_minutes} min)")
        
        # Iniciar scheduler
        self.scheduler.start()
        self.is_running = True
        
        logger.info("🚀 Scheduler automático iniciado com sucesso!")
        logger.info(f"⏰ Execuções programadas: {self.start_hour}h às {self.end_hour}h")
        
        # Executar imediatamente se estiver no horário
        if self._is_within_schedule():
            logger.info("⚡ Executando sync inicial imediatamente...")
            if self.auto_releitura:
                self._execute_releitura_sync()
            if self.auto_porteira:
                self._execute_porteira_sync()
    
    def stop(self):
        """Para o scheduler"""
        if self.scheduler and self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("⏹️ Scheduler parado")
    
    def get_status(self) -> dict:
        """Retorna status do scheduler"""
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
            'schedule': f"{self.start_hour}h - {self.end_hour}h",
            'interval_minutes': self.interval_minutes,
            'auto_releitura': self.auto_releitura,
            'auto_porteira': self.auto_porteira,
            'user_id': self.user_id,
            'within_schedule': self._is_within_schedule(),
            'jobs': jobs
        }


# Instância global do scheduler
_scheduler_instance = None


def get_scheduler() -> AutoScheduler:
    """Retorna a instância única do scheduler"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = AutoScheduler()
    return _scheduler_instance


def init_scheduler():
    """Inicializa e inicia o scheduler (chamado no app.py)"""
    scheduler = get_scheduler()
    scheduler.start()
    return scheduler


if __name__ == "__main__":
    # Teste standalone
    print("🧪 Testando scheduler...")
    scheduler = get_scheduler()
    print(f"Status: {scheduler.get_status()}")
    
    if scheduler.enabled:
        scheduler.start()
        print("Scheduler iniciado. Pressione Ctrl+C para parar.")
        try:
            import time
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            scheduler.stop()
            print("\n👋 Scheduler parado")
    else:
        print("⚠️ Scheduler desabilitado no .env")
