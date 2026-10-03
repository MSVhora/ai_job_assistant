import json
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import TOTAL_COUNT_HEADER, Pagination
from app.deps import get_db, pagination
from app.schemas.resume_document import (
    ConflictsResponse,
    ResolveConflictRequest,
    ResumeContent,
    ResumeDocumentCreate,
    ResumeDocumentResponse,
    ResumeDocumentSummary,
    ResumeDocumentUpdate,
)
from app.services import resume_documents, resume_export

router = APIRouter(prefix="/api", tags=["resume-documents"])

ExportFormat = Literal["text", "markdown", "json_resume"]
EXPORT_MEDIA_TYPES = {
    "text": "text/plain; charset=utf-8",
    "markdown": "text/markdown; charset=utf-8",
    "json_resume": "application/json",
}


@router.post("/resume-documents", response_model=ResumeDocumentResponse, status_code=201)
async def create_resume_document(
    payload: ResumeDocumentCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResumeDocumentResponse:
    return await resume_documents.create_document(session, payload)


@router.get("/resume-documents", response_model=list[ResumeDocumentSummary])
async def list_resume_documents(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[Pagination, Depends(pagination())],
    profile_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ResumeDocumentSummary]:
    total = await resume_documents.count_documents(session, profile_id)
    response.headers[TOTAL_COUNT_HEADER] = str(total)
    return await resume_documents.list_documents(session, profile_id, page)


@router.get("/resume-documents/{document_id}", response_model=ResumeDocumentResponse)
async def get_resume_document(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResumeDocumentResponse:
    return await resume_documents.get_document(session, document_id)


@router.patch("/resume-documents/{document_id}", response_model=ResumeDocumentResponse)
async def update_resume_document(
    document_id: uuid.UUID,
    payload: ResumeDocumentUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResumeDocumentResponse:
    return await resume_documents.update_document(session, document_id, payload)


@router.delete("/resume-documents/{document_id}", status_code=204)
async def delete_resume_document(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await resume_documents.delete_document(session, document_id)
    return Response(status_code=204)


@router.post(
    "/resume-documents/{document_id}/resync-identity", response_model=ResumeDocumentResponse
)
async def resync_resume_identity(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResumeDocumentResponse:
    return await resume_documents.resync_identity(session, document_id)


@router.get("/resume-documents/{document_id}/conflicts", response_model=ConflictsResponse)
async def get_resume_conflicts(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConflictsResponse:
    return await resume_documents.get_conflicts(session, document_id)


@router.post(
    "/resume-documents/{document_id}/conflicts/{key}/resolve", response_model=ConflictsResponse
)
async def resolve_resume_conflict(
    document_id: uuid.UUID,
    key: str,
    payload: ResolveConflictRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConflictsResponse:
    return await resume_documents.resolve_conflict(session, document_id, key, payload)


@router.get(
    "/resume-documents/{document_id}/export",
    response_class=Response,
    responses={
        200: {
            "description": "Clean export: no private marks, badges or provenance.",
            "content": {media_type: {} for media_type in EXPORT_MEDIA_TYPES.values()},
        }
    },
)
async def export_resume_document(
    document_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    export_format: Annotated[ExportFormat, Query(alias="format")] = "text",
) -> Response:
    document = await resume_documents.get_document(session, document_id)
    content: ResumeContent = document.content
    if export_format == "markdown":
        body = resume_export.to_markdown(content)
    elif export_format == "json_resume":
        body = json.dumps(resume_export.to_json_resume(content), indent=2, ensure_ascii=False)
    else:
        body = resume_export.to_plain_text(content)
    return Response(content=body, media_type=EXPORT_MEDIA_TYPES[export_format])
