"""Compara latência de endpoints GET (versão ingênua x otimizada).

  python bench/bench.py --path /orders/summary-naive/{uid} --requests 2000 --concurrency 20
  python bench/bench.py --path /orders/summary/{uid}       --requests 2000 --concurrency 20

{uid} é substituído por um usuário aleatório entre 1 e 1000.
Rode cada caminho nas mesmas condições e anote os resultados no README.
"""
import argparse
import asyncio
import random
import statistics
import time

import httpx


async def worker(client, path, n, latencies, errors):
    for _ in range(n):
        url = path.replace("{uid}", str(random.randint(1, 1000)))
        t0 = time.perf_counter()
        try:
            r = await client.get(url)
            if r.status_code >= 400:
                errors.append(r.status_code)
        except httpx.HTTPError as exc:
            errors.append(type(exc).__name__)
        latencies.append((time.perf_counter() - t0) * 1000)


def pct(data, p):
    data = sorted(data)
    return data[min(len(data) - 1, int(len(data) * p))]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--path", required=True)
    ap.add_argument("--requests", type=int, default=2000)
    ap.add_argument("--concurrency", type=int, default=20)
    a = ap.parse_args()

    latencies, errors = [], []
    async with httpx.AsyncClient(base_url=a.url, timeout=30) as client:
        t0 = time.perf_counter()
        await asyncio.gather(
            *(worker(client, a.path, a.requests // a.concurrency, latencies, errors) for _ in range(a.concurrency))
        )
        elapsed = time.perf_counter() - t0
    print(f"path={a.path} requests={len(latencies)} errors={len(errors)} {len(latencies) / elapsed:,.0f} req/s")
    print(
        f"latency ms: mean={statistics.mean(latencies):.1f} p50={pct(latencies, .5):.1f} "
        f"p95={pct(latencies, .95):.1f} p99={pct(latencies, .99):.1f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
