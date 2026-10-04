import io

import pdfplumber
import pytest
from fakes import synthetic_resume

from app.schemas.resume_document import (
    AwardEntry,
    Bullet,
    CertificateEntry,
    ProjectEntry,
    ResumeContent,
)
from app.services.resume_blocks import blocks
from app.services.resume_render.page_meter import compile_pdf
from app.services.resume_render.typst_data import PRESETS, build_data

EMAIL = "ada@example.com"


def full_resume() -> ResumeContent:
    content = synthetic_resume(2, 3, seed=31, words=5)
    content.basics.summary = "Backend engineer."
    content.projects = [
        ProjectEntry(
            id="proj",
            name="Toolkit",
            technologies=["Rust"],
            highlights=[Bullet(id="p0", text="Shipped the Toolkit CLI", check="passed")],
        )
    ]
    content.certificates = [CertificateEntry(name="Cloud Architect", issuer="Vendor")]
    content.awards = [AwardEntry(title="Hackathon Winner")]
    return content


def render(content: ResumeContent, template: str) -> bytes:
    included = frozenset(b.id for entry in blocks(content) for b in entry.highlights)
    return compile_pdf(build_data(content, included, PRESETS[0], template))


@pytest.fixture(params=["classic", "compact"])
def pdf(request: pytest.FixtureRequest) -> bytes:
    return render(full_resume(), request.param)


def test_headings_appear_in_standard_order(pdf: bytes) -> None:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        text = document.pages[0].extract_text()

    order = ["Summary", "Experience", "Education", "Skills", "Projects", "Certifications", "Awards"]
    positions = [text.index(heading) for heading in order]
    assert positions == sorted(positions)


def test_bullets_are_real_text_lines_with_a_plain_glyph(pdf: bytes) -> None:
    content = full_resume()
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        lines = (document.pages[0].extract_text() or "").splitlines()

    for entry in blocks(content):
        for bullet in entry.highlights:
            assert f"• {bullet.text}" in lines


def test_text_has_no_replacement_or_empty_glyph_boxes(pdf: bytes) -> None:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        text = "".join(page.extract_text() or "" for page in document.pages)

    assert "�" not in text
    assert "□" not in text
    assert "(cid:" not in text


def test_contact_appears_exactly_once_in_the_body(pdf: bytes) -> None:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        text = "".join(page.extract_text() or "" for page in document.pages)

    assert text.count(EMAIL) == 1
    assert text.count("555 0100") == 1


def test_document_has_no_tables_or_images(pdf: bytes) -> None:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        for page in document.pages:
            assert page.find_tables() == []
            assert page.images == []


def test_compact_template_is_a_single_left_aligned_column() -> None:
    with pdfplumber.open(io.BytesIO(render(full_resume(), "compact"))) as document:
        page = document.pages[0]
        lefts = {round(float(word["x0"])) for word in page.extract_words(keep_blank_chars=False)}
        first_of_line: dict[int, float] = {}
        for word in page.extract_words():
            first_of_line.setdefault(round(float(word["top"])), float(word["x0"]))

    assert max(first_of_line.values()) < float(page.width) * 0.2
    assert len(lefts) > 1
