from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_reports_components() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "database", "llm_configured"}
    assert body["status"] in {"ok", "degraded"}
    assert isinstance(body["llm_configured"], bool)
