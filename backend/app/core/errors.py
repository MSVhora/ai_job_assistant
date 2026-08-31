from fastapi import Request
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


async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
