"""
Módulo de Coleta de Dados (Web Scraper) - Portal CEMIG SGL

Este módulo automatiza o download de relatórios do portal SGL usando Selenium.
Ele é implementado com importações preguiçosas (lazy imports) para permitir
que o backend inicie mesmo sem as dependências de scraping instaladas.

Diretório padrão de download:
    VigilaCore/data/exports/
"""

from __future__ import annotations

import os
import time
import threading
from pathlib import Path

# --- Configurações Padrão (podem ser sobrescritas por variáveis de ambiente) ---
URL_PORTAL = os.getenv("PORTAL_URL", "https://sglempreiteira.cemig.com.br/SGLEmpreiteira")
UNIDADE_PADRAO_DE = os.getenv("PORTAL_UNIDADE_DE", "01000000")
UNIDADE_PADRAO_ATE = os.getenv("PORTAL_UNIDADE_ATE", "18999999")


def _find_project_root() -> Path:
    """
    Encontra a raiz do projeto VigilaCore de forma robusta.
    Procura pelas pastas 'frontend' e 'data' ou pelo arquivo '.env'.

    Retorna:
        Path: Caminho absoluto para a raiz do projeto.
    """
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "frontend").exists() and (parent / "backend").exists():
            return parent
        if (parent / ".env").exists() and (parent / "data").exists():
            return parent
    # Fallback para estrutura antiga: backend/core -> backend -> root
    return here.parents[2]


def _default_download_dir() -> Path:
    """Retorna o diretório padrão de downloads."""
    return _find_project_root() / "data" / "exports"


def _clear_download_dir(download_dir: Path) -> None:
    """
    Limpa arquivos existentes no diretório de download para evitar confusão
    entre downloads anteriores e o atual.
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    for f in download_dir.iterdir():
        try:
            if f.is_file():
                f.unlink()
        except Exception:
            pass

def switch_to_main_tab(driver):
    """Foca na aba principal do navegador."""
    driver.switch_to.window(driver.window_handles[0])

def _latest_file(download_dir: Path) -> Path | None:
    """Retorna o arquivo mais recente no diretório."""
    files = [p for p in download_dir.iterdir() if p.is_file()]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def _wait_download_finished(download_dir: Path, timeout: int = 120) -> bool:
    """
    Aguarda o término do download verificando a inexistência de arquivos temporários (.crdownload/.tmp).

    Argumentos:
        download_dir (Path): Diretório onde o arquivo está sendo baixado.
        timeout (int): Tempo máximo de espera em segundos.

    Retorna:
        bool: True se o download for concluído com sucesso, False caso contrário.
    """
    end = time.time() + timeout
    while time.time() < end:
        try:
            # Verifica arquivos temporários do Chrome
            unfinished = list(download_dir.glob("*.crdownload")) + list(download_dir.glob("*.tmp"))
            if unfinished:
                time.sleep(1)
                continue

            # Verifica se já existe um arquivo finalizado com tamanho > 0
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
    Realiza o download do relatório de RELEITURAS NÃO EXECUTADAS.

    Argumentos:
        portal_user: Usuário do portal (SGL).
        portal_pass: Senha do portal.
        download_dir: Pasta de destino (opcional).
        unidade_de: Filtro inicial de Unidade de Leitura.
        unidade_ate: Filtro final de Unidade de Leitura.
        timeout: Tempo limite de espera.

    Retorna:
        str: Caminho absoluto do arquivo baixado.

    Lança:
        RuntimeError: Se houver falha no processo de automação ou download.
    """

    # Importações preguiçosas (Selenium/PyAutoGUI) para evitar erros no backend
    # se essas libs não estiverem instaladas no ambiente de produção.
    try:
        import pyautogui  # type: ignore
        from selenium import webdriver  # type: ignore
        from selenium.webdriver.common.window import WindowTypes  # type: ignore
        from selenium.webdriver.common.by import By  # type: ignore
        from selenium.webdriver.common.keys import Keys  # type: ignore
        from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
        from selenium.webdriver.support import expected_conditions as EC  # type: ignore
        from selenium.webdriver.chrome.options import Options  # type: ignore
        from dotenv import load_dotenv  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Dependências do sincronizador não instaladas. Instale: selenium, pyautogui, python-dotenv. "
            f"Detalhe: {e}"
        )
    
    # Carregar variáveis de ambiente
    project_root = _find_project_root()
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))

    user = portal_user or os.getenv("PORTAL_USER")
    password = portal_pass or os.getenv("PORTAL_PASS")
    if not user or not password:
        raise RuntimeError(
            "Credenciais não encontradas. Configure PORTAL_USER e PORTAL_PASS no arquivo .env na raiz do projeto."
        )

    dl_dir = Path(download_dir) if download_dir else _default_download_dir()
    _clear_download_dir(dl_dir)

    unidade_de = unidade_de or UNIDADE_PADRAO_DE
    unidade_ate = unidade_ate or UNIDADE_PADRAO_ATE

    # Localizadores (XPaths e IDs) para automação do Selenium
    LOC_USER = (By.ID, "UserName")
    LOC_PASS = (By.ID, "Password")
    LOC_BTN_LOGIN = (By.XPATH, "//button[text()='Login']")
    LOC_MENU_RELATORIOS = (By.XPATH, "//ul[@id='side-menu']//li//span[text()='RELATÓRIOS']")
    # Tenta href primeiro, depois texto para maior robustez
    LOC_RELEITURA_BY_HREF = (By.XPATH, "//a[contains(@href,'/SGLEmpreiteira/Relatorios/RlReleituraNaoExecutada')]")
    LOC_RELEITURA_BY_TEXT = (By.XPATH, "//a[contains(.,'Releit') or contains(.,'RELEIT')]")
    LOC_MES_ANO = (By.ID, "txtMesAno")
    LOC_DATA_HOJE = (By.XPATH, "/html/body/div[3]/div[2]/table/tfoot/tr[1]/th")
    LOC_BTN_GERAR = (By.ID, "btnGerarExcel")

    def handle_certificate():
        """
        Tenta fechar automaticamente o popup de seleção de certificado do Windows/Chrome.
        Usa PyAutoGUI para simular 'Enter'.
        """
        time.sleep(5)
        try:
            pyautogui.press("enter")
            time.sleep(1)
            pyautogui.press("enter")
        except Exception:
            pass

    # Configuração do Chrome Driver
    chrome_options = Options()
    if os.getenv("PORTAL_DETACH", "0") == "1":
        chrome_options.add_experimental_option("detach", True)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_leak_detection": False,
        "profile.password_manager_enabled": False,
        "download.default_directory": str(dl_dir),
        "download.prompt_for_download": False,
        "directory_upgrade": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # Thread separada para lidar com certificado digital (se necessário)
    if os.getenv("PORTAL_HANDLE_CERT", "1") == "1":
        threading.Thread(target=handle_certificate, daemon=True).start()

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 30)

    try:
        driver.get(URL_PORTAL)
        switch_to_main_tab(driver)

        # Login
        wait.until(EC.element_to_be_clickable(LOC_USER)).send_keys(user)
        driver.find_element(*LOC_PASS).send_keys(password)
        wait.until(EC.element_to_be_clickable(LOC_BTN_LOGIN)).click()

        # Navegação
        wait.until(EC.element_to_be_clickable(LOC_MENU_RELATORIOS)).click()
        try:
            link = wait.until(EC.presence_of_element_located(LOC_RELEITURA_BY_HREF))
        except Exception:
            link = wait.until(EC.presence_of_element_located(LOC_RELEITURA_BY_TEXT))
        driver.execute_script("arguments[0].click();", link)

        # Preencher filtros (Mês/Ano = Hoje)
        wait.until(EC.element_to_be_clickable(LOC_MES_ANO)).click()
        wait.until(EC.element_to_be_clickable(LOC_DATA_HOJE)).click()

        # Gerar e Baixar
        wait.until(EC.element_to_be_clickable(LOC_BTN_GERAR)).click()

        if not _wait_download_finished(dl_dir, timeout=timeout):
            raise RuntimeError("Tempo limite de download excedido.")

        latest = _latest_file(dl_dir)
        if latest is None:
            raise RuntimeError("Download finalizado, mas nenhum arquivo foi encontrado.")

        if latest.suffix.lower() not in {".xls", ".xlsx"}:
            raise RuntimeError(f"Arquivo baixado não parece Excel: {latest.name}")

        return str(latest)

    finally:
        try:
            driver.quit()
        except Exception:
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
    Realiza o download do relatório de ACOMPANHAMENTO DE RESULTADOS DE LEITURA (Porteira).
    """

    try:
        import pyautogui  # type: ignore
        from selenium import webdriver  # type: ignore
        from selenium.webdriver.common.by import By  # type: ignore
        from selenium.webdriver.common.keys import Keys  # type: ignore
        from selenium.webdriver.common.window import WindowTypes  # type: ignore
        from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
        from selenium.webdriver.support import expected_conditions as EC  # type: ignore
        from selenium.webdriver.chrome.options import Options  # type: ignore
        from dotenv import load_dotenv  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Dependências do sincronizador não instaladas. Instale: selenium, pyautogui, python-dotenv. "
            f"Detalhe: {e}"
        )

    project_root = _find_project_root()
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))

    user = portal_user or os.getenv("PORTAL_USER")
    password = portal_pass or os.getenv("PORTAL_PASS")
    if not user or not password:
        raise RuntimeError(
            "Credenciais não encontradas. Configure PORTAL_USER e PORTAL_PASS no arquivo .env na raiz do projeto."
        )

    dl_dir = Path(download_dir) if download_dir else _default_download_dir()
    _clear_download_dir(dl_dir)

    unidade_de = unidade_de or UNIDADE_PADRAO_DE
    unidade_ate = unidade_ate or UNIDADE_PADRAO_ATE

    # Localizadores (específicos da página Porteira)
    LOC_USER = (By.ID, "UserName")
    LOC_PASS = (By.ID, "Password")
    LOC_BTN_LOGIN = (By.XPATH, "//button[text()='Login']")
    LOC_MENU_RELATORIOS = (By.XPATH, "//ul[@id='side-menu']//li//span[text()='RELATÓRIOS']")
    LOC_PORTEIRA_BY_HREF = (By.XPATH, "//a[contains(@href,'/SGLEmpreiteira/Relatorios/RlAcompanhamentoResultadoLeitura')]")
    LOC_PORTEIRA_BY_TEXT = (By.XPATH, "//a[contains(.,'Acompanh') or contains(.,'Resultado') or contains(.,'Leitura')]")
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
        except Exception:
            pass

    chrome_options = Options()
    if os.getenv("PORTAL_DETACH", "0") == "1":
        chrome_options.add_experimental_option("detach", True)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_leak_detection": False,
        "profile.password_manager_enabled": False,
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
        switch_to_main_tab(driver)

        # Login
        wait.until(EC.element_to_be_clickable(LOC_USER)).send_keys(user)
        driver.find_element(*LOC_PASS).send_keys(password)
        wait.until(EC.element_to_be_clickable(LOC_BTN_LOGIN)).click()

        # Navegação
        wait.until(EC.element_to_be_clickable(LOC_MENU_RELATORIOS)).click()
        try:
            link = wait.until(EC.presence_of_element_located(LOC_PORTEIRA_BY_HREF))
        except Exception:
            link = wait.until(EC.presence_of_element_located(LOC_PORTEIRA_BY_TEXT))
        driver.execute_script("arguments[0].click();", link)

        # Preenchimento de Data (Mês/Ano)
        mes_ano_el = wait.until(EC.element_to_be_clickable(LOC_MES_ANO))
        mes_ano_el.click()

        if report_date:
            try:
                # Converte formato YYYY-MM-DD ou DD/MM/YYYY para MM/YYYY do portal
                if "-" in report_date:
                    y, m, _d = report_date.split("-", 2)
                else:
                    _d, m, y = report_date.split("/", 2)
                mm_yyyy = f"{int(m):02d}/{int(y)}"

                try:
                    mes_ano_el.clear()
                except Exception:
                    pass
                mes_ano_el.send_keys(mm_yyyy)
            except Exception:
                # Fallback para "Hoje"
                wait.until(EC.element_to_be_clickable(LOC_DATA_HOJE)).click()
        else:
            # Padrão: "Hoje"
            wait.until(EC.element_to_be_clickable(LOC_DATA_HOJE)).click()

        # Filtro de Unidades (Range)
        ini = wait.until(EC.element_to_be_clickable(LOC_UNIDADE_INI))
        fim = driver.find_element(*LOC_UNIDADE_FIM)
        for el, val in ((ini, unidade_de), (fim, unidade_ate)):
            try:
                el.click()
                el.clear()
            except Exception:
                pass
            try:
                # Fallback: Selecionar tudo e apagar
                el.send_keys(Keys.CONTROL, 'a')
                el.send_keys(Keys.DELETE)
            except Exception:
                pass
            el.send_keys(val)

        # Download
        wait.until(EC.element_to_be_clickable(LOC_BTN_GERAR)).click()

        if not _wait_download_finished(dl_dir, timeout=timeout):
            raise RuntimeError("Tempo limite de download excedido.")

        latest = _latest_file(dl_dir)
        if latest is None:
            raise RuntimeError("Download finalizado, mas nenhum arquivo foi encontrado.")

        if latest.suffix.lower() not in {".xls", ".xlsx"}:
            raise RuntimeError(f"Arquivo baixado não parece Excel: {latest.name}")

        return str(latest)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    path = download_releitura_excel()
    print(path)
