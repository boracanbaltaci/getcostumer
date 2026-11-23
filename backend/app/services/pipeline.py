"""Günlük otomasyon akışı (Türkiye saatiyle 08:30).

Adımlar: yetkili kaynakları kontrol et → yeni Ankara kuruluşlarını içe al → mükerrerleri ayıkla →
iletişim bilgisi araştır → fırsat analizi → günlük özet → (isteğe bağlı) ekip bildirimi.

Tekrar çalıştırılabilir (idempotent): ham kayıtlar içerik özetiyle tekilleştirilir, işletmeler
kesin anahtarlarla eşleştirilir, kapsam tablosu gün bazında güncellenir. Aynı anda iki akış
çalışmasın diye kilit kullanılır.
"""
from __future__ import annotations

import datetime as dt
import logging
import traceback
from typing import Dict, List, Optional

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Business, DataSource, JobRun, utcnow
from app.services import notifications
from app.services.enrichment.orchestrator import enrich_business
from app.services.reports import build_daily_report, report_text, today_tr
from app.services.scoring.engine import analyze_business
from app.services.sources.registry import ADAPTERS, last_covered_date, seed_sources

log = logging.getLogger(__name__)
LOCK_ID = 842_115_001
STALE_AFTER = dt.timedelta(hours=3)


class JobLogger:
    def __init__(self, db: Session, job: JobRun):
        self.db = db
        self.job = job
        self.lines: List[str] = []

    def __call__(self, msg: str) -> None:
        log.info(msg)
        self.lines.append(f"{dt.datetime.now().strftime('%H:%M:%S')} {msg}")
        self.job.log = list(self.lines[-500:])


def _acquire_lock(db: Session) -> bool:
    if db.bind.dialect.name == "postgresql":
        return bool(db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_ID}).scalar())
    return True


def _release_lock(db: Session) -> None:
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_ID})


def start_job(db: Session, job_type: str, triggered_by: str, run_key: Optional[str] = None) -> Optional[JobRun]:
    running = db.scalar(select(JobRun).where(JobRun.job_type == job_type, JobRun.status == "running"))
    if running:
        started = running.started_at if running.started_at.tzinfo else running.started_at.replace(tzinfo=dt.timezone.utc)
        if utcnow() - started < STALE_AFTER:
            return None
        running.status = "failed"
        running.error = "Zaman aşımı: görev yarım kalmış olarak işaretlendi"
        running.finished_at = utcnow()
    job = JobRun(job_type=job_type, triggered_by=triggered_by, run_key=run_key, status="running", stats={}, log=[])
    db.add(job)
    db.commit()
    return job


def run_enrichment(db: Session, limit: int = 100, say=None) -> Dict[str, int]:
    stats = {"enriched": 0, "found": 0, "not_found": 0, "errors": 0}
    q = (select(Business).where(Business.is_active.is_(True), Business.enrichment_status == "bekliyor")
         .order_by(Business.first_seen_at.desc()).limit(limit))
    for b in db.scalars(q).all():
        try:
            enrich_business(db, b)
            stats["enriched"] += 1
            stats["found" if b.enrichment_status == "tamamlandi" else "not_found"] += 1
            db.commit()
        except Exception as exc:
            db.rollback()
            stats["errors"] += 1
            b.enrichment_status = "hata"
            b.enrichment_log = [f"Hata: {exc}"]
            db.commit()
            if say:
                say(f"İletişim araştırması hatası ({b.trade_name}): {exc}")
    return stats


def run_scoring(db: Session, limit: int = 1000, use_llm: bool = True) -> Dict[str, int]:
    stats = {"analyzed": 0, "errors": 0}
    q = (select(Business).where(Business.is_active.is_(True),
                                or_(Business.analyzed_at.is_(None), Business.analyzed_at < Business.enriched_at))
         .limit(limit))
    for b in db.scalars(q).all():
        try:
            analyze_business(db, b, use_llm=use_llm)
            stats["analyzed"] += 1
            db.commit()
        except Exception:
            db.rollback()
            stats["errors"] += 1
            log.exception("Analiz hatası: %s", b.id)
    return stats


def run_daily_pipeline(db: Session, triggered_by: str = "schedule", notify: bool = True) -> Optional[JobRun]:
    today = today_tr()
    job = start_job(db, "daily_pipeline", triggered_by, run_key=today.isoformat())
    if job is None:
        return None
    if not _acquire_lock(db):
        job.status = "skipped"
        job.error = "Başka bir günlük akış çalışıyor"
        job.finished_at = utcnow()
        db.commit()
        return job
    say = JobLogger(db, job)
    stats: Dict = {"sources": {}, "created": 0}
    any_source_ok = False
    any_source_failed = False
    any_day_covered = False
    try:
        seed_sources(db)
        db.commit()
        for key, adapter in ADAPTERS.items():
            source = db.scalar(select(DataSource).where(DataSource.key == key))
            if source is None:
                continue
            if not source.enabled:
                stats["sources"][key] = {"status": "disabled"}
                say(f"{source.name}: devre dışı")
                continue
            ok, msg = adapter.is_configured()
            source.last_checked_at = utcnow()
            if not ok:
                source.health = "not_configured"
                source.last_error = msg
                stats["sources"][key] = {"status": "not_configured", "message": msg}
                say(f"{source.name}: yapılandırılmadı – {msg}")
                db.commit()
                continue
            last = last_covered_date(db, source)
            start = (last + dt.timedelta(days=1)) if last else today - dt.timedelta(days=settings.INITIAL_BACKFILL_DAYS)
            start = max(start, today - dt.timedelta(days=settings.INITIAL_BACKFILL_DAYS))
            say(f"{source.name}: {start} – {today} aralığı kontrol ediliyor")
            try:
                res = adapter.run(db, source, start, today, job.id)
                failed_days = [d for d, s in res.days.items() if s == "failed"]
                any_day_covered = any_day_covered or any(s == "covered" for s in res.days.values())
                source.health = "error" if (res.errors and not res.days) or failed_days else "ok"
                source.last_error = "; ".join(res.errors)[:2000] if res.errors else None
                if source.health == "ok":
                    source.last_success_at = utcnow()
                    any_source_ok = True
                else:
                    any_source_failed = True
                stats["sources"][key] = {"status": source.health, "created": res.created, "stats": res.stats,
                                         "failed_days": failed_days, "errors": res.errors[:20]}
                stats["created"] += res.created
                for line in res.log[-50:]:
                    say(f"  {line}")
                for err in res.errors[:20]:
                    say(f"  HATA: {err}")
                db.commit()
            except Exception as exc:
                db.rollback()
                source = db.scalar(select(DataSource).where(DataSource.key == key))
                source.health = "error"
                source.last_error = str(exc)[:2000]
                any_source_failed = True
                stats["sources"][key] = {"status": "error", "error": str(exc)[:500]}
                say(f"{source.name}: HATA – {exc}")
                db.commit()

        say("İletişim bilgisi araştırması başlıyor")
        stats["enrichment"] = run_enrichment(db, say=say)
        say(f"İletişim araştırması: {stats['enrichment']}")
        stats["scoring"] = run_scoring(db)
        say(f"Fırsat analizi: {stats['scoring']}")

        if any_source_failed:
            job.status = "partial" if any_source_ok else "failed"
        elif not any_source_ok or not any_day_covered:
            job.status = "partial"
            say("UYARI: Hiçbir otomatik kaynaktan yayın günü taranamadı; bugünkü tarama yapılmamış sayılır")
        else:
            job.status = "success"
        job.stats = stats
        rep = build_daily_report(db, today, job)
        db.commit()
        if notify:
            sent = notifications.notify_team(f"Günlük özet – {today.strftime('%d.%m.%Y')}", report_text(rep.content))
            if any(sent.values()):
                rep.sent_at = utcnow()
            stats["notifications"] = sent
    except Exception as exc:
        db.rollback()
        job = db.get(JobRun, job.id)
        job.status = "failed"
        job.error = f"{exc}\n{traceback.format_exc()[-3000:]}"
        say(f"Akış hatası: {exc}")
    finally:
        job.stats = stats
        job.finished_at = utcnow()
        db.commit()
        try:
            _release_lock(db)
            db.commit()
        except Exception:
            db.rollback()
    return job
