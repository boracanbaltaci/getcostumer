"""Kaynak tarama kapsamı: hangi yayın günü hangi kaynaktan taranabildi?"""
from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataSource, SourceCoverage, utcnow


def mark_coverage(db: Session, source: DataSource, day: dt.date, status: str, *, records_found: int = 0,
                  new_businesses: int = 0, job_run_id: Optional[int] = None, notes: Optional[str] = None) -> SourceCoverage:
    cov = db.scalar(select(SourceCoverage).where(SourceCoverage.source_id == source.id, SourceCoverage.coverage_date == day))
    if cov is None:
        cov = SourceCoverage(source_id=source.id, coverage_date=day, status=status)
        db.add(cov)
    # Daha önce başarıyla taranmış bir günü sonraki hatalı deneme 'failed' yapmaz
    if not (cov.status == "covered" and status == "failed"):
        cov.status = status
    cov.records_found = max(cov.records_found or 0, records_found) if status != "failed" else (cov.records_found or 0)
    cov.new_businesses = (cov.new_businesses or 0) + new_businesses
    cov.job_run_id = job_run_id or cov.job_run_id
    cov.checked_at = utcnow()
    if notes:
        cov.notes = notes[:2000]
    db.flush()
    return cov


def coverage_calendar(db: Session, start: dt.date, end: dt.date) -> List[Dict]:
    """Gün gün kapsam durumu. Hiçbir kaynakta 'covered' olmayan gün 'taranmadı' olarak döner."""
    rows = db.execute(
        select(SourceCoverage, DataSource.name)
        .join(DataSource, DataSource.id == SourceCoverage.source_id)
        .where(SourceCoverage.coverage_date >= start, SourceCoverage.coverage_date <= end)
    ).all()
    by_day: Dict[dt.date, List] = {}
    for cov, name in rows:
        by_day.setdefault(cov.coverage_date, []).append((cov, name))
    out = []
    d = start
    while d <= end:
        items = by_day.get(d, [])
        statuses = {c.status for c, _ in items}
        if "covered" in statuses:
            st = "covered"
        elif "partial" in statuses:
            st = "partial"
        elif "failed" in statuses:
            st = "failed"
        else:
            st = "not_scanned"
        out.append({
            "date": d.isoformat(), "status": st, "weekend": d.weekday() >= 5,
            "new_businesses": sum(c.new_businesses or 0 for c, _ in items) if st != "not_scanned" else None,
            "sources": [{"source": n, "status": c.status, "records": c.records_found, "notes": c.notes} for c, n in items],
        })
        d += dt.timedelta(days=1)
    return out
