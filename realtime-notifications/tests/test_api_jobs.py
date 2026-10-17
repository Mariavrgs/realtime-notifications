import httpx
import pytest

from app import main


class FakeResult:
    id = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=main.app)  # sem lifespan (sem Redis/DB)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def test_report_job_is_enqueued(client, monkeypatch):
    calls = []
    monkeypatch.setattr(main.generate_report_pdf, "delay", lambda uid: calls.append(uid) or FakeResult())
    r = await client.post("/jobs/report", json={"user_id": 5})
    assert r.status_code == 202 and r.json()["job_id"] == FakeResult.id
    assert calls == [5]


async def test_download_rejects_bad_job_id(client):
    r = await client.get("/reports/..%2F..%2Fetc%2Fpasswd.pdf")
    assert r.status_code in (400, 404)


async def test_download_not_ready(client):
    r = await client.get("/reports/11111111-1111-1111-1111-111111111111.pdf")
    assert r.status_code == 404
