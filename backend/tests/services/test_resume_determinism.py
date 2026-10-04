import io

import pdfplumber
from fakes import synthetic_resume

from app.schemas.resume_document import Generation
from app.services.resume_render.fit import fit_layout
from app.services.resume_render.page_meter import compile_pdf, measure_pages
from app.services.resume_render.typst_data import PRESETS, build_data


def extracted_text(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return "\n".join(page.extract_text() or "" for page in document.pages)


def test_fit_and_render_are_identical_across_runs_for_every_target() -> None:
    content = synthetic_resume(4, 7, seed=21, words=14)

    for target in (1, 2, 3, 4):
        first = fit_layout(content, Generation(), target, "classic", measure_pages, 30)
        second = fit_layout(content, Generation(), target, "classic", measure_pages, 30)
        assert first.model_dump() == second.model_dump()

        preset = next(p for p in PRESETS if p.name == first.preset)
        data = build_data(content, frozenset(first.included_ids), preset, "classic")
        pdf_one, pdf_two = compile_pdf(data), compile_pdf(data)
        assert extracted_text(pdf_one) == extracted_text(pdf_two)
        assert pdf_one == pdf_two
