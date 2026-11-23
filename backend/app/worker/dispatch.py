"""Arka plan görevi gönderimi: Celery/Redis varsa kuyruğa, yoksa süreç içi iş parçacığına."""
from __future__ import annotations

import logging
import threading

from app.config import settings

log = logging.getLogger(__name__)

TASKS = {
    "daily": "app.worker.tasks.daily_pipeline",
    "enrich_and_score": "app.worker.tasks.enrich_and_score",
    "score": "app.worker.tasks.score",
    "inbox": "app.worker.tasks.inbox_check",
}


def _broker_available() -> bool:
    if settings.ENVIRONMENT == "test":
        return False
    try:
        import redis
        redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1).ping()
        return True
    except Exception:
        return False


def dispatch(kind: str, triggered_by: str = "user") -> str:
    name = TASKS[kind]
    if settings.ENVIRONMENT == "test":
        return "skipped_in_tests"
    if _broker_available():
        from app.worker.celery_app import celery_app
        celery_app.send_task(name, kwargs={"triggered_by": triggered_by})
        return "queued"
    from app.worker import tasks
    fn = getattr(tasks, name.rsplit(".", 1)[1])
    threading.Thread(target=fn, kwargs={"triggered_by": triggered_by}, daemon=True).start()
    log.warning("Redis erişilemedi; '%s' görevi süreç içinde çalıştırılıyor", kind)
    return "thread"
