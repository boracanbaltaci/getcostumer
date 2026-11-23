"""İçe aktarma, inceleme kuyruğu, veri kaynakları, görevler, raporlar ve dışa aktarma uç noktaları."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import audit, get_current_user, require_role
from app.models import (
    AuditLog, Business, DailyReport, DataSource, ImportBatch, JobRun, NaceHazard, RawRecord, SourceCoverage, User, utcnow,
)
from app.schemas import ReviewApprove, SourceUpdate
from app.serializers import business_detail, raw_out
from app.services import exports, ingestion, reports
from app.services.coverage import coverage_calendar
from app.services.importers import tabular
from app.services.importers.runner import already_imported, run_import
from app.services.normalize import clean_nace, fold
from app.services.scoring.engine import analyze_business
from app.services.sources.registry import check_health, get_source
from app.worker.dispatch import dispatch

router = APIRouter()
MAX_UPLOAD = 50 * 1024 * 1024


# ------------------------------------------------------------------ İçe aktarma
@router.post("/imports", tags=["imports"])
async def upload_import(
    file: UploadFile = File(...), declared_establishment: bool = Form(True), full_day: bool = Form(False),
    gazette_date: Optional[str] = Form(None), gazette_no: Optional[str] = Form(None), allow_duplicate_file: bool = Form(False),
    source_key: str = Form("manual_import"), db: Session = Depends(get_db), user: User = Depends(require_role("sales")),
):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Dosya 50 MB sınırını aşıyor")
    if source_key not in ("manual_import", "ttsg_inbox"):
        raise HTTPException(400, "Geçersiz kaynak")
    prev = already_imported(db, data)
    if prev and not allow_duplicate_file:
        raise HTTPException(409, f"Bu dosya {prev.created_at:%d.%m.%Y %H:%M} tarihinde içe aktarılmış (#{prev.id})")
    source = get_source(db, source_key)
    batch = run_import(db, source, file.filename or "dosya", data, user_id=user.id,
                       declared_establishment=declared_establishment, gazette_date=gazette_date,
                       gazette_no=gazette_no, marks_full_day=full_day)
    audit(db, user, "import", "import_batch", batch.id, {"filename": file.filename, "stats": batch.stats})
    db.commit()
    dispatch("enrich_and_score")
    return _batch_out(batch)


@router.post("/imports/preview", tags=["imports"])
async def preview_import(file: UploadFile = File(...), _: User = Depends(require_role("sales"))):
    data = await file.read()
    name = file.filename or ""
    if name.lower().endswith(".pdf"):
        from app.services.importers.pdf import iter_announcements
        try:
            items = [dict(rec, _page=p, _warnings=w) for p, rec, _, w in iter_announcements(data)][:20]
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return {"type": "pdf", "columns": {}, "sample": items}
    try:
        cols = tabular.mapped_columns(name, data)
        sample = [rec for _, rec in zip(range(10), (r for _, r in tabular.iter_records(name, data)))]
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"type": "tabular", "columns": cols, "sample": sample}


def _batch_out(b: ImportBatch) -> dict:
    return {"id": b.id, "source": b.source.name if b.source else None, "filename": b.filename, "file_type": b.file_type,
            "status": b.status, "created_at": b.created_at, "stats": b.stats, "errors": b.errors}


@router.get("/imports", tags=["imports"])
def list_imports(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_batch_out(b) for b in db.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc()).limit(100)).all()]


@router.get("/imports/{iid}", tags=["imports"])
def get_import(iid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    b = db.get(ImportBatch, iid)
    if not b:
        raise HTTPException(404, "Bulunamadı")
    out = _batch_out(b)
    out["records"] = [raw_out(r, with_text=False) for r in db.scalars(
        select(RawRecord).where(RawRecord.import_batch_id == iid).order_by(RawRecord.id).limit(1000)).all()]
    return out


@router.post("/imports/nace-hazard", tags=["imports"])
async def import_nace_hazard(file: UploadFile = File(...), db: Session = Depends(get_db),
                             user: User = Depends(require_role("manager"))):
    """İşyeri Tehlike Sınıfları Tebliği ekindeki listeyi (NACE kodu, tanım, tehlike sınıfı) yükler."""
    data = await file.read()
    try:
        headers, body = tabular.read_rows(file.filename or "liste.xlsx", data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    fh = [fold(h) for h in headers]

    def col(*names):
        for n in names:
            for i, h in enumerate(fh):
                if n in h:
                    return i
        return None
    ci, di, hi = col("nace"), col("tanim", "aciklama", "faaliyet"), col("tehlike")
    if ci is None or hi is None:
        raise HTTPException(400, "Dosyada 'NACE Kodu' ve 'Tehlike Sınıfı' sütunları bulunmalı")
    n = 0
    for row in body:
        code = clean_nace(row[ci] if ci < len(row) else None)
        hz = fold(str(row[hi] if hi < len(row) else ""))
        hz_key = "cok_tehlikeli" if "cok" in hz else ("tehlikeli" if "tehlikeli" in hz and "az" not in hz else
                                                     ("az_tehlikeli" if "az" in hz else None))
        if not code or not hz_key:
            continue
        row_obj = db.get(NaceHazard, code) or NaceHazard(code=code)
        row_obj.hazard_class = hz_key
        row_obj.description = str(row[di])[:1000] if di is not None and di < len(row) and row[di] else row_obj.description
        row_obj.source = file.filename
        row_obj.imported_at = utcnow()
        db.merge(row_obj)
        n += 1
    db.query(Business).update({Business.analyzed_at: None})
    audit(db, user, "nace_hazard_import", None, None, {"rows": n, "file": file.filename})
    db.commit()
    dispatch("score")
    return {"imported": n}


@router.get("/nace-hazard/stats", tags=["imports"])
def nace_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return {"rows": db.scalar(select(func.count(NaceHazard.code))) or 0}


# ------------------------------------------------------------------ İnceleme kuyruğu
@router.get("/review", tags=["review"])
def review_queue(status: str = "needs_review", limit: int = 200, db: Session = Depends(get_db),
                 _: User = Depends(require_role("sales"))):
    rows = db.scalars(select(RawRecord).where(RawRecord.status == status).order_by(RawRecord.fetched_at.desc()).limit(limit)).all()
    return [raw_out(r) for r in rows]


@router.post("/review/{rid}/approve", tags=["review"])
def review_approve(rid: int, body: ReviewApprove, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    r = db.get(RawRecord, rid)
    if not r:
        raise HTTPException(404, "Kayıt bulunamadı")
    rec = dict(r.payload or {})
    rec.update({k: v for k, v in body.fields.items() if k in ingestion.CANONICAL_FIELDS})
    src = db.get(DataSource, r.source_id)
    res = ingestion.ingest_record(db, src, rec, raw_text=r.raw_text, payload=r.payload, reviewed_by_user=True)
    if not res.business_id:
        db.rollback()
        raise HTTPException(400, f"Onaylanamadı: {res.reason}")
    audit(db, user, "review_approve", "raw_record", rid, {"business_id": res.business_id})
    db.commit()
    b = db.get(Business, res.business_id)
    analyze_business(db, b, use_llm=False)
    db.commit()
    dispatch("enrich_and_score")
    return business_detail(b)


@router.post("/review/{rid}/reject", tags=["review"])
def review_reject(rid: int, reason: str = "Kuruluş ilanı değil", db: Session = Depends(get_db),
                  user: User = Depends(require_role("sales"))):
    r = db.get(RawRecord, rid)
    if not r:
        raise HTTPException(404, "Kayıt bulunamadı")
    r.status, r.skip_reason = "rejected", reason[:255]
    audit(db, user, "review_reject", "raw_record", rid, {"reason": reason})
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ Kaynaklar
def _source_out(db: Session, s: DataSource) -> dict:
    last_cov = db.scalar(select(func.max(SourceCoverage.coverage_date)).where(
        SourceCoverage.source_id == s.id, SourceCoverage.status == "covered"))
    failed = db.scalar(select(func.count(SourceCoverage.id)).where(SourceCoverage.source_id == s.id,
                                                                   SourceCoverage.status == "failed")) or 0
    n_bus = db.scalar(select(func.count(Business.id)).where(Business.source_id == s.id)) or 0
    return {"id": s.id, "key": s.key, "name": s.name, "kind": s.kind, "url": s.url, "enabled": s.enabled,
            "automated": s.automated, "legal_basis": s.legal_basis, "access_notes": s.access_notes, "health": s.health,
            "last_checked_at": s.last_checked_at, "last_success_at": s.last_success_at, "last_error": s.last_error,
            "last_covered_date": last_cov, "failed_days": failed, "businesses": n_bus}


@router.get("/sources", tags=["sources"])
def list_sources(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    out = []
    for s in db.scalars(select(DataSource).order_by(DataSource.id)).all():
        check_health(db, s)
        out.append(_source_out(db, s))
    db.commit()
    return out


@router.patch("/sources/{sid}", tags=["sources"])
def update_source(sid: int, body: SourceUpdate, db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    s = db.get(DataSource, sid)
    if not s:
        raise HTTPException(404, "Kaynak bulunamadı")
    if body.enabled is not None:
        if s.kind == "reference" and body.enabled:
            raise HTTPException(400, "Bu kaynak için yetkili otomatik erişim yolu yok; manuel içe aktarma kullanın")
        s.enabled = body.enabled
    if body.config is not None:
        s.config = body.config
    audit(db, user, "source_update", "source", sid, body.model_dump(exclude_none=True))
    db.commit()
    return _source_out(db, s)


@router.get("/coverage", tags=["sources"])
def coverage(start: Optional[dt.date] = None, end: Optional[dt.date] = None, db: Session = Depends(get_db),
             _: User = Depends(get_current_user)):
    end = end or reports.today_tr()
    start = start or end - dt.timedelta(days=29)
    if (end - start).days > 366:
        raise HTTPException(400, "En fazla 1 yıllık aralık")
    return coverage_calendar(db, start, end)


# ------------------------------------------------------------------ Görevler
def _job_out(j: JobRun, with_log: bool = False) -> dict:
    d = {"id": j.id, "job_type": j.job_type, "status": j.status, "triggered_by": j.triggered_by, "started_at": j.started_at,
         "finished_at": j.finished_at, "stats": j.stats, "error": j.error}
    if with_log:
        d["log"] = j.log
    return d


@router.get("/jobs", tags=["jobs"])
def list_jobs(limit: int = 50, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_job_out(j) for j in db.scalars(select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)).all()]


@router.get("/jobs/{jid}", tags=["jobs"])
def get_job(jid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    j = db.get(JobRun, jid)
    if not j:
        raise HTTPException(404, "Görev bulunamadı")
    return _job_out(j, with_log=True)


@router.post("/jobs/{kind}", tags=["jobs"])
def run_job(kind: str, dry_run: bool = True, db: Session = Depends(get_db), user: User = Depends(require_role("manager"))):
    if kind not in ("daily", "enrich_and_score", "score", "retention"):
        raise HTTPException(400, "Bilinmeyen görev")
    if kind == "retention" and user.role != "admin":
        raise HTTPException(403, "Saklama politikası görevi yalnızca yönetici tarafından çalıştırılabilir")
    audit(db, user, "job_trigger", "job", kind, {"dry_run": dry_run})
    db.commit()
    if kind == "retention":
        from app.services.retention import apply_retention
        res = apply_retention(db, dry_run=dry_run)
        db.commit()
        return res
    mode = dispatch(kind, triggered_by=f"user:{user.id}")
    return {"queued": True, "mode": mode}


# ------------------------------------------------------------------ Panel ve raporlar
@router.get("/dashboard", tags=["reports"])
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return reports.dashboard(db)


@router.get("/reports/daily", tags=["reports"])
def daily_reports(limit: int = 30, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [{"date": r.report_date, "content": r.content, "sent_at": r.sent_at}
            for r in db.scalars(select(DailyReport).order_by(DailyReport.report_date.desc()).limit(limit)).all()]


@router.post("/reports/daily/rebuild", tags=["reports"])
def rebuild_daily(day: Optional[dt.date] = None, db: Session = Depends(get_db), _: User = Depends(require_role("manager"))):
    rep = reports.build_daily_report(db, day or reports.today_tr(), None)
    db.commit()
    return {"date": rep.report_date, "content": rep.content}


@router.get("/reports/sales", tags=["reports"])
def sales(start: Optional[dt.date] = None, end: Optional[dt.date] = None, db: Session = Depends(get_db),
          _: User = Depends(get_current_user)):
    end = end or reports.today_tr()
    start = start or end.replace(day=1)
    return reports.sales_report(db, start, end)


@router.get("/reports/sales.xlsx", tags=["reports"])
def sales_xlsx(start: Optional[dt.date] = None, end: Optional[dt.date] = None, db: Session = Depends(get_db),
               user: User = Depends(require_role("sales"))):
    end = end or reports.today_tr()
    start = start or end.replace(day=1)
    data = exports.sales_report_xlsx(reports.sales_report(db, start, end))
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="satis-raporu-{start}-{end}.xlsx"'})


# ------------------------------------------------------------------ Dışa aktarma
@router.get("/exports/businesses.{fmt}", tags=["exports"])
def export_businesses(fmt: str, request: Request, db: Session = Depends(get_db), user: User = Depends(require_role("sales"))):
    from app.api.businesses import build_query
    params = {}
    qp = request.query_params
    list_keys = {"district", "sector", "company_type", "sales_status", "priority", "stage"}
    for k in ("q", "date_from", "date_to", "isg_min", "software_min", "has_contact", "service_line", "owner_id",
              "detected_from", "sort", "district", "sector", "company_type", "sales_status", "priority", "stage"):
        if k in list_keys:
            vals = qp.getlist(k)
            if vals:
                params[k] = vals
        elif k in qp:
            v = qp.get(k)
            if k in ("isg_min", "software_min", "owner_id"):
                params[k] = int(v)
            elif k in ("date_from", "date_to", "detected_from"):
                params[k] = dt.date.fromisoformat(v)
            elif k == "has_contact":
                params[k] = v.lower() in ("1", "true", "evet")
            else:
                params[k] = v
    rows = db.scalars(build_query(**params).options(selectinload(Business.contacts), selectinload(Business.source))
                      .limit(10000)).all()
    audit(db, user, "export", "business", None, {"format": fmt, "count": len(rows), "filters": {k: str(v) for k, v in params.items()}})
    db.commit()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    if fmt == "xlsx":
        return Response(exports.businesses_xlsx(rows),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="isletmeler-{stamp}.xlsx"'})
    if fmt == "pdf":
        return Response(exports.businesses_pdf(rows), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="isletmeler-{stamp}.pdf"'})
    if fmt == "csv":
        import csv
        import io
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow([c[0] for c in exports.EXPORT_COLUMNS])
        from app.services.contacts import best_contacts
        for b in rows:
            c = best_contacts(b)
            if b.do_not_contact:
                c["phone"] = c["email"] = None
            w.writerow([fn(b, c) for _, fn in exports.EXPORT_COLUMNS])
        return Response(("﻿" + buf.getvalue()).encode("utf-8"), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="isletmeler-{stamp}.csv"'})
    raise HTTPException(400, "Desteklenen biçimler: xlsx, pdf, csv")


@router.get("/import-template.xlsx", tags=["imports"])
def import_template(_: User = Depends(get_current_user)):
    from openpyxl import Workbook
    import io
    wb = Workbook()
    ws = wb.active
    ws.append(["Ticaret Unvanı", "Kuruluş Tarihi", "Ticaret Sicil Müdürlüğü", "Ticaret Sicil No", "MERSİS No", "İlçe",
               "Adres", "Faaliyet Konusu", "NACE Kodu", "NACE Doğrulandı", "Şirket Türü", "Sermaye", "İlan Türü",
               "Gazete Tarihi", "Gazete Sayısı", "İlan Linki", "Kurumsal Telefon", "Kurumsal E-posta", "Web Sitesi"])
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="ice-aktarma-sablonu.xlsx"'})


# ------------------------------------------------------------------ Denetim kaydı
@router.get("/audit", tags=["audit"])
def audit_log(limit: int = 200, action: Optional[str] = None, db: Session = Depends(get_db),
              _: User = Depends(require_role("admin"))):
    stmt = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.user_id).order_by(AuditLog.created_at.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return [{"id": a.id, "user": email, "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
             "details": a.details, "ip": a.ip, "created_at": a.created_at} for a, email in db.execute(stmt.limit(limit)).all()]
