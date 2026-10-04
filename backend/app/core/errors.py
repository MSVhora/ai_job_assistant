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


class DuplicateSyncError(DomainError):
    """A pending/running evidence sync for the same source already exists (#50)."""

    status_code = 409
    default_detail = "an evidence sync for this source is already active"

    def __init__(self, detail: str | None = None, active_sync_id: UUID | None = None) -> None:
        super().__init__(detail)
        self.active_sync_id = active_sync_id


class EvidenceSourceNotConfiguredError(DomainError):
    status_code = 400
    default_detail = "GITHUB_TOKEN is not configured - add a read-only token to backend/.env"


class NoEnabledScopesError(DomainError):
    status_code = 400
    default_detail = "enable at least one repository before syncing"


class DisclosureRequiredError(DomainError):
    status_code = 409
    default_detail = (
        "enabling a private repository sends its text to your LLM provider - "
        "acknowledge the disclosure first"
    )


class EvidenceScopeNotFoundError(DomainError):
    status_code = 404
    default_detail = "repository not found - list the repositories first"


class SyncRunNotFoundError(DomainError):
    status_code = 404
    default_detail = "evidence sync run not found"


class EvidenceSourceUnavailableError(DomainError):
    status_code = 502
    default_detail = "GitHub request failed - check the token and retry shortly"


class AchievementNotFoundError(DomainError):
    status_code = 404
    default_detail = "achievement not found"


class AchievementConflictError(DomainError):
    """The requested review change is not allowed in the achievement's current state (409)."""

    status_code = 409
    default_detail = "that change is not allowed for this achievement right now"


class InvalidAchievementInputError(DomainError):
    status_code = 400
    default_detail = "the achievement change is not valid"


class ResumeDocumentNotFoundError(DomainError):
    status_code = 404
    default_detail = "resume document not found"


class ConflictNotFoundError(DomainError):
    status_code = 404
    default_detail = "conflict not found"


class InvalidResumeDocumentError(DomainError):
    status_code = 400
    default_detail = "the resume document change is not valid"


class ResumeBlockNotFoundError(DomainError):
    status_code = 404
    default_detail = "resume section not found"


class BulletNotFoundError(DomainError):
    status_code = 404
    default_detail = "bullet not found"


class CommentNotFoundError(DomainError):
    status_code = 404
    default_detail = "comment not found"


class InvalidCommentTargetError(DomainError):
    status_code = 422
    default_detail = "the comment must target a section or bullet of this document"


class CannotFitError(DomainError):
    status_code = 422
    default_detail = (
        "this resume cannot fit the chosen page count at the smallest type size; "
        "choose more pages or shorten the contact, education or skills sections"
    )


class ResumeRenderError(DomainError):
    status_code = 500
    default_detail = "the resume could not be rendered"


class InvalidEmployerError(DomainError):
    status_code = 400
    default_detail = "employer must be one of your profile's experience entries or personal"


class DuplicateExtractionError(DomainError):
    """A pending/running achievement extraction for this candidate already exists (#52)."""

    status_code = 409
    default_detail = "an achievement extraction is already active"

    def __init__(self, detail: str | None = None, active_run_id: UUID | None = None) -> None:
        super().__init__(detail)
        self.active_run_id = active_run_id


class EstimateMismatchError(DomainError):
    status_code = 409
    default_detail = "the evidence or settings changed since the estimate - estimate again"


class NothingToExtractError(DomainError):
    status_code = 400
    default_detail = "there is no new evidence to extract"


class ExtractionRunNotFoundError(DomainError):
    status_code = 404
    default_detail = "extraction run not found"


class EvidenceItemNotFoundError(DomainError):
    status_code = 404
    default_detail = "evidence item not found"


class DuplicateEvidenceError(DomainError):
    status_code = 409
    default_detail = "this evidence already exists"


class InvalidEvidenceInputError(DomainError):
    status_code = 400
    default_detail = "the evidence could not be created from this input"


class JobPostingNotFoundError(DomainError):
    status_code = 404
    default_detail = "job posting not found"


class JobSourceNotFoundError(DomainError):
    status_code = 404
    default_detail = "job source not found"


class MatchNotFoundError(DomainError):
    status_code = 404
    default_detail = "match not found"


class NoTunableSignalsError(DomainError):
    """Tune-my-queries has no engagement signals to learn from (#39)."""

    status_code = 409
    default_detail = "no engagement signals yet — open, save, or dismiss some matches first"


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
    if isinstance(exc, DuplicateSyncError) and exc.active_sync_id is not None:
        body["active_sync_id"] = str(exc.active_sync_id)
    if isinstance(exc, DuplicateExtractionError) and exc.active_run_id is not None:
        body["active_run_id"] = str(exc.active_run_id)
    return JSONResponse(status_code=exc.status_code, content=body)


async def request_validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    parts: list[str] = []
    for error in exc.errors()[:20]:
        location = ".".join(str(item) for item in error["loc"] if item != "body")
        message = str(error["msg"])
        parts.append(f"{location}: {message}" if location else message)
    detail = "; ".join(parts) if parts else "invalid request"
    return JSONResponse(status_code=422, content={"detail": detail})
