"""
Módulo de Coleta de Dados (Web Scraper) - Portal CEMIG SGL

Este módulo automatiza a extração de relatórios (Releitura e Porteira) do portal SGL.
Utiliza Selenium para automação web e PyAutoGUI para interação com componentes 
do sistema operacional (Certificados Digitais).

Design Patterns e Estratégias:
    - Lazy Imports: Dependências (Selenium/PyAutoGUI) carregadas apenas sob demanda.
    - Path Resolution: Localização dinâmica da raiz do projeto para portabilidade.
    - Multithreading: Tratamento concorrente para janelas de diálogo do Windows.
"""

from __future__ import annotations

import os
import time
import threading
from pathlib import Path

# --- Configurações Globais (Variáveis de Ambiente) ---
URL_PORTAL = os.getenv("PORTAL_URL", "https://sglempreiteira.cemig.com.br/SGLEmpreiteira")
UNIDADE_PADRAO_DE = os.getenv("PORTAL_UNIDADE_DE", "01000000")
UNIDADE_PADRAO_ATE = os.getenv("PORTAL_UNIDADE_ATE", "18999999")


def _find_project_root() -> Path:
    """
    Localiza a raiz do projeto LOGOS DECISION subindo na árvore de diretórios.
    Busca por marcadores estruturais como 'frontend', 'data' ou '.env'.
    """
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "frontend").exists() and (parent / "backend").exists():
            return parent
        if (parent / ".env").exists() and (parent / "data").exists():
            return parent
    return here.parents[2]


def _default_download_dir() -> Path:
    """Define o caminho absoluto para o diretório de exportações de dados."""
    return _find_project_root() / "data" / "exports"


def _clear_download_dir(download_dir: Path) -> None:
    """
    Remove arquivos residuais no diretório de destino.
    Garante que a análise subsequente processe apenas os dados coletados agora.
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    for f in download_dir.iterdir():
        try:
            if f.is_file():
                f.unlink()
        except Exception:
            pass





def switch_to_main_tab(driver):
    """Garante o foco do WebDriver na aba principal do navegador."""
    driver.switch_to.window(driver.window_handles[0])


def _latest_file(download_dir: Path) -> Path | None:
    """Identifica o arquivo mais recente via timestamp de modificação."""
    files = [p for p in download_dir.iterdir() if p.is_file()]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def _wait_download_finished(download_dir: Path, timeout: int = 120) -> bool:
    """
    Aguarda a finalização do download monitorando arquivos temporários do Chrome.
    """
    end = time.time() + timeout
    while time.time() < end:
        try:
            unfinished = list(download_dir.glob("*.crdownload")) + list(download_dir.glob("*.tmp"))
            if unfinished:
                time.sleep(1)
                continue

            latest = _latest_file(download_dir)
            if latest is not None and latest.stat().st_size > 0:
                return True
        except FileNotFoundError:
            pass
        time.sleep(1)
    return False


def download_releitura_excel(
    portal_user: str | None = None,
    portal_pass: str | None = None,
    download_dir: str | os.PathLike | None = None,
    unidade_de: str | None = None,
    unidade_ate: str | None = None,
    timeout: int = 120,
) -> str:
    """
    Automatiza a coleta do relatório de Releituras Não Executadas.
    Inclui lógica de foco de janela para sobreposição ao VS Code.
    """
    try:
        import pyautogui
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options
        from dotenv import load_dotenv
    except Exception as e:
        raise RuntimeError(f"Dependências ausentes (Selenium/PyAutoGUI/Dotenv): {e}")
    
    # Configuração de Ambiente
    project_root = _find_project_root()
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))

    user = portal_user or os.getenv("PORTAL_USER")
    password = portal_pass or os.getenv("PORTAL_PASS")
    if not user or not password:
        raise RuntimeError("Credenciais de acesso não configuradas no .env")

    dl_dir = Path(download_dir) if download_dir else _default_download_dir()
    _clear_download_dir(dl_dir)

    # Localizadores de Interface (XPaths/IDs)
    LOC_USER = (By.ID, "UserName")
    LOC_PASS = (By.ID, "Password")
    LOC_BTN_LOGIN = (By.XPATH, "//button[text()='Login']")
    LOC_MENU_RELATORIOS = (By.XPATH, "//ul[@id='side-menu']//li//span[text()='RELATÓRIOS']")
    LOC_RELEITURA_HREF = (By.XPATH, "//a[contains(@href,'/SGLEmpreiteira/Relatorios/RlReleituraNaoExecutada')]")
    LOC_RELEITURA_TEXT = (By.XPATH, "//a[contains(.,'Releit') or contains(.,'RELEIT')]")
    LOC_MES_ANO = (By.ID, "txtMesAno")
    LOC_DATA_HOJE = (By.XPATH, "/html/body/div[3]/div[2]/table/tfoot/tr[1]/th")
    LOC_BTN_GERAR = (By.ID, "btnGerarExcel")

    def handle_certificate():
        """Rotina para confirmar o diálogo de certificado digital via teclado."""
        time.sleep(5)
        try:
            pyautogui.press("enter")
            time.sleep(1)
            pyautogui.press("enter")
        except Exception:
            pass

    # Configuração do Navegador
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized") # Garante foco e visibilidade

    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-notifications")
    
    if os.getenv("PORTAL_DETACH", "0") == "1":
        chrome_options.add_experimental_option("detach", True)
    
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    prefs = {
        "download.default_directory": str(dl_dir),
        "download.prompt_for_download": False,
        "directory_upgrade": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # Monitoramento do Certificado em Thread Paralela
    if os.getenv("PORTAL_HANDLE_CERT", "1") == "1":
        threading.Thread(target=handle_certificate, daemon=True).start()

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 30)

    try:
        driver.get(URL_PORTAL)
        # ATIVAÇÃO FORÇADA: Traz o navegador para frente do VS Code
        driver.switch_to.window(driver.current_window_handle)
        
        # Fluxo de Autenticação
        wait.until(EC.element_to_be_clickable(LOC_USER)).send_keys(user)
        driver.find_element(*LOC_PASS).send_keys(password)
        wait.until(EC.element_to_be_clickable(LOC_BTN_LOGIN)).click()

        # Navegação no Menu
        wait.until(EC.element_to_be_clickable(LOC_MENU_RELATORIOS)).click()
        try:
            link = wait.until(EC.presence_of_element_located(LOC_RELEITURA_HREF))
        except Exception:
            link = wait.until(EC.presence_of_element_located(LOC_RELEITURA_TEXT))
        driver.execute_script("arguments[0].click();", link)

        # Filtros Temporais
        wait.until(EC.element_to_be_clickable(LOC_MES_ANO)).click()
        wait.until(EC.element_to_be_clickable(LOC_DATA_HOJE)).click()

        # Download
        wait.until(EC.element_to_be_clickable(LOC_BTN_GERAR)).click()

        if not _wait_download_finished(dl_dir, timeout=timeout):
            raise RuntimeError("Timeout no download.")

        return str(_latest_file(dl_dir))
    finally:
        try:
            driver.quit()
        except:
            pass

def download_porteira_excel(
    portal_user: str | None = None,
    portal_pass: str | None = None,
    download_dir: str | os.PathLike | None = None,
    unidade_de: str | None = None,
    unidade_ate: str | None = None,
    report_date: str | None = None,
    timeout: int = 120,
) -> str:
    """
    Automatiza a coleta do relatório de Acompanhamento de Resultado (Porteira).
    Lógica de navegação específica para range de unidades.
    """
    try:
        import pyautogui
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options
        from dotenv import load_dotenv
    except Exception as e:
        raise RuntimeError(f"Dependências ausentes: {e}")

    project_root = _find_project_root()
    load_dotenv(dotenv_path=str(project_root / ".env"))

    user = portal_user or os.getenv("PORTAL_USER")
    password = portal_pass or os.getenv("PORTAL_PASS")
    
    dl_dir = Path(download_dir) if download_dir else _default_download_dir()
    _clear_download_dir(dl_dir)

    unidade_de = unidade_de or UNIDADE_PADRAO_DE
    unidade_ate = unidade_ate or UNIDADE_PADRAO_ATE

    # Localizadores específicos da Porteira
    LOC_USER = (By.ID, "UserName")
    LOC_PASS = (By.ID, "Password")
    LOC_BTN_LOGIN = (By.XPATH, "//button[text()='Login']")
    LOC_MENU_RELATORIOS = (By.XPATH, "//ul[@id='side-menu']//li//span[text()='RELATÓRIOS']")
    LOC_PORTEIRA_HREF = (By.XPATH, "//a[contains(@href,'/SGLEmpreiteira/Relatorios/RlAcompanhamentoResultadoLeitura')]")
    LOC_PORTEIRA_TEXT = (By.XPATH, "//a[contains(.,'Acompanh') or contains(.,'Resultado')]")
    LOC_MES_ANO = (By.ID, "txtMesAno")
    LOC_DATA_HOJE = (By.XPATH, "/html/body/div[3]/div[2]/table/tfoot/tr[1]/th")
    LOC_UNIDADE_INI = (By.ID, "txtUnidadeLeituraIni")
    LOC_UNIDADE_FIM = (By.ID, "txtUnidadeLeituraFim")
    LOC_BTN_GERAR = (By.ID, "btnGerarExcel")

    def handle_certificate():
        time.sleep(5)
        try:
            pyautogui.press("enter")
            time.sleep(1)
            pyautogui.press("enter")
        except:
            pass

    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-notifications")

    prefs = {
        "download.default_directory": str(dl_dir),
        "download.prompt_for_download": False,
        "directory_upgrade": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    if os.getenv("PORTAL_HANDLE_CERT", "1") == "1":
        threading.Thread(target=handle_certificate, daemon=True).start()

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 30)

    try:
        driver.get(URL_PORTAL)
        driver.switch_to.window(driver.current_window_handle)

        # Login
        wait.until(EC.element_to_be_clickable(LOC_USER)).send_keys(user)
        driver.find_element(*LOC_PASS).send_keys(password)
        wait.until(EC.element_to_be_clickable(LOC_BTN_LOGIN)).click()

        # Navegação
        wait.until(EC.element_to_be_clickable(LOC_MENU_RELATORIOS)).click()
        try:
            link = wait.until(EC.presence_of_element_located(LOC_PORTEIRA_HREF))
        except Exception:
            link = wait.until(EC.presence_of_element_located(LOC_PORTEIRA_TEXT))
        driver.execute_script("arguments[0].click();", link)

        # Seleção de Data
        mes_ano_el = wait.until(EC.element_to_be_clickable(LOC_MES_ANO))
        mes_ano_el.click()

        if report_date:
            try:
                # Normalização de formato de data para MM/YYYY
                if "-" in report_date:
                    y, m, _d = report_date.split("-", 2)
                else:
                    _d, m, y = report_date.split("/", 2)
                mm_yyyy = f"{int(m):02d}/{int(y)}"
                mes_ano_el.clear()
                mes_ano_el.send_keys(mm_yyyy)
            except:
                wait.until(EC.element_to_be_clickable(LOC_DATA_HOJE)).click()
        else:
            wait.until(EC.element_to_be_clickable(LOC_DATA_HOJE)).click()

        # Filtro de Unidades
        ini = wait.until(EC.element_to_be_clickable(LOC_UNIDADE_INI))
        fim = driver.find_element(*LOC_UNIDADE_FIM)
        for el, val in ((ini, unidade_de), (fim, unidade_ate)):
            el.send_keys(Keys.CONTROL, 'a')
            el.send_keys(Keys.DELETE)
            el.send_keys(val)

        # Download
        wait.until(EC.element_to_be_clickable(LOC_BTN_GERAR)).click()

        if not _wait_download_finished(dl_dir, timeout=timeout):
            raise RuntimeError("Falha no download da Porteira.")

        return str(_latest_file(dl_dir))
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    # Teste de execução direta
    print("Portal scraper rodando.")