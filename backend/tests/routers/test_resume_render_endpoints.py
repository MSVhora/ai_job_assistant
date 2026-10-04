import io
import uuid
from typing import Any

import pdfplumber
import pytest
from fakes import FakeResumeLLM, install_acompletion, seed_resume_world
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.errors import CannotFitError
from app.main import app
from app.services import resume_builder

pytestmark = pytest.mark.usefixtures("clean_tables")

BASE = "/api/resume-documents"


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_retry_attempts", 1)
    monkeypatch.setattr(settings, "llm_retry_base_delay_s", 0.0)


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def generate(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, **extra: Any
) -> dict[str, Any]:
    world = await seed_resume_world()
    install_acompletion(monkeypatch, FakeResumeLLM())
    response = await client.post(BASE, json={"profile_id": str(world["profile"]), **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_stores_a_measured_layout(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = await generate(client, monkeypatch, page_target=1)

    layout = document["layout"]
    assert layout["pages"] == 1
    assert layout["preset"] in {"P0", "P1", "P2"}
    assert layout["font_pt"]
    assert layout["margin_in"]
    assert layout["included_ids"]
    assert layout["steps"][-1].startswith("chose ")


async def test_fit_returns_the_layout_as_json_and_no_pdf(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = await generate(client, monkeypatch, page_target=2)

    response = await client.post(f"{BASE}/{document['id']}/fit")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.content[:4] != b"%PDF"
    assert response.json()["layout"]["pages"] <= 2
    stored = await client.get(f"{BASE}/{document['id']}/layout")
    assert stored.json() == response.json()["layout"]


async def test_render_returns_a_pdf_within_the_page_target(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = await generate(client, monkeypatch, page_target=1, template="compact")

    response = await client.post(f"{BASE}/{document['id']}/render")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith('attachment; filename="resume-')
    assert response.content.startswith(b"%PDF")
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        assert len(pdf.pages) == 1
        assert "Experience" in (pdf.pages[0].extract_text() or "")


async def test_render_follows_edits_made_after_generation(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = await generate(client, monkeypatch, page_target=2)
    entry = next(job for job in document["content"]["work"] if job["highlights"])
    bullet = entry["highlights"][0]
    await client.patch(
        f"{BASE}/{document['id']}/bullets/{bullet['id']}", json={"text": "Rewrote the importer"}
    )

    response = await client.post(f"{BASE}/{document['id']}/render")

    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "Rewrote the importer" in text


@pytest.mark.parametrize("path", ["fit", "render"])
async def test_fit_and_render_are_404_for_an_unknown_document(
    client: AsyncClient, path: str
) -> None:
    response = await client.post(f"{BASE}/{uuid.uuid4()}/{path}")

    assert response.status_code == 404


async def test_layout_is_404_for_an_unknown_document(client: AsyncClient) -> None:
    assert (await client.get(f"{BASE}/{uuid.uuid4()}/layout")).status_code == 404


async def test_create_rejects_an_unknown_template(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = await seed_resume_world()
    install_acompletion(monkeypatch, FakeResumeLLM())

    response = await client.post(
        BASE, json={"profile_id": str(world["profile"]), "template": "fancy"}
    )

    assert response.status_code == 422


async def test_fit_and_render_answer_422_when_nothing_fits(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = await generate(client, monkeypatch, page_target=1)

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise CannotFitError

    monkeypatch.setattr(resume_builder, "fit_layout", refuse)

    for path in ("fit", "render"):
        response = await client.post(f"{BASE}/{document['id']}/{path}")
        assert response.status_code == 422
        assert "cannot fit" in response.json()["detail"]


async def test_generation_keeps_its_content_when_nothing_fits(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise CannotFitError

    monkeypatch.setattr(resume_builder, "fit_layout", refuse)

    document = await generate(client, monkeypatch, page_target=1)

    assert document["layout"]["included_ids"] == []
    assert document["layout"]["pages"] is None
    assert any(item["reason"] == "did_not_fit" for item in document["layout"]["not_included"])
    assert any("does not fit" in warning for warning in document["generation"]["warnings"])
    assert any(job["highlights"] for job in document["content"]["work"])
