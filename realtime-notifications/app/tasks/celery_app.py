from celery import Celery

from app.config import settings

celery_app = Celery(
    "notifications",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.tasks"],
)
celery_app.conf.update(
    task_acks_late=True,  # só confirma depois de executar; se o worker cair, a tarefa volta pra fila
    worker_prefetch_multiplier=1,  # evita que um worker "acumule" tarefas longas
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    task_routes={
        "app.tasks.tasks.generate_report_pdf": {"queue": "pdf"},
        "app.tasks.tasks.send_email": {"queue": "email"},
        "app.tasks.tasks.deliver_webhook": {"queue": "webhook"},
    },
)
