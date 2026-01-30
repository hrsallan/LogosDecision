"""Portal scraper (CEMIG SGL) to download the Releituras Excel report.

This module is intentionally implemented with *lazy imports* so the Flask
backend can still start even if Selenium / PyAutoGUI are not installed.

Default download folder (inside the project):
    VigilaCore/data/exports/
"""

from __future__ import annotations

import os
import time
import threading
from pathlib import Path

# --- Defaults (can be overridden by env vars) ---
URL_PORTAL = os.getenv("PORTAL_URL", "https://sglempreiteira.cemig.com.br/SGLEmpreiteira")
UNIDADE_PADRAO_DE = os.getenv("PORTAL_UNIDADE_DE", "01000000")
UNIDADE_PADRAO_ATE = os.getenv("PORTAL_UNIDADE_ATE", "18999999")


def _find_project_root() -> Path:
    """Find VigilaCore root folder robustly.

    We walk upwards looking for 'frontend' and 'data' folders (or '.env').
    """
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "frontend").exists() and (parent / "backend").exists():
            return parent
        if (parent / ".env").exists() and (parent / "data").exists():
            return parent
    # Fallback to previous assumption: backend/core -> backend -> root
    return here.parents[2]


def _default_download_dir() -> Path:
    return _find_project_root() / "data" / "exports"


def _clear_download_dir(download_dir: Path) -> None:
    download_dir.mkdir(parents=True, exist_ok=True)
    for f in download_dir.iterdir():
        try:
            if f.is_file():
                f.unlink()
        except Exception:
            pass

def switch_to_main_tab(driver):
    driver.switch_to.window(driver.window_handles[0])

def _latest_file(download_dir: Path) -> Path | None:
    files = [p for p in download_dir.iterdir() if p.is_file()]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def _wait_download_finished(download_dir: Path, timeout: int = 120) -> bool:
    """Wait until at least one file exists and there are no unfinished downloads."""
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
    """Download the Releituras Excel report and return the downloaded file path.

    Raises RuntimeError with a clear message on failure.
    """

    # Lazy imports (so backend can start without these deps installed)
    try:
        import pyautogui  # type: ignore
        from selenium import webdriver  # type: ignore
        from selenium.webdriver.common.window import WindowTypes  # type: ignore
        from selenium.webdriver.common.by import By  # type: ignore
        from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
        from selenium.webdriver.support import expected_conditions as EC  # type: ignore
        from selenium.webdriver.chrome.options import Options  # type: ignore
        from dotenv import load_dotenv  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Dependências do sincronizador não instaladas. Instale: selenium, pyautogui, python-dotenv. "
            f"Detalhe: {e}"
        )
    
    # Load .env from project root
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

    # Locators
    LOC_USER = (By.ID, "UserName")
    LOC_PASS = (By.ID, "Password")
    LOC_BTN_LOGIN = (By.XPATH, "//button[text()='Login']")
    LOC_MENU_RELATORIOS = (By.XPATH, "//ul[@id='side-menu']//li//span[text()='RELATÓRIOS']")
    # Prefer href, but also try by link text if it changes
    LOC_RELEITURA_BY_HREF = (By.XPATH, "//a[contains(@href,'/SGLEmpreiteira/Relatorios/RlReleituraNaoExecutada')]")
    LOC_RELEITURA_BY_TEXT = (By.XPATH, "//a[contains(.,'Releit') or contains(.,'RELEIT')]")
    LOC_MES_ANO = (By.ID, "txtMesAno")
    LOC_DATA_HOJE = (By.XPATH, "//div[@class='datepicker-months']/table/tfoot/tr/th[contains(@class,'today')]")
    # LOC_UNIDADE_INI = (By.ID, "txtUnidadeLeituraIni")
    # LOC_UNIDADE_FIM = (By.ID, "txtUnidadeLeituraFim")
    LOC_BTN_GERAR = (By.ID, "btnGerarExcel")

    def handle_certificate():
        """Best-effort close Windows certificate pop-up."""
        time.sleep(5)
        try:
            pyautogui.press("enter")
            time.sleep(1)
            pyautogui.press("enter")
        except Exception:
            pass

    # Chrome prefs
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

        # Navigation
        wait.until(EC.element_to_be_clickable(LOC_MENU_RELATORIOS)).click()
        try:
            link = wait.until(EC.presence_of_element_located(LOC_RELEITURA_BY_HREF))
        except Exception:
            link = wait.until(EC.presence_of_element_located(LOC_RELEITURA_BY_TEXT))
        driver.execute_script("arguments[0].click();", link)

        # Fill month/year (today)
        wait.until(EC.element_to_be_clickable(LOC_MES_ANO)).click()
        wait.until(EC.element_to_be_clickable(LOC_DATA_HOJE)).click()

        # Download
        wait.until(EC.element_to_be_clickable(LOC_BTN_GERAR)).click()

        if not _wait_download_finished(dl_dir, timeout=timeout):
            raise RuntimeError("Tempo limite de download excedido.")

        latest = _latest_file(dl_dir)
        if latest is None:
            raise RuntimeError("Download finalizado, mas nenhum arquivo foi encontrado.")

        # Basic validation: avoid returning an HTML error page
        if latest.suffix.lower() not in {".xls", ".xlsx"}:
            # still return, but warn via exception for clarity
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
    """Download the 'Acompanhamento de Resultados de Leitura' Excel report (Porteira)."""

    # Lazy imports
    try:
        import pyautogui  # type: ignore
        from selenium import webdriver  # type: ignore
        from selenium.webdriver.common.by import By  # type: ignore
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

    # Locators (porteira)
    LOC_USER = (By.ID, "UserName")
    LOC_PASS = (By.ID, "Password")
    LOC_BTN_LOGIN = (By.XPATH, "//button[text()='Login']")
    LOC_MENU_RELATORIOS = (By.XPATH, "//ul[@id='side-menu']//li//span[text()='RELATÓRIOS']")
    LOC_PORTEIRA_BY_HREF = (By.XPATH, "//a[contains(@href,'/SGLEmpreiteira/Relatorios/RlAcompanhamentoResultadoLeitura')]")
    LOC_PORTEIRA_BY_TEXT = (By.XPATH, "//a[contains(.,'Acompanh') or contains(.,'Resultado') or contains(.,'Leitura')]")
    LOC_MES_ANO = (By.ID, "txtMesAno")
    LOC_DATA_HOJE = (By.XPATH, "//div[@class='datepicker-months']/table/tfoot/tr/th[contains(@class,'today')]")
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

        # Navigation
        wait.until(EC.element_to_be_clickable(LOC_MENU_RELATORIOS)).click()
        try:
            link = wait.until(EC.presence_of_element_located(LOC_PORTEIRA_BY_HREF))
        except Exception:
            link = wait.until(EC.presence_of_element_located(LOC_PORTEIRA_BY_TEXT))
        driver.execute_script("arguments[0].click();", link)

        # Fill month/year
        # O portal usa um campo de mês/ano; para manter compatibilidade com o UX do calendário no front,
        # aceitamos report_date (YYYY-MM-DD) e extraímos o MM/YYYY.
        mes_ano_el = wait.until(EC.element_to_be_clickable(LOC_MES_ANO))
        mes_ano_el.click()

        if report_date:
            try:
                # suporta YYYY-MM-DD ou DD/MM/YYYY
                if "-" in report_date:
                    y, m, _d = report_date.split("-", 2)
                else:
                    _d, m, y = report_date.split("/", 2)
                mm_yyyy = f"{int(m):02d}/{int(y)}"

                # limpar e digitar
                try:
                    mes_ano_el.clear()
                except Exception:
                    pass
                mes_ano_el.send_keys(mm_yyyy)
            except Exception:
                # fallback: clicar em "hoje"
                wait.until(EC.element_to_be_clickable(LOC_DATA_HOJE)).click()
        else:
            # padrão: hoje
            wait.until(EC.element_to_be_clickable(LOC_DATA_HOJE)).click()

        # Unidade range
        wait.until(EC.element_to_be_clickable(LOC_UNIDADE_INI)).send_keys(unidade_de)
        driver.find_element(*LOC_UNIDADE_FIM).send_keys(unidade_ate)

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