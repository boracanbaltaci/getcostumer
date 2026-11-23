"""Dahili bildirimler (satış ekibine e-posta / Telegram).

Bu modül işletmelere pazarlama iletisi GÖNDERMEZ; yalnızca ekip içi özet ve hatırlatma yollar.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import List

import httpx

from app.config import settings

log = logging.getLogger(__name__)


def send_email(subject: str, body: str, to: List[str]) -> bool:
    if not (settings.SMTP_HOST and settings.SMTP_FROM and to):
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = ", ".join(to)
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as s:
            if settings.SMTP_USE_TLS:
                s.starttls()
            if settings.SMTP_USER:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
            s.send_message(msg)
        return True
    except Exception as exc:
        log.warning("E-posta gönderilemedi: %s", exc)
        return False


def send_telegram(text: str) -> bool:
    if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID):
        return False
    try:
        r = httpx.post(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                       json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text[:4000]}, timeout=20)
        return r.status_code == 200
    except Exception as exc:
        log.warning("Telegram bildirimi gönderilemedi: %s", exc)
        return False


def notify_team(subject: str, body: str) -> dict:
    return {"email": send_email(subject, body, settings.notify_emails), "telegram": send_telegram(f"{subject}\n\n{body}")}
