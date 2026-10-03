import pytest
from httpx import ASGITransport, AsyncClient

from app.core.pagination import TOTAL_COUNT_HEADER
from app.main import create_app

ALLOWED_ORIGIN = "http://localhost:3000"


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def preflight(client: AsyncClient, *, origin: str, method: str, headers: str) -> object:
    return await client.options(
        "/api/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        },
    )


async def test_preflight_from_allowed_origin_with_frontend_request_succeeds(
    client: AsyncClient,
) -> None:
    for method in ("GET", "POST", "PATCH", "DELETE"):
        response = await preflight(
            client, origin=ALLOWED_ORIGIN, method=method, headers="content-type"
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
        assert response.headers["access-control-allow-credentials"] == "true"


async def test_preflight_from_other_origin_is_rejected(client: AsyncClient) -> None:
    response = await preflight(
        client, origin="http://evil.example", method="POST", headers="content-type"
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_preflight_with_disallowed_method_is_rejected(client: AsyncClient) -> None:
    response = await preflight(client, origin=ALLOWED_ORIGIN, method="PUT", headers="content-type")

    assert response.status_code == 400


async def test_preflight_with_disallowed_header_is_rejected(client: AsyncClient) -> None:
    response = await preflight(
        client, origin=ALLOWED_ORIGIN, method="POST", headers="content-type,x-custom-token"
    )

    assert response.status_code == 400


async def test_total_count_header_is_exposed_to_browsers(client: AsyncClient) -> None:
    response = await client.get("/api/health", headers={"Origin": ALLOWED_ORIGIN})

    exposed = response.headers["access-control-expose-headers"].lower()
    assert TOTAL_COUNT_HEADER.lower() in exposed
