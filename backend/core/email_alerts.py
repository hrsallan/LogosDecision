"""core.email_alerts

Envio de alertas por e-mail quando o web-scraping (Portal SGL) falha.

Configuração via .env / variáveis de ambiente:

    ALERT_EMAIL_ENABLED=1
    ALERT_EMAIL_TO=seuemail@dominio.com

    ALERT_SMTP_HOST=smtp.gmail.com
    ALERT_SMTP_PORT=587
    ALERT_SMTP_USER=seuemail@gmail.com
    ALERT_SMTP_PASS=senha_de_app

Opcional:
    ALERT_EMAIL_SUBJECT_PREFIX=[LOGOS DECISION]
    ALERT_EMAIL_COOLDOWN_MIN=30
    ALERT_EMAIL_TO_CC=email2@dominio.com,email3@dominio.com

Observação:
    - Para Gmail/Workspace use *Senha de app* (App Password).
    - Se variáveis não estiverem configuradas, o módulo apenas loga e não envia.
"""

from __future__ import annotations

import json
import os
import smtplib
import socket
import time
import traceback
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

# --- dotenv / .env loading -------------------------------------------------
_ENV_LOADED = False
_ENV_SOURCE: str | None = None

def _ensure_env_loaded() -> None:
    """Garante que o arquivo .env da raiz do projeto foi carregado em os.environ.

    Muitos ambientes (especialmente quando o backend é iniciado por IDE/atalho)
    não carregam automaticamente o .env. Este helper garante consistência.
    """
    global _ENV_LOADED, _ENV_SOURCE
    if _ENV_LOADED:
        return
    try:
        from dotenv import dotenv_values  # type: ignore
    except Exception:
        _ENV_LOADED = True
        _ENV_SOURCE = "python-dotenv-indisponível"
        return

    root = _find_project_root()
    env_path = root / ".env"
    if env_path.exists():
        try:
            values = dotenv_values(env_path)
            for k, v in values.items():
                if v is None:
                    continue
                # Override SEMPRE: .env deve prevalecer para esta aplicação
                os.environ[str(k)] = str(v)
            _ENV_SOURCE = str(env_path)
        except Exception as e:
            _ENV_SOURCE = f"{env_path} (falha ao ler: {e})"
    else:
        _ENV_SOURCE = f"{env_path} (não encontrado)"
    _ENV_LOADED = True

def _env_debug_flags() -> dict:
    _ensure_env_loaded()
    user = (os.getenv("ALERT_SMTP_USER") or "").strip().strip('"').strip("\'")
    password = (os.getenv("ALERT_SMTP_PASS") or "").strip().replace(" ", "").strip('"').strip("\'")
    to_ = (os.getenv("ALERT_EMAIL_TO") or "").strip()
    return {
        "env_source": _ENV_SOURCE,
        "smtp_user_set": bool(user),
        "smtp_pass_set": bool(password),
        "to_set": bool(to_),
    }


def _find_project_root() -> Path:
    """Localiza a raiz do projeto (pasta que contém 'backend' e 'frontend')."""
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "frontend").exists() and (parent / "backend").exists():
            return parent
        if (parent / ".env").exists() and (parent / "data").exists():
            return parent
    # fallback seguro
    return here.parents[2]


def _state_file() -> Path:
    root = _find_project_root()
    (root / "data").mkdir(parents=True, exist_ok=True)
    return root / "data" / "email_alert_state.json"


def _load_state() -> dict:
    fp = _state_file()
    if not fp.exists():
        return {}
    try:
        return json.loads(fp.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    fp = _state_file()
    try:
        fp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # nunca interrompa a aplicação por causa de persistência de estado
        pass


def _split_emails(value: str | None) -> list[str]:
    if not value:
        return []
    items: list[str] = []
    for part in value.replace(";", ",").split(","):
        p = part.strip()
        if p:
            items.append(p)
    return items


@dataclass
class EmailConfig:
    enabled: bool
    host: str
    port: int
    user: str
    password: str
    to_list: list[str]
    cc_list: list[str]
    subject_prefix: str
    cooldown_min: int


def _get_config() -> EmailConfig:
    _ensure_env_loaded()
    enabled = os.getenv("ALERT_EMAIL_ENABLED", "0").strip() == "1"
    host = os.getenv("ALERT_SMTP_HOST", "smtp.gmail.com").strip() or "smtp.gmail.com"
    port = int(os.getenv("ALERT_SMTP_PORT", "587") or "587")
    user = (os.getenv("ALERT_SMTP_USER") or "").strip().strip('"').strip("\'")
    password = (os.getenv("ALERT_SMTP_PASS") or "").strip().replace(" ", "").strip('"').strip("\'")
    to_list = _split_emails(os.getenv("ALERT_EMAIL_TO"))
    cc_list = _split_emails(os.getenv("ALERT_EMAIL_TO_CC"))
    subject_prefix = (os.getenv("ALERT_EMAIL_SUBJECT_PREFIX") or "[LOGOS DECISION]").strip()
    cooldown_min = int(os.getenv("ALERT_EMAIL_COOLDOWN_MIN", "30") or "30")
    return EmailConfig(
        enabled=enabled,
        host=host,
        port=port,
        user=user,
        password=password,
        to_list=to_list,
        cc_list=cc_list,
        subject_prefix=subject_prefix,
        cooldown_min=cooldown_min,
    )


def _can_send(key: str, cooldown_min: int) -> bool:
    """Evita spam: no máximo 1 e-mail por `key` a cada cooldown."""
    state = _load_state()
    now = int(time.time())
    last = int(state.get(key, 0) or 0)
    if now - last < cooldown_min * 60:
        return False
    state[key] = now
    _save_state(state)
    return True


def send_email(subject: str, body: str, *, to_addrs: Iterable[str], cc_addrs: Iterable[str] = ()) -> bool:
    """Envia e-mail via SMTP/TLS. Retorna True se enviou, False caso contrário."""
    cfg = _get_config()
    if not cfg.enabled:
        print("ℹ️ [email] ALERT_EMAIL_ENABLED=0 (não enviando e-mail)")
        return False

    if not cfg.user or not cfg.password:
        print("⚠️ [email] SMTP não configurado (ALERT_SMTP_USER/ALERT_SMTP_PASS ausentes)")
        return False

    to_list = list(to_addrs)
    cc_list = list(cc_addrs)
    if not to_list:
        print("⚠️ [email] ALERT_EMAIL_TO vazio (sem destinatário)")
        return False

    msg = EmailMessage()
    msg["From"] = cfg.user
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(cfg.host, cfg.port, timeout=25) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(cfg.user, cfg.password)
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, socket.timeout, OSError) as e:
        print(f"❌ [email] Falha ao enviar e-mail: {e}")
        return False


def notify_scraper_error(*, where: str, err: Exception, extra: dict | None = None, traceback_text: str | None = None) -> bool:
    """Dispara e-mail de alerta quando o scraping falhar (com cooldown)."""
    cfg = _get_config()
    if not cfg.enabled:
        # Não persiste estado (para não bloquear quando o usuário habilitar depois)
        return False
    # Mesmo se desabilitado, não quebra fluxo.
    key = f"scraper:{where}".lower().replace(" ", "_")
    if not _can_send(key, cfg.cooldown_min):
        print(f"⏳ [email] Cooldown ativo para '{where}'.")
        return False

    tb = traceback_text or traceback.format_exc()
    extra = extra or {}
    
    # Formatação minimalista e profissional
    timestamp = time.strftime('%d/%m/%Y às %H:%M:%S')
    error_type = type(err).__name__
    error_msg = str(err)
    
    # Detalhes extras formatados
    extra_section = ""
    if extra:
        extra_items = "\n".join([f"  • {k}: {v}" for k, v in extra.items()])
        extra_section = f"\n\n📋 CONTEXTO\n{extra_items}"
    
    subject = f"{cfg.subject_prefix} Alerta de Falha • {where}"
    
    body = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOGOS DECISION • Sistema de Monitoramento
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 ALERTA DE FALHA NO WEB SCRAPING

📍 LOCAL
  {where}

⏰ DATA/HORA
  {timestamp}

❌ ERRO
  {error_type}: {error_msg}{extra_section}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 DIAGNÓSTICO TÉCNICO

{tb}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Este é um alerta automático do LOGOS DECISION.
Sistema de Gestão de Releitura e Porteira • CEMIG
"""

    to_list = cfg.to_list
    cc_list = cfg.cc_list
    return send_email(subject, body, to_addrs=to_list, cc_addrs=cc_list)


def send_test_email(*, requested_by: str | None = None, to_override: str | None = None, force: bool = True) -> tuple[bool, str]:
    """Envia um e-mail de teste (para validar SMTP), sem depender de provocar falhas no scraping.

    - `force=True` ignora ALERT_EMAIL_ENABLED (útil para teste).
    - `to_override` permite informar destinatário pontual; caso vazio usa ALERT_EMAIL_TO.
    Retorna (ok, message).
    """
    cfg = _get_config()
    if (not force) and (not cfg.enabled):
        return False, "ALERT_EMAIL_ENABLED=0 (alertas desabilitados)."

    host = cfg.host
    port = cfg.port
    user = (cfg.user or "").strip()
    password = (cfg.password or "").strip()

    to_list = _split_emails(to_override) if to_override else list(cfg.to_list)
    cc_list = list(cfg.cc_list)

    if not user or not password:
        dbg = _env_debug_flags()
        return False, f"SMTP não configurado (ALERT_SMTP_USER/ALERT_SMTP_PASS ausentes). Env: {dbg.get('env_source')} (smtp_user_set={dbg.get('smtp_user_set')}, smtp_pass_set={dbg.get('smtp_pass_set')}, to_set={dbg.get('to_set')})"
    if not to_list:
        return False, "Destinatário vazio (ALERT_EMAIL_TO ausente ou 'to' não informado)."

    timestamp = time.strftime('%d/%m/%Y às %H:%M:%S')
    subject = f"{cfg.subject_prefix} Teste de Configuração SMTP"
    
    body = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOGOS DECISION • Sistema de Monitoramento
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ TESTE DE CONFIGURAÇÃO SMTP

Este é um email de teste para validar a configuração
do sistema de alertas do LOGOS DECISION.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 INFORMAÇÕES DA CONFIGURAÇÃO

⏰ Data/Hora
  {timestamp}

📧 Servidor SMTP
  {host}:{port}

👤 Remetente
  {user}

🔑 Solicitado por
  {requested_by or 'Sistema'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Configuração SMTP validada com sucesso!

Se você recebeu este email, o sistema de alertas
está funcionando corretamente.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LOGOS DECISION v1.0
Sistema de Gestão de Releitura e Porteira • CEMIG
"""

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=25) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)
        return True, "E-mail de teste enviado com sucesso."
    except (smtplib.SMTPException, socket.timeout, OSError) as e:
        return False, f"Falha ao enviar e-mail de teste: {e}"