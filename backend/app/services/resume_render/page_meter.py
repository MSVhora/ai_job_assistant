import io
import json
import logging
from pathlib import Path

import pdfplumber
import typst

from app.core.errors import ResumeRenderError
from app.services.resume_render.typst_data import JsonObject

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "resources" / "typst" / "resume.typ"


def compile_pdf(data: JsonObject) -> bytes:
    """Compile the template with `data` as its only input; the single call into the compiler.

    Compiler messages can quote resume text, so they are never logged or surfaced.
    """
    try:
        pdf = typst.compile(
            TEMPLATE_PATH,
            sys_inputs={"data": json.dumps(data, ensure_ascii=False)},
            ignore_system_fonts=True,
        )
    except typst.TypstError as exc:
        logger.warning("resume.render compile failed error=%s", type(exc).__name__)
        raise ResumeRenderError from exc
    return bytes(pdf)


def count_pages(pdf: bytes) -> int:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return len(document.pages)


def measure_pages(data: JsonObject) -> int:
    """The `PageMeter` the fit uses: compile in memory and count pages."""
    return count_pages(compile_pdf(data))
