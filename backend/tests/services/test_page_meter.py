import io
import logging

import pdfplumber
import pytest
import typst
from fakes import synthetic_resume

from app.core.errors import ResumeRenderError
from app.services.resume_render import page_meter
from app.services.resume_render.page_meter import compile_pdf, count_pages, measure_pages
from app.services.resume_render.typst_data import PRESETS, build_data

HOSTILE = [
    '#panic("boom") and #raw("x")',
    "*bold?* _under_ $x^2$ @label `tick` \\ \"quote\" 'single'",
    "#set text(size: 40pt) // comment /* block */",
    "<tag> {braces} [brackets] ~tilde~ 100% & more",
]


def build(content_text: list[str]) -> bytes:
    content = synthetic_resume(1, len(content_text), seed=41)
    for bullet, text in zip(content.work[0].highlights, content_text, strict=True):
        bullet.text = text
    content.basics.full_name = "Zoë #Ünï *x* $y @z"
    included = frozenset(b.id for b in content.work[0].highlights)
    return compile_pdf(build_data(content, included, PRESETS[0], "classic"))


def test_hostile_text_is_rendered_literally_and_never_executed() -> None:
    pdf = build(HOSTILE)

    with pdfplumber.open(io.BytesIO(pdf)) as document:
        text = document.pages[0].extract_text()
    assert "Zoë #Ünï *x* $y @z" in text
    for item in HOSTILE:
        assert f"• {item}" in text


def test_a_short_document_is_one_page_and_a_long_one_is_several() -> None:
    short = synthetic_resume(1, 2, seed=42)
    long = synthetic_resume(6, 12, seed=43, words=24)
    meter = {
        name: measure_pages(
            build_data(
                content,
                frozenset(b.id for e in content.work for b in e.highlights),
                PRESETS[0],
                "classic",
            )
        )
        for name, content in (("short", short), ("long", long))
    }

    assert meter["short"] == 1
    assert meter["long"] > 1


def test_count_pages_reads_the_compiled_pdf() -> None:
    assert count_pages(build(["One short bullet"])) == 1


def test_a_compiler_failure_becomes_a_render_error_without_logging_content(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def failing(*_args: object, **_kwargs: object) -> bytes:
        message = "secret resume text SECRET-MARKER"
        raise typst.TypstError(message)

    monkeypatch.setattr(page_meter.typst, "compile", failing)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(ResumeRenderError):
        compile_pdf({"name": "SECRET-MARKER"})

    assert "SECRET-MARKER" not in caplog.text
