"""SMTP ile gerçek e-posta gönderimi.

Tek bağlantı açılır ve alıcılara sırayla gönderilir; bir alıcının hatası
diğerlerini durdurmaz (alıcı bazlı `failed` listesi döner). Bağlantı ve
giriş hataları çağırana yayılır — uç katmanı 502'ye çevirir.
`{firma_adi}` yer tutucusu konu ve metinde alıcı adıyla değiştirilir.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Dict, List

from app.config import settings

logger = logging.getLogger(__name__)


def _personalize(text: str, name: str) -> str:
    return text.replace("{firma_adi}", name) if name else text


def _connect() -> smtplib.SMTP:
    if settings.SMTP_PORT == 465:
        return smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT,
                                timeout=settings.SMTP_TIMEOUT)
    conn = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT,
                        timeout=settings.SMTP_TIMEOUT)
    if settings.SMTP_TLS:
        conn.starttls()
    return conn


def send_bulk(recipients: List[Dict[str, str]], subject: str,
              body: str) -> Dict[str, object]:
    """recipients: [{"to", "name"}]; dönüş {"sent": int, "failed": [...]}."""
    conn = _connect()
    sent: int = 0
    failed: List[Dict[str, str]] = []
    try:
        if settings.SMTP_USERNAME:
            conn.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        for r in recipients:
            msg = EmailMessage()
            msg["From"] = settings.smtp_from
            msg["To"] = r["to"]
            msg["Subject"] = _personalize(subject, r.get("name", ""))
            msg.set_content(_personalize(body, r.get("name", "")))
            try:
                conn.send_message(msg)
                sent += 1
            except smtplib.SMTPException as exc:
                logger.warning("E-posta gönderilemedi %s: %s", r["to"], exc)
                failed.append({"to": r["to"],
                               "error": str(exc) or exc.__class__.__name__})
    finally:
        try:
            conn.quit()
        except smtplib.SMTPException:
            pass
    return {"sent": sent, "failed": failed}
