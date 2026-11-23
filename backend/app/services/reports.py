"""Gösterge paneli metrikleri, günlük özet ve satış raporları."""
from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import HIGH_SCORE_THRESHOLD, STAGE_KEYS, STAGE_LABELS
from app.models import (
    Business, ContactPoint, DailyReport, DataSource, JobRun, Opportunity, Quote, RawRecord,
)
from app.services.coverage import coverage_calendar

TZ = ZoneInfo(settings.TIMEZONE)


def today_tr() -> dt.date:
    return dt.datetime.now(TZ).date()


def _day_bounds(d: dt.date):
    start = dt.datetime.combine(d, dt.time.min, tzinfo=TZ)
    return start, start + dt.timedelta(days=1)


def ref_date_col():
    return func.coalesce(Business.establishment_date, Business.gazette_date)


def has_contact_clause():
    return exists().where(and_(ContactPoint.business_id == Business.id, ContactPoint.status != "reddedildi",
                               ContactPoint.type.in_(["phone", "email"])))


def dashboard(db: Session) -> Dict:
    today = today_tr()
    active = Business.is_active.is_(True)
    s, e = _day_bounds(today)
    cnt = lambda *conds: db.scalar(select(func.count(Business.id)).where(active, *conds)) or 0  # noqa: E731
    opp_cnt = lambda stage: db.scalar(  # noqa: E731
        select(func.count(func.distinct(Opportunity.business_id))).join(Business).where(active, Opportunity.stage == stage)) or 0
    metrics = {
        "today_detected": cnt(Business.first_seen_at >= s, Business.first_seen_at < e),
        "last7_established": cnt(ref_date_col() >= today - dt.timedelta(days=6)),
        "last30_established": cnt(ref_date_col() >= today - dt.timedelta(days=29)),
        "with_contact": cnt(has_contact_clause()),
        "high_isg": cnt(Business.isg_score >= HIGH_SCORE_THRESHOLD),
        "high_software": cnt(Business.software_score >= HIGH_SCORE_THRESHOLD),
        "not_contacted": cnt(Business.sales_status.in_(["yeni", "arastiriliyor", "iletisime_hazir"])),
        "quoted": opp_cnt("teklif_gonderildi"),
        "won": opp_cnt("kazanildi"),
        "total_active": cnt(),
        "needs_review": db.scalar(select(func.count(RawRecord.id)).where(RawRecord.status == "needs_review")) or 0,
    }
    calendar = coverage_calendar(db, today - dt.timedelta(days=13), today)
    sources = [{"key": x.key, "name": x.name, "health": x.health, "enabled": x.enabled, "kind": x.kind,
                "last_success_at": x.last_success_at, "last_error": x.last_error}
               for x in db.scalars(select(DataSource).where(DataSource.kind != "reference")).all()]
    last_job = db.scalar(select(JobRun).where(JobRun.job_type == "daily_pipeline").order_by(JobRun.started_at.desc()))
    stage_funnel = []
    for line in ("isg", "yazilim"):
        rows = dict(db.execute(select(Opportunity.stage, func.count()).join(Business)
                               .where(active, Opportunity.service_line == line).group_by(Opportunity.stage)).all())
        stage_funnel.append({"service_line": line, "stages": [{"stage": k, "label": STAGE_LABELS[k], "count": rows.get(k, 0)}
                                                              for k in STAGE_KEYS]})
    top = db.scalars(select(Business).where(active, Business.sales_status.in_(["yeni", "arastiriliyor", "iletisime_hazir"]))
                     .order_by(Business.total_score.desc().nulls_last(), Business.first_seen_at.desc()).limit(8)).all()
    return {
        "metrics": metrics, "coverage": calendar, "sources": sources,
        "last_job": {"id": last_job.id, "status": last_job.status, "started_at": last_job.started_at,
                     "finished_at": last_job.finished_at, "stats": last_job.stats, "error": last_job.error} if last_job else None,
        "funnel": stage_funnel,
        "top_leads": [{"id": b.id, "trade_name": b.trade_name, "district": b.district, "isg_score": b.isg_score,
                       "software_score": b.software_score, "total_score": b.total_score, "priority": b.priority,
                       "establishment_date": b.establishment_date or b.gazette_date} for b in top],
    }


def build_daily_report(db: Session, day: dt.date, job: Optional[JobRun]) -> DailyReport:
    s, e = _day_bounds(day)
    new = db.scalars(select(Business).where(Business.first_seen_at >= s, Business.first_seen_at < e, Business.is_active.is_(True))
                     .order_by(Business.total_score.desc().nulls_last())).all()
    cal = coverage_calendar(db, day - dt.timedelta(days=6), day)
    automated = db.scalars(select(DataSource).where(DataSource.automated.is_(True))).all()
    warnings: List[str] = []
    active_auto = [x for x in automated if x.enabled and x.health == "ok"]
    if not active_auto:
        warnings.append("Çalışan otomatik veri kaynağı yok. Yeni kuruluşlar yalnızca manuel içe aktarma veya gelen "
                        "kutusu klasörü ile tespit edilebilir; bugün için 'tarama yapılmadı' kabul edin.")
    for x in automated:
        if x.enabled and x.health == "error":
            warnings.append(f"{x.name}: erişim hatası – {x.last_error or ''}"[:300])
    if cal and cal[-1]["status"] != "covered":
        warnings.append(f"{day.strftime('%d.%m.%Y')} için hiçbir yetkili kaynaktan tarama yapılamadı; yeni kuruluş "
                        "sayısı bilinmiyor (sıfır kabul edilmemeli).")
    not_scanned = [c["date"] for c in cal if c["status"] in ("not_scanned", "failed") and not c["weekend"]]
    if not_scanned:
        warnings.append("Taranamayan iş günleri (sıfır kuruluş anlamına GELMEZ): " + ", ".join(not_scanned))
    content = {
        "date": day.isoformat(),
        "new_businesses": len(new),
        "with_contact": sum(1 for b in new if any(c.type in ("phone", "email") and c.status != "reddedildi" for c in b.contacts)),
        "high_isg": sum(1 for b in new if (b.isg_score or 0) >= HIGH_SCORE_THRESHOLD),
        "high_software": sum(1 for b in new if (b.software_score or 0) >= HIGH_SCORE_THRESHOLD),
        "top": [{"id": b.id, "trade_name": b.trade_name, "district": b.district, "isg": b.isg_score,
                 "software": b.software_score, "priority": b.priority} for b in new[:20]],
        "coverage": cal,
        "warnings": warnings,
        "job": {"id": job.id, "status": job.status, "stats": job.stats} if job else None,
    }
    rep = db.scalar(select(DailyReport).where(DailyReport.report_date == day))
    if rep is None:
        rep = DailyReport(report_date=day)
        db.add(rep)
    rep.content = content
    rep.job_run_id = job.id if job else rep.job_run_id
    db.flush()
    return rep


def report_text(content: Dict) -> str:
    lines = [f"Ankara Business Radar – Günlük Özet ({content['date']})", "",
             f"Yeni tespit edilen işletme: {content['new_businesses']}",
             f"İletişim bilgisi bulunan: {content['with_contact']}",
             f"Yüksek İSG potansiyeli: {content['high_isg']}",
             f"Yüksek yazılım potansiyeli: {content['high_software']}", ""]
    if content.get("warnings"):
        lines.append("UYARILAR:")
        lines += [f"- {w}" for w in content["warnings"]]
        lines.append("")
    if content.get("top"):
        lines.append("Öncelikli işletmeler:")
        for t in content["top"][:10]:
            lines.append(f"- [{t.get('priority') or '-'}] {t['trade_name']} ({t.get('district') or 'ilçe ?'}) "
                         f"İSG {t.get('isg') if t.get('isg') is not None else '-'} / Yazılım {t.get('software') if t.get('software') is not None else '-'}")
    return "\n".join(lines)


def sales_report(db: Session, start: dt.date, end: dt.date) -> Dict:
    s = dt.datetime.combine(start, dt.time.min, tzinfo=TZ)
    e = dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min, tzinfo=TZ)
    detected = db.scalar(select(func.count(Business.id)).where(Business.first_seen_at >= s, Business.first_seen_at < e)) or 0
    won = db.execute(select(Opportunity.service_line, func.count(), func.coalesce(func.sum(Opportunity.estimated_value), 0))
                     .where(Opportunity.won_at >= s, Opportunity.won_at < e).group_by(Opportunity.service_line)).all()
    quotes = db.execute(select(Quote.status, func.count(), func.coalesce(func.sum(Quote.total), 0))
                        .where(Quote.created_at >= s, Quote.created_at < e).group_by(Quote.status)).all()
    by_stage = db.execute(select(Opportunity.service_line, Opportunity.stage, func.count())
                          .join(Business).where(Business.is_active.is_(True))
                          .group_by(Opportunity.service_line, Opportunity.stage)).all()
    by_district = db.execute(select(Business.district, func.count()).where(Business.first_seen_at >= s, Business.first_seen_at < e)
                             .group_by(Business.district).order_by(func.count().desc())).all()
    by_sector = db.execute(select(Business.sector, func.count()).where(Business.first_seen_at >= s, Business.first_seen_at < e)
                           .group_by(Business.sector).order_by(func.count().desc())).all()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "detected": detected,
        "won": [{"service_line": l, "count": c, "value": float(v)} for l, c, v in won],
        "quotes": [{"status": st, "count": c, "total": float(v)} for st, c, v in quotes],
        "pipeline": [{"service_line": l, "stage": st, "label": STAGE_LABELS.get(st, st), "count": c} for l, st, c in by_stage],
        "by_district": [{"district": d or "Belirsiz", "count": c} for d, c in by_district],
        "by_sector": [{"sector": sct or "analiz edilmedi", "count": c} for sct, c in by_sector],
    }
