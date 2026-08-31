import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import FileTooLargeError, TextExtractionError
from app.models import Candidate, Resume
from app.schemas.resume import ResumeUploadResponse
from app.services.text_extraction import SupportedKind, extract_docx, extract_pdf, sniff_file_type

logger = logging.getLogger(__name__)

PARSE_VERSION = "text_v1"


async def get_or_create_candidate(session: AsyncSession) -> Candidate:
    result = await session.execute(select(Candidate).limit(1))
    candidate = result.scalars().first()
    if candidate is None:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
    return candidate


def _extract_from_bytes(data: bytes, kind: SupportedKind) -> tuple[str, int | None]:
    if kind == "pdf":
        text, page_count = extract_pdf(data)
        return text, page_count
    return extract_docx(data), None


def _save_file(uploads_dir: Path, data: bytes, kind: SupportedKind) -> Path:
    uploads_dir.mkdir(parents=True, exist_ok=True)
    destination = uploads_dir / f"{uuid.uuid4().hex}.{kind}"
    destination.write_bytes(data)
    return destination


async def upload_resume(session: AsyncSession, file: UploadFile) -> ResumeUploadResponse:
    started = time.monotonic()
    settings = get_settings()
    max_bytes = settings.resume_max_upload_mb * 1024 * 1024
    filename = file.filename or ""
    content_type = file.content_type or "application/octet-stream"

    if file.size is not None and file.size > max_bytes:
        raise FileTooLargeError(f"file exceeds the {settings.resume_max_upload_mb} MB limit")
    data = await file.read()
    if len(data) > max_bytes:
        raise FileTooLargeError(f"file exceeds the {settings.resume_max_upload_mb} MB limit")

    kind = sniff_file_type(filename, data[:8])
    candidate = await get_or_create_candidate(session)

    text, page_count = await asyncio.to_thread(_extract_from_bytes, data, kind)
    if not text.strip():
        raise TextExtractionError(
            "no readable text found — scanned or image-only PDFs are not supported"
        )

    destination = _save_file(settings.uploads_dir, data, kind)
    parsed_at = datetime.now(UTC)
    resume = Resume(
        candidate_id=candidate.id,
        file_path=str(destination),
        original_filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        extracted_text=text,
        page_count=page_count,
        parsed_at=parsed_at,
        parse_version=PARSE_VERSION,
    )
    session.add(resume)
    await session.flush()

    logger.info(
        "resume uploaded: size_bytes=%d kind=%s page_count=%s duration_ms=%.0f",
        len(data),
        kind,
        page_count,
        (time.monotonic() - started) * 1000,
    )
    return ResumeUploadResponse(
        resume_id=resume.id,
        candidate_id=candidate.id,
        original_filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        extracted_text=text,
        page_count=page_count,
        parsed_at=parsed_at,
        parse_version=PARSE_VERSION,
    )
