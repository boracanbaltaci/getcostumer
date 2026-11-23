"""Komut satırı araçları.

Kullanım:
  python -m app.cli create-admin --email admin@firma.com --name "Ad Soyad"
  python -m app.cli run-daily            # günlük akışı hemen çalıştır
  python -m app.cli import <dosya> [--full-day] [--not-declared]
  python -m app.cli seed-sources
  python -m app.cli retention [--apply]
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password, validate_password_strength


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="radar")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("create-admin")
    a.add_argument("--email", required=True)
    a.add_argument("--name", default="Yönetici")
    a.add_argument("--password")
    sub.add_parser("run-daily")
    sub.add_parser("seed-sources")
    i = sub.add_parser("import")
    i.add_argument("path")
    i.add_argument("--full-day", action="store_true", help="Dosya o günün tam gazetesi/fihristi")
    i.add_argument("--not-declared", action="store_true", help="İlan türü yoksa satırları kuruluş kabul etme")
    r = sub.add_parser("retention")
    r.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)

    with SessionLocal() as db:
        if args.cmd == "create-admin":
            pw = args.password or getpass.getpass("Parola: ")
            err = validate_password_strength(pw)
            if err:
                print(err)
                return 1
            u = db.scalar(select(User).where(User.email == args.email.lower()))
            if u:
                u.password_hash, u.role, u.is_active = hash_password(pw), "admin", True
            else:
                db.add(User(email=args.email.lower(), full_name=args.name, role="admin", password_hash=hash_password(pw)))
            db.commit()
            print("Yönetici hazır:", args.email)
        elif args.cmd == "seed-sources":
            from app.services.sources.registry import seed_sources
            seed_sources(db)
            db.commit()
            print("Kaynaklar yüklendi")
        elif args.cmd == "run-daily":
            from app.services.pipeline import run_daily_pipeline
            job = run_daily_pipeline(db, triggered_by="cli")
            if job is None:
                print("Başka bir günlük akış çalışıyor")
                return 1
            print(json.dumps({"job": job.id, "status": job.status, "stats": job.stats}, ensure_ascii=False, indent=2, default=str))
        elif args.cmd == "import":
            from app.services.importers.runner import run_import
            from app.services.sources.registry import get_source
            with open(args.path, "rb") as fh:
                data = fh.read()
            batch = run_import(db, get_source(db, "manual_import"), args.path.rsplit("/", 1)[-1], data,
                               declared_establishment=not args.not_declared, marks_full_day=args.full_day)
            db.commit()
            print(json.dumps({"status": batch.status, "stats": batch.stats, "errors": batch.errors[:20]},
                             ensure_ascii=False, indent=2, default=str))
        elif args.cmd == "retention":
            from app.services.retention import apply_retention
            res = apply_retention(db, dry_run=not args.apply)
            db.commit()
            print(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
