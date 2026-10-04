import asyncio
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.resume_document import Layout, ResumeDocumentResponse
from app.services import resume_documents
from app.services.resume_blocks import ensure_ids
from app.services.resume_builder import Context, load_context, persist
from app.services.resume_render.render import render_pdf


async def _fitted_context(session: AsyncSession, document_id: uuid.UUID, source: str) -> Context:
    """Current content re-fitted to the page target; raises `CannotFitError` when it cannot be."""
    ctx = await load_context(session, await resume_documents.owned_document(session, document_id))
    ensure_ids(ctx.content)
    await persist(ctx, source, strict=True)
    return ctx


async def refit_document(session: AsyncSession, document_id: uuid.UUID) -> ResumeDocumentResponse:
    """Layout only: measured in memory, no PDF leaves this function."""
    ctx = await _fitted_context(session, document_id, "fit")
    return resume_documents.to_response(ctx.document)


async def get_layout(session: AsyncSession, document_id: uuid.UUID) -> Layout:
    document = await resume_documents.owned_document(session, document_id)
    return Layout.model_validate(document.layout)


def _filename(full_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", full_name.casefold()).strip("-")
    return f"resume-{slug}.pdf" if slug else "resume.pdf"


async def render_document(session: AsyncSession, document_id: uuid.UUID) -> tuple[bytes, str]:
    """Explicit "Generate PDF": re-fit the current content, then render exactly what was fitted."""
    ctx = await _fitted_context(session, document_id, "render")
    layout = Layout.model_validate(ctx.document.layout)
    pdf = await asyncio.to_thread(render_pdf, ctx.content, layout, ctx.document.template)
    return pdf, _filename(ctx.content.basics.full_name)
