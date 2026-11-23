"""Dosya içe aktarma iş akışı (CSV / Excel / PDF)."""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Business, DataSource, ImportBatch
from app.services import ingestion
from app.services.contacts import add_contact
from app.services.coverage import mark_coverage
from app.services.importers import pdf as pdf_importer
from app.services.importers import tabular
from app.services.normalize import parse_date


def run_import(db: Session, source: DataSource, filename: str, data: bytes, *, user_id: Optional[int] = None,
               declared_establishment: bool = True, gazette_date: Optional[str] = None,
               gazette_no: Optional[str] = None, marks_full_day: bool = False, job_run_id: Optional[int] = None,
               ) -> ImportBatch:
    """Dosyayı içe aktarır.

    declared_establishment: Dosyada 'ilan türü' sütunu yoksa satırların yeni kuruluş olduğunu
        kullanıcı beyan eder. İlan türü sütunu varsa her zaman ona göre filtrelenir.
    marks_full_day: Dosya o günün TAM gazetesi/fihristi ise (ör. satın alınan günlük elektronik
        gazete) o yayın günü 'tarandı' olarak işaretlenir.
    """
    sha = hashlib.sha256(data).hexdigest()
    lower = filename.lower()
    ftype = "pdf" if lower.endswith(".pdf") else ("xlsx" if lower.endswith((".xlsx", ".xlsm")) else "csv")
    batch = ImportBatch(source_id=source.id, filename=filename[:500], file_type=ftype, file_sha256=sha,
                        uploaded_by=user_id, status="processing")
    db.add(batch)
    db.flush()

    results: List[ingestion.IngestResult] = []
    errors: List[Dict[str, Any]] = []
    gazette_dates: Dict[str, Dict[str, int]] = {}
    contacts_added = 0
    try:
        if ftype == "pdf":
            for page_no, rec, raw_text, warnings in pdf_importer.iter_announcements(data, gazette_date, gazette_no):
                rec["source_reference"] = f"{filename} – sayfa {page_no}"
                r = ingestion.ingest_record(db, source, rec, batch=batch, raw_text=raw_text, payload=rec,
                                            declared_establishment=False)
                results.append(r)
                if warnings:
                    errors.append({"row": f"sayfa {page_no}", "warning": "; ".join(warnings), "status": r.status})
                _count_day(gazette_dates, rec.get("gazette_date"), r)
        else:
            for row_no, rec in tabular.iter_records(filename, data):
                contacts = tabular.extract_contacts(rec)
                rec.setdefault("source_reference", f"{filename} – satır {row_no}")
                if gazette_date and not rec.get("gazette_date"):
                    rec["gazette_date"] = gazette_date
                if gazette_no and not rec.get("gazette_no"):
                    rec["gazette_no"] = gazette_no
                try:
                    with db.begin_nested():
                        r = ingestion.ingest_record(db, source, rec, batch=batch,
                                                    declared_establishment=declared_establishment)
                        results.append(r)
                        if r.business_id and r.status in ("created", "updated", "duplicate_business"):
                            b = db.get(Business, r.business_id)
                            for ctype, val in contacts.items():
                                if val:
                                    cp, _ = add_contact(db, b, ctype, val, source_name=f"İçe aktarım: {filename}",
                                                        source_url=None, confidence=55,
                                                        evidence=f"Kullanıcı dosyası satır {row_no}")
                                    contacts_added += 1 if cp else 0
                except Exception as exc:  # satır bazlı hata, tüm içe aktarmayı durdurmaz
                    errors.append({"row": row_no, "error": str(exc)[:500]})
                    continue
                _count_day(gazette_dates, rec.get("gazette_date"), r)
        batch.status = "completed"
    except ValueError as exc:
        batch.status = "failed"
        errors.append({"row": None, "error": str(exc)})

    stats = ingestion.summarize(results)
    stats["total_rows"] = len(results)
    stats["contacts_added"] = contacts_added
    batch.stats = stats
    batch.errors = errors[:500]

    if marks_full_day and batch.status == "completed":
        for day_s, cnt in gazette_dates.items():
            d = parse_date(day_s)
            if d:
                mark_coverage(db, source, d, "covered", records_found=cnt["records"], new_businesses=cnt["created"],
                              job_run_id=job_run_id, notes=f"Dosya: {filename}")
    db.flush()
    return batch


def _count_day(acc: Dict[str, Dict[str, int]], day: Optional[str], r: ingestion.IngestResult) -> None:
    if not day:
        return
    d = acc.setdefault(str(day), {"records": 0, "created": 0})
    d["records"] += 1
    if r.status == "created":
        d["created"] += 1


def already_imported(db: Session, data: bytes) -> Optional[ImportBatch]:
    sha = hashlib.sha256(data).hexdigest()
    return db.scalar(select(ImportBatch).where(ImportBatch.file_sha256 == sha, ImportBatch.status == "completed"))
