# Realtime Notifications

Sistema de **tarefas em segundo plano** e **notificações em tempo real** para uma API FastAPI: a API só enfileira o trabalho pesado e responde na hora; quando a tarefa termina, o usuário é avisado por WebSocket.

## O problema

Gerar PDFs, enviar e-mails e chamar webhooks dentro da requisição trava o fluxo principal da API e pode sobrecarregar o banco.

## A solução

```
cliente ──POST /jobs/*──► FastAPI ──► Redis (fila) ──► Celery workers
   ▲                        │ 202                         │ PDF / e-mail / webhook
   │                        │                             ▼
   └──── WebSocket ◄── Redis pub/sub  ◄───────── publica "report.ready" etc.
```

- **Celery + Redis**: filas separadas (`pdf`, `email`, `webhook`), `acks_late`, retentativas com backoff exponencial.
- **WebSocket (FastAPI)**: `/ws/{user_id}` recebe avisos em tempo real. O aviso passa pelo Redis pub/sub, então funciona com várias instâncias da API.
- **Webhooks assinados** com HMAC-SHA256 (`X-Signature-SHA256`).
- **Consultas otimizadas**: `/orders/summary-naive/{id}` (traz todas as linhas e soma em Python) x `/orders/summary/{id}` (agregação no banco com índice *covering* + cache no Redis).

## Como rodar

```bash
docker compose up --build -d
```

Gerar um relatório e acompanhar pelo WebSocket (use [websocat](https://github.com/vi/websocat) ou o console do navegador):

```bash
websocat ws://localhost:8000/ws/42 &
curl -X POST localhost:8000/jobs/report -H 'content-type: application/json' -d '{"user_id": 42}'
# o WebSocket recebe: {"event":"report.ready","data":{"job_id":"...","download_url":"/reports/....pdf"}}
```

E-mail (a caixa de entrada de teste fica em http://localhost:8025):

```bash
curl -X POST localhost:8000/jobs/email -H 'content-type: application/json' \
  -d '{"user_id":42,"to":"alguem@example.com","subject":"Oi","body":"Teste"}'
```

Webhook:

```bash
curl -X POST localhost:8000/jobs/webhook -H 'content-type: application/json' \
  -d '{"user_id":42,"url":"https://webhook.site/SEU-ID","payload":{"ok":true},"secret":"segredo"}'
```

## Testes

```bash
pip install -r requirements.txt
pytest
```

## Benchmark das consultas

```bash
pip install httpx
python bench/bench.py --path '/orders/summary-naive/{uid}'
python bench/bench.py --path '/orders/summary/{uid}'
```

Resultados na minha máquina (preencha com os seus números medidos):

| Endpoint | req/s | p50 (ms) | p95 (ms) |
|---|---|---|---|
| `summary-naive` | — | — | — |
| `summary` (índice + cache) | — | — | — |

Os dados são sintéticos (500 mil pedidos, 1.000 usuários, gerados em `sql/02_seed.sql`). A diferença medida depende do volume de dados e do hardware.

## Limitações conhecidas

- Sem autenticação: `user_id` vem direto da URL. Em produção, autentique o WebSocket e as rotas.
- Os PDFs ficam num volume compartilhado entre API e worker; em produção use armazenamento de objetos (S3/MinIO).
- Um único worker consome as três filas; para escalar, rode workers dedicados por fila.
