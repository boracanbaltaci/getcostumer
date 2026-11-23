from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery("radar", broker=settings.REDIS_URL, backend=settings.REDIS_URL, include=["app.worker.tasks"])
celery_app.conf.update(
    timezone=settings.TIMEZONE,
    enable_utc=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "gunluk-tarama": {
            "task": "app.worker.tasks.daily_pipeline",
            "schedule": crontab(hour=settings.DAILY_SCAN_HOUR, minute=settings.DAILY_SCAN_MINUTE),
        },
        "gelen-kutusu-kontrolu": {
            # Gün içinde bırakılan gazete dosyalarını hızlı işlemek için saatlik kontrol (08:00–20:00)
            "task": "app.worker.tasks.inbox_check",
            "schedule": crontab(minute=5, hour="9-20"),
        },
        "hatirlatmalar": {
            "task": "app.worker.tasks.reminder_digest",
            "schedule": crontab(hour=8, minute=45),
        },
        "kvkk-saklama": {
            "task": "app.worker.tasks.retention",
            "schedule": crontab(hour=3, minute=15, day_of_week="sunday"),
        },
    },
)
