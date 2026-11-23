from __future__ import annotations

import datetime as dt
import logging

from app.database import SessionLocal
from app.worker.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="app.worker.tasks.daily_pipeline")
def daily_pipeline(triggered_by: str = "schedule") -> dict:
    from app.services.pipeline import run_daily_pipeline
    with SessionLocal() as db:
        job = run_daily_pipeline(db, triggered_by=triggered_by)
        return {"job_id": job.id if job else None, "status": job.status if job else "already_running"}


@celery_app.task(name="app.worker.tasks.enrich_and_score")
def enrich_and_score(triggered_by: str = "user") -> dict:
    from app.services.pipeline import run_enrichment, run_scoring, start_job
    from app.models import utcnow
    with SessionLocal() as db:
        job = start_job(db, "enrich_and_score", triggered_by)
        if job is None:
            return {"status": "already_running"}
        try:
            stats = {"enrichment": run_enrichment(db), "scoring": run_scoring(db)}
            job.status, job.stats = "success", stats
        except Exception as exc:
            db.rollback()
            job.status, job.error = "failed", str(exc)
        job.finished_at = utcnow()
        db.commit()
        return {"job_id": job.id, "status": job.status}


@celery_app.task(name="app.worker.tasks.score")
def score(triggered_by: str = "user") -> dict:
    from app.services.pipeline import run_scoring
    with SessionLocal() as db:
        return run_scoring(db)


@celery_app.task(name="app.worker.tasks.inbox_check")
def inbox_check(triggered_by: str = "schedule") -> dict:
    """Yalnızca gelen kutusu klasörünü işler (tam günlük akışı beklemeden)."""
    from sqlalchemy import select
    from app.models import DataSource, utcnow
    from app.services.pipeline import run_enrichment, run_scoring, start_job
    from app.services.reports import today_tr
    from app.services.sources.registry import ADAPTERS
    adapter = ADAPTERS["ttsg_inbox"]
    if not adapter.pending_files():
        return {"status": "empty"}
    with SessionLocal() as db:
        src = db.scalar(select(DataSource).where(DataSource.key == "ttsg_inbox"))
        if not src or not src.enabled:
            return {"status": "disabled"}
        job = start_job(db, "inbox_check", triggered_by)
        if job is None:
            return {"status": "already_running"}
        try:
            res = adapter.run(db, src, today_tr(), today_tr(), job.id)
            src.health, src.last_success_at = ("ok", utcnow()) if not res.errors else ("error", src.last_success_at)
            src.last_error = "; ".join(res.errors)[:2000] if res.errors else None
            db.commit()
            job.stats = {"inbox": res.stats, "created": res.created, "enrichment": run_enrichment(db),
                         "scoring": run_scoring(db)}
            job.log = res.log + res.errors
            job.status = "success" if not res.errors else "partial"
        except Exception as exc:
            db.rollback()
            job.status, job.error = "failed", str(exc)
        job.finished_at = utcnow()
        db.commit()
        return {"job_id": job.id, "status": job.status}


@celery_app.task(name="app.worker.tasks.reminder_digest")
def reminder_digest(triggered_by: str = "schedule") -> dict:
    from app.services import crm, notifications
    from app.services.reports import today_tr
    with SessionLocal() as db:
        items = crm.due_reminders(db, today_tr())
    if not items:
        return {"count": 0}
    body = "\n".join(f"- {'GECİKMİŞ ' if i['overdue'] else ''}{i['date']} · {i['business']}: {i['text']}" for i in items[:50])
    sent = notifications.notify_team(f"Bugünkü takipler ({len(items)})", body)
    return {"count": len(items), "sent": sent}


@celery_app.task(name="app.worker.tasks.retention")
def retention(triggered_by: str = "schedule") -> dict:
    from app.services.retention import apply_retention
    with SessionLocal() as db:
        res = apply_retention(db, dry_run=False)
        db.commit()
        return res
