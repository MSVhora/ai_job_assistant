import pytest
from httpx import ASGITransport, AsyncClient

from app.core.errors import DomainError, DuplicateRunError
from app.main import create_app


def all_domain_errors() -> list[type[DomainError]]:
    found: list[type[DomainError]] = []
    pending = list(DomainError.__subclasses__())
    while pending:
        cls = pending.pop()
        found.append(cls)
        pending.extend(cls.__subclasses__())
    return sorted(found, key=lambda cls: cls.__name__)


@pytest.mark.parametrize("error_class", all_domain_errors(), ids=lambda cls: cls.__name__)
async def test_domain_error_renders_detail_and_declared_status(
    error_class: type[DomainError],
) -> None:
    application = create_app()

    @application.get("/raise")
    async def raise_error() -> None:
        raise error_class

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.get("/raise")

    body = response.json()
    assert response.status_code == error_class.status_code
    assert isinstance(body["detail"], str)
    assert body["detail"] == error_class.default_detail
    allowed_extra = {"active_search_id"} if issubclass(error_class, DuplicateRunError) else set()
    assert set(body) - {"detail"} <= allowed_extra


async def test_validation_error_renders_readable_detail() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/matches", params={"limit": "many"})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
