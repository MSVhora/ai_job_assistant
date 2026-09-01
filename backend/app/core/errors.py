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


class NoJobSourcesConfiguredError(DomainError):
    status_code = 400
    default_detail = "no job sources are configured for the selected search"


class UnknownJobSourceError(DomainError):
    status_code = 400
    default_detail = "unknown job source"


class JobSearchNotFoundError(DomainError):
    status_code = 404
    default_detail = "job search not found"


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
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def request_validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    parts: list[str] = []
    for error in exc.errors()[:20]:
        location = ".".join(str(item) for item in error["loc"] if item != "body")
        message = str(error["msg"])
        parts.append(f"{location}: {message}" if location else message)
    detail = "; ".join(parts) if parts else "invalid request"
    return JSONResponse(status_code=422, content={"detail": detail})
