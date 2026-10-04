from app.schemas.resume_document import Layout, ResumeContent
from app.services.resume_render.page_meter import compile_pdf
from app.services.resume_render.typst_data import PRESETS, build_data


def render_pdf(content: ResumeContent, layout: Layout, template: str) -> bytes:
    """The PDF for a fitted layout: only its included bullets, at the preset the fit chose."""
    preset = next((p for p in PRESETS if p.name == layout.preset), PRESETS[0])
    return compile_pdf(build_data(content, frozenset(layout.included_ids), preset, template))
