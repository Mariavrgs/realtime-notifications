"""Tarefas pesadas executadas em segundo plano pelo Celery.

Ao terminar, cada tarefa publica um aviso no canal Redis `notifications:{user_id}`;
a API repassa esse aviso ao navegador pelo WebSocket.
"""
import hashlib
import hmac
import json
import smtplib
from email.message import EmailMessage
from pathlib import Path

import httpx
import psycopg
import redis
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.config import settings
from app.queries import SUMMARY_PSYCOPG
from app.tasks.celery_app import celery_app


def publish_notification(user_id: int, event: str, data: dict) -> None:
    client = redis.Redis.from_url(settings.redis_url)
    try:
        client.publish(f"notifications:{user_id}", json.dumps({"event": event, "data": data}))
    finally:
        client.close()


def build_pdf(path: Path, user_id: int, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4)
    _, height = A4
    y = height - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, f"Relatório de pedidos - usuário {user_id}")
    y -= 40
    c.setFont("Helvetica", 11)
    for status, qty, total in rows:
        c.drawString(50, y, f"{status:<12} {qty:>6} pedidos   R$ {float(total):>12,.2f}")
        y -= 20
    c.save()


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@celery_app.task(bind=True, autoretry_for=(psycopg.OperationalError,), retry_backoff=True, max_retries=3)
def generate_report_pdf(self, user_id: int) -> dict:
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute(SUMMARY_PSYCOPG, (user_id,)).fetchall()
    path = Path(settings.reports_dir) / f"{self.request.id}.pdf"
    build_pdf(path, user_id, rows)
    publish_notification(
        user_id,
        "report.ready",
        {"job_id": self.request.id, "download_url": f"/reports/{self.request.id}.pdf"},
    )
    return {"path": str(path)}


@celery_app.task(
    bind=True, autoretry_for=(OSError, smtplib.SMTPException), retry_backoff=True, max_retries=5
)
def send_email(self, user_id: int, to: str, subject: str, body: str) -> dict:
    msg = EmailMessage()
    msg["From"] = "no-reply@example.com"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.send_message(msg)
    publish_notification(user_id, "email.sent", {"job_id": self.request.id, "to": to})
    return {"to": to}


@celery_app.task(bind=True, autoretry_for=(httpx.HTTPError,), retry_backoff=True, max_retries=5)
def deliver_webhook(self, user_id: int, url: str, payload: dict, secret: str = "") -> dict:
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = {"content-type": "application/json"}
    if secret:
        headers["X-Signature-SHA256"] = sign_payload(secret, body)
    response = httpx.post(url, content=body, headers=headers, timeout=10)
    response.raise_for_status()
    publish_notification(
        user_id, "webhook.delivered", {"job_id": self.request.id, "status": response.status_code}
    )
    return {"status": response.status_code}
