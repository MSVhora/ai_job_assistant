"""Mapper for curious_coder/linkedin-jobs-scraper dataset items (run output, not README)."""

import re
from datetime import datetime

from pydantic import ValidationError

from app.adapters.job_sources.base import (
    ConnectorError,
    JobPostingData,
    RawJobPosting,
    clean_text,
    parse_datetime,
)
from app.models import JobType, RemoteType

_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

_EMPLOYMENT_TYPE_MAP: dict[str, JobType] = {
    "full_time": JobType.full_time,
    "part_time": JobType.part_time,
    "contract": JobType.contract,
    "internship": JobType.internship,
    "temporary": JobType.temporary,
}

_WORKPLACE_TYPE_MAP: dict[str, RemoteType] = {
    "remote": RemoteType.remote,
    "hybrid": RemoteType.hybrid,
    "on_site": RemoteType.on_site,
    "on-site": RemoteType.on_site,
}


def _salary_pair(value: object) -> tuple[float | None, float | None]:
    numbers: list[float] = []
    if isinstance(value, list):
        for entry in value:
            numbers.extend(_numbers(entry))
    else:
        numbers = _numbers(value)
    if not numbers:
        return None, None
    low, high = numbers[0], numbers[-1]
    return (low, high) if low <= high else (high, low)


def _numbers(value: object) -> list[float]:
    if not isinstance(value, str):
        return []
    return [float(match.replace(",", "")) for match in _NUM_RE.findall(value)]


def _job_type(value: object) -> JobType | None:
    if not isinstance(value, str):
        return None
    return _EMPLOYMENT_TYPE_MAP.get(value.strip().lower().replace(" ", "_").replace("-", "_"))


def _remote_type(payload: dict[str, object]) -> RemoteType | None:
    workplace = payload.get("workplaceTypes")
    if isinstance(workplace, str):
        mapped = _WORKPLACE_TYPE_MAP.get(workplace.strip().lower().replace(" ", "_"))
        if mapped is not None:
            return mapped
    return RemoteType.remote if payload.get("workRemoteAllowed") is True else None


def _posted_at(payload: dict[str, object]) -> datetime | None:
    parsed = parse_datetime(payload.get("postedAtTimestamp")) or parse_datetime(
        payload.get("postedAt")
    )
    return parsed


def normalize(raw: RawJobPosting) -> JobPostingData:
    payload = raw.payload
    title = clean_text(payload.get("title"))
    if title is None:
        raise ConnectorError("linkedin posting has no title")
    description = clean_text(payload.get("descriptionText")) or clean_text(
        payload.get("descriptionHtml")
    )
    salary_min, salary_max = _salary_pair(payload.get("salary") or payload.get("salaryInfo"))
    try:
        return JobPostingData(
            external_id=raw.external_id,
            title=title,
            company=clean_text(payload.get("companyName")),
            url=clean_text(payload.get("link")) or clean_text(payload.get("applyUrl")),
            location=clean_text(payload.get("location")),
            job_type=_job_type(payload.get("employmentType")),
            remote_type=_remote_type(payload),
            description=description,
            posted_at=_posted_at(payload),
            salary_min=salary_min,
            salary_max=salary_max,
            raw_payload=payload,
        )
    except ValidationError as exc:
        raise ConnectorError(f"linkedin posting failed normalization: {exc}") from exc
