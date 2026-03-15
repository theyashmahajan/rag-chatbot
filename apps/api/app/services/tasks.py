from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_client = Celery("rag_api", broker=settings.redis_url, backend=settings.redis_url)


def enqueue_document_ingestion(document_id: str) -> None:
    celery_client.send_task("ingestion.process_document", args=[document_id], queue="ingestion")

