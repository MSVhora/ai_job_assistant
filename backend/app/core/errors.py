from uuid import UUID

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code: int = 400
    default_detail: str = "invalid request"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.default_detail)
        self.detail = detail or self.default_detail


class UnsupportedFileTypeError(DomainError):
    status_code = 415
    default_detail = "unsupported file type: only PDF and DOCX resumes are accepted"


class FileTooLargeError(DomainError):
    status_code = 413
    default_detail = "file too large"


class TextExtractionError(DomainError):
    status_code = 422
    default_detail = "no readable text found in file"


class ResumeNotFoundError(DomainError):
    status_code = 404
    default_detail = "resume not found"


class ProfileNotFoundError(DomainError):
    status_code = 404
    default_detail = "profile not found"


class ProfileNotEmbeddedError(DomainError):
    status_code = 409
    default_detail = "profile has no embedding; save the profile once the embedding provider works"


class ResumeDraftUnavailableError(DomainError):
    status_code = 409
    default_detail = "resume has no extracted draft profile"


class ResumeTextUnavailableError(DomainError):
    status_code = 409
    default_detail = "resume has no extracted text to parse"


class LLMNotConfiguredError(DomainError):
    status_code = 503
    default_detail = "LLM provider is not configured"


class LLMExtractionError(DomainError):
    status_code = 502
    default_detail = "profile extraction failed"


class LLMGapFillError(DomainError):
    status_code = 502
    default_detail = "gap-fill turn failed"


class LLMQueryGenerationError(DomainError):
    status_code = 502
    default_detail = "search query generation failed"


class MissingSearchQueryError(DomainError):
    status_code = 400
    default_detail = "no search query provided for a selected source"


class MissingSearchCountryError(DomainError):
    status_code = 400
    default_detail = "no country provided by the request or the profile"


class MissingProfileIdError(DomainError):
    status_code = 400
    default_detail = "profile_id is required"


class NoJobSourcesConfiguredError(DomainError):
    status_code = 400
    default_detail = "no job sources are configured for the selected search"


class UnknownJobSourceError(DomainError):
    status_code = 400
    default_detail = "unknown job source"


class InvalidSourceFilterError(DomainError):
    status_code = 400
    default_detail = "invalid filter option for the selected source"


class JobSearchNotFoundError(DomainError):
    status_code = 404
    default_detail = "job search not found"


class DuplicateRunError(DomainError):
    """A non-terminal run for the same (profile, source) already exists (#36)."""

    status_code = 409
    default_detail = "a run for this profile and source is already active"

    def __init__(self, detail: str | None = None, active_search_id: UUID | None = None) -> None:
        super().__init__(detail)
        self.active_search_id = active_search_id


class JobPostingNotFoundError(DomainError):
    status_code = 404
    default_detail = "job posting not found"


class JobSourceNotFoundError(DomainError):
    status_code = 404
    default_detail = "job source not found"


class DisclosureNotAcknowledgedError(DomainError):
    status_code = 409
    default_detail = "disclosure must be acknowledged before enabling this source"


class JobSourceNotEnabledError(DomainError):
    status_code = 409
    default_detail = "job source is not enabled"


async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    body: dict[str, object] = {"detail": exc.detail}
    if isinstance(exc, DuplicateRunError) and exc.active_search_id is not None:
        body["active_search_id"] = str(exc.active_search_id)
    return JSONResponse(status_code=exc.status_code, content=body)


async def request_validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    parts: list[str] = []
    for error in exc.errors()[:20]:
        location = ".".join(str(item) for item in error["loc"] if item != "body")
        message = str(error["msg"])
        parts.append(f"{location}: {message}" if location else message)
    detail = "; ".join(parts) if parts else "invalid request"
    return JSONResponse(status_code=422, content={"detail": detail})
