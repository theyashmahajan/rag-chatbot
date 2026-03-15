from celery import Celery

from worker.config import settings

celery_app = Celery(
    "rag_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks"],
)
celery_app.conf.task_default_queue = "ingestion"
