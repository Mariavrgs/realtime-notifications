import asyncio
import json
import re
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import asyncpg
import redis.asyncio as aioredis
from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from app.config import settings
from app.queries import NAIVE_SQL, SUMMARY_ASYNCPG
from app.tasks.celery_app import celery_app
from app.tasks.tasks import deliver_webhook, generate_report_pdf, send_email
from app.ws import ConnectionManager

manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    listener = asyncio.create_task(manager.listen(app.state.redis))
    try:
        yield
    finally:
        listener.cancel()
        await asyncio.gather(listener, return_exceptions=True)
        await app.state.pool.close()
        await app.state.redis.aclose()


app = FastAPI(title="Realtime Notifications", lifespan=lifespan)


class ReportJob(BaseModel):
    user_id: int


class EmailJob(BaseModel):
    user_id: int
    to: str
    subject: str
    body: str


class WebhookJob(BaseModel):
    user_id: int
    url: HttpUrl
    payload: dict
    secret: str = ""


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------- tarefas em segundo plano: a API só enfileira e responde ----------
@app.post("/jobs/report", status_code=202)
async def create_report(job: ReportJob):
    return {"job_id": generate_report_pdf.delay(job.user_id).id}


@app.post("/jobs/email", status_code=202)
async def create_email(job: EmailJob):
    return {"job_id": send_email.delay(job.user_id, job.to, job.subject, job.body).id}


@app.post("/jobs/webhook", status_code=202)
async def create_webhook(job: WebhookJob):
    return {"job_id": deliver_webhook.delay(job.user_id, str(job.url), job.payload, job.secret).id}


@app.get("/jobs/{job_id}")
async def job_status(job_id: str):
    result = AsyncResult(job_id, app=celery_app)
    return {"job_id": job_id, "state": result.state}


_UUID = re.compile(r"^[0-9a-f\-]{36}$")


@app.get("/reports/{job_id}.pdf")
async def download_report(job_id: str):
    if not _UUID.match(job_id):  # impede path traversal
        raise HTTPException(400, "job_id inválido")
    path = Path(settings.reports_dir) / f"{job_id}.pdf"
    if not path.exists():
        raise HTTPException(404, "relatório ainda não está pronto")
    return FileResponse(path, media_type="application/pdf")


# ---------- WebSocket ----------
@app.websocket("/ws/{user_id}")
async def ws_endpoint(ws: WebSocket, user_id: str):
    await manager.connect(user_id, ws)
    try:
        while True:
            await ws.receive_text()  # mantém a conexão; ignoramos o que o cliente envia
    except WebSocketDisconnect:
        manager.disconnect(user_id, ws)


# ---------- consultas: versão ingênua x otimizada (índice + cache Redis) ----------
def _rows_to_summary(rows) -> list[dict]:
    return [{"status": r[0], "qty": r[1], "total": float(r[2])} for r in rows]


@app.get("/orders/summary-naive/{user_id}")
async def summary_naive(user_id: int, request: Request):
    rows = await request.app.state.pool.fetch(NAIVE_SQL, user_id)
    agg: dict[str, list] = {}
    for r in rows:
        item = agg.setdefault(r["status"], [0, Decimal(0)])
        item[0] += 1
        item[1] += r["amount"]
    return [{"status": s, "qty": q, "total": float(t)} for s, (q, t) in sorted(agg.items())]


@app.get("/orders/summary/{user_id}")
async def summary(user_id: int, request: Request):
    r = request.app.state.redis
    key = f"summary:{user_id}"
    cached = await r.get(key)
    if cached:
        return json.loads(cached)
    rows = await request.app.state.pool.fetch(SUMMARY_ASYNCPG, user_id)
    data = _rows_to_summary(rows)
    await r.set(key, json.dumps(data), ex=settings.cache_ttl_seconds)
    return data
