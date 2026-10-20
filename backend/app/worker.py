"""Celery worker:  celery -A app.worker worker --loglevel=info"""
from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery = Celery("queryhub", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"],
                   broker_connection_retry_on_startup=True)


@celery.task(name="qtrace.run_investigation")
def run_investigation(experiment_id: str) -> dict:
    """Long Q-TRACE+ investigation background me (Ch 2.2)."""
    from app.services.experiments.runner import execute_experiment

    run_id = execute_experiment(experiment_id)
    return {"id": experiment_id, "run_id": run_id}


def broker_available(timeout: float = 0.5) -> bool:
    try:
        import redis

        redis.Redis.from_url(settings.redis_url, socket_connect_timeout=timeout).ping()
        return True
    except Exception:
        return False

