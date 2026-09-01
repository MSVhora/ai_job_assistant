import json
import logging
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, is_llm_configured, parse_structured
from app.core.errors import LLMGapFillError, LLMNotConfiguredError, ProfileNotFoundError
from app.models import Profile, ProfileRevision, RevisionSource
from app.schemas.gap_fill import (
    GapFillAppliedField,
    GapFillField,
    GapFillMessage,
    GapFillRequest,
    GapFillResponse,
    RevisionSummary,
)
from app.schemas.profile import Preferences, RemotePreference, SeniorityLevel, StructuredProfile
from app.services.profile_service import _next_timestamp, diff_profiles

logger = logging.getLogger(__name__)

GAP_FILL_SYSTEM = (
    "You are the gap-fill assistant inside a job-search app. You ask the user short, friendly "
    "questions to complete the missing fields listed in the prompt. Rules: ask about at most "
    "two fields per reply; never ask about a field that is not listed as missing; never invent "
    "or assume answers; extract into `answers` only what the user explicitly stated; if a "
    "reply is ambiguous, ask a clarifying question instead of guessing; keep replies under 80 "
    "words, plain text, no lists or markdown."
)

_NOTHING_MISSING_REPLY = (
    "Your profile already covers everything I would ask about - you are all set."
)

_MAX_PROMPT_CHARS = 24_000

_FIELD_LABELS: dict[str, str] = {
    "contact.location": "Current location",
    "contact.country": "Country",
    "preferences.target_location": "Target location",
    "preferences.remote_preference": "Remote preference",
    "preferences.salary_band": "Salary band",
    "preferences.seniority": "Target seniority",
    "preferences.work_authorization": "Work authorization",
}

_FIELD_DESCRIPTIONS: dict[str, str] = {
    "contact.location": "the city/region the user works from",
    "contact.country": (
        "the ISO 3166-1 alpha-2 country code (lowercase, e.g. 'in', 'de', 'us') of the "
        "country the user will work from"
    ),
    "preferences.target_location": (
        "where they want their next job to be (city, country, or 'remote anywhere')"
    ),
    "preferences.remote_preference": "one of: remote, hybrid, onsite, flexible",
    "preferences.salary_band": (
        "their target salary range - set salary_min and/or salary_max as plain numbers "
        "('80k' -> 80000), plus currency as a 3-letter code if they mention one"
    ),
    "preferences.seniority": (
        "one of: intern, junior, mid, senior, staff, lead, principal, manager, director, executive"
    ),
    "preferences.work_authorization": (
        "their work-authorization situation in the target location, in their own words "
        "(e.g. 'EU citizen', 'H-1B, needs sponsorship')"
    ),
}

_APPLIED_LABELS: dict[str, str] = {
    **_FIELD_LABELS,
    "preferences.salary_min": "Salary min",
    "preferences.salary_max": "Salary max",
    "preferences.currency": "Currency",
}


class GapFillAnswers(BaseModel):
    contact_location: str | None = Field(default=None, max_length=200)
    contact_country: str | None = Field(default=None, max_length=2, pattern=r"^[A-Za-z]{2}$")
    target_location: str | None = Field(default=None, max_length=200)
    remote_preference: RemotePreference | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    seniority: SeniorityLevel | None = None
    work_authorization: str | None = Field(default=None, max_length=200)

    @field_validator(
        "contact_location", "contact_country", "target_location", "work_authorization", mode="after"
    )
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("contact_country", mode="after")
    @classmethod
    def _lowercase_country(cls, value: str | None) -> str | None:
        return value.lower() if value else value


class GapFillTurn(BaseModel):
    answers: GapFillAnswers
    reply: str = Field(min_length=1, max_length=2000)


def _blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def _field(key: str) -> GapFillField:
    return GapFillField(key=key, label=_FIELD_LABELS[key])


def missing_fields(profile: StructuredProfile) -> list[GapFillField]:
    prefs = profile.preferences
    missing: list[GapFillField] = []
    if _blank(profile.contact.location):
        missing.append(_field("contact.location"))
    if _blank(profile.contact.country):
        missing.append(_field("contact.country"))
    if prefs is None or _blank(prefs.target_location):
        missing.append(_field("preferences.target_location"))
    if prefs is None or prefs.remote_preference is None:
        missing.append(_field("preferences.remote_preference"))
    if prefs is None or (prefs.salary_min is None and prefs.salary_max is None):
        missing.append(_field("preferences.salary_band"))
    if prefs is None or prefs.seniority is None:
        missing.append(_field("preferences.seniority"))
    if prefs is None or _blank(prefs.work_authorization):
        missing.append(_field("preferences.work_authorization"))
    return missing


def _context_profile(profile: StructuredProfile) -> dict[str, Any]:
    context: dict[str, Any] = {
        "contact.location": profile.contact.location,
        "contact.country": profile.contact.country,
        "headline": profile.headline,
    }
    if profile.preferences is not None:
        context["preferences"] = profile.preferences.model_dump(mode="json")
    return context


def _build_prompt(
    profile: StructuredProfile, missing: list[GapFillField], messages: list[GapFillMessage]
) -> str:
    lines = [
        "Known profile data (never ask about anything already present here):",
        json.dumps(_context_profile(profile)),
        "",
        "Missing fields you may ask about (ask ONLY about these):",
    ]
    lines.extend(
        f"- {field.key} ({field.label}): {_FIELD_DESCRIPTIONS[field.key]}" for field in missing
    )
    lines.extend(["", "Conversation so far:"])
    if messages:
        lines.extend(f"{message.role}: {message.content}" for message in messages)
    else:
        lines.append("(no messages yet - open the conversation)")
    lines.extend(
        [
            "",
            "Extract any answers the user gave for the missing fields into `answers` (null for "
            "anything not clearly answered). Then write `reply`: briefly acknowledge any new "
            "information and ask about the next missing field; if every missing field now has "
            "an answer, confirm and wrap up.",
        ]
    )
    return "\n".join(lines)[:_MAX_PROMPT_CHARS]


def _display(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _apply_answers(
    profile: StructuredProfile, answers: GapFillAnswers, missing_keys: set[str]
) -> list[GapFillAppliedField]:
    salary_min = answers.salary_min
    salary_max = answers.salary_max
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        logger.warning(
            "gap_fill dropped inverted salary band min=%s max=%s", salary_min, salary_max
        )
        salary_min = None
        salary_max = None

    prefs = (
        _ensure_preferences(profile)
        if {
            "preferences.target_location",
            "preferences.remote_preference",
            "preferences.salary_band",
            "preferences.seniority",
            "preferences.work_authorization",
        }
        & missing_keys
        else profile.preferences
    )

    applied: list[GapFillAppliedField] = []

    def record(field: str, value: object) -> None:
        applied.append(
            GapFillAppliedField(field=field, label=_APPLIED_LABELS[field], value=_display(value))
        )

    if "contact.location" in missing_keys and answers.contact_location is not None:
        profile.contact.location = answers.contact_location
        record("contact.location", answers.contact_location)

    if "contact.country" in missing_keys and answers.contact_country is not None:
        profile.contact.country = answers.contact_country
        record("contact.country", answers.contact_country)

    if prefs is None:
        return applied

    if "preferences.target_location" in missing_keys and answers.target_location is not None:
        prefs.target_location = answers.target_location
        record("preferences.target_location", answers.target_location)
    if "preferences.remote_preference" in missing_keys and answers.remote_preference is not None:
        prefs.remote_preference = answers.remote_preference
        record("preferences.remote_preference", answers.remote_preference)
    if "preferences.salary_band" in missing_keys:
        if salary_min is not None and prefs.salary_min is None:
            prefs.salary_min = salary_min
            record("preferences.salary_min", salary_min)
        if salary_max is not None and prefs.salary_max is None:
            prefs.salary_max = salary_max
            record("preferences.salary_max", salary_max)
        if answers.currency is not None and _blank(prefs.currency):
            prefs.currency = answers.currency.upper()
            record("preferences.currency", answers.currency.upper())
    if "preferences.seniority" in missing_keys and answers.seniority is not None:
        prefs.seniority = answers.seniority
        record("preferences.seniority", answers.seniority)
    if "preferences.work_authorization" in missing_keys and answers.work_authorization is not None:
        prefs.work_authorization = answers.work_authorization
        record("preferences.work_authorization", answers.work_authorization)

    return applied


def _ensure_preferences(profile: StructuredProfile) -> Preferences:
    if profile.preferences is None:
        profile.preferences = Preferences()
    return profile.preferences


async def _llm_turn(
    profile: StructuredProfile, missing: list[GapFillField], messages: list[GapFillMessage]
) -> GapFillTurn:
    prompt = _build_prompt(profile, missing, messages)
    try:
        result = await parse_structured(prompt, schema=GapFillTurn, system=GAP_FILL_SYSTEM)
    except LLMError as exc:
        logger.warning("gap_fill llm turn failed: %s", exc)
        raise LLMGapFillError(str(exc)) from exc
    return result.data


async def run_gap_fill_turn(
    session: AsyncSession, profile_id: uuid.UUID, payload: GapFillRequest
) -> GapFillResponse:
    started = time.monotonic()
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    current = StructuredProfile.model_validate(profile.structured_profile)

    missing = missing_fields(current)
    if not missing:
        return GapFillResponse(
            reply=_NOTHING_MISSING_REPLY,
            status="complete",
            missing_fields=[],
            applied_fields=[],
            structured_profile=current,
            revision=None,
        )

    if not is_llm_configured():
        raise LLMNotConfiguredError()

    turn = await _llm_turn(current, missing, payload.messages)
    updated = current.model_copy(deep=True)
    applied = _apply_answers(updated, turn.answers, {field.key for field in missing})

    revision: ProfileRevision | None = None
    if applied:
        profile.structured_profile = updated.model_dump(mode="json")
        revision = ProfileRevision(
            profile_id=profile.id,
            source=RevisionSource.gap_fill,
            diff=diff_profiles(current.model_dump(mode="json"), updated.model_dump(mode="json")),
            created_at=_next_timestamp(None),
        )
        session.add(revision)
        await session.flush()

    remaining = missing_fields(updated)
    logger.info(
        "profile.gap_fill profile_id=%s duration_ms=%.0f applied=%d "
        "missing_before=%d missing_after=%d",
        profile_id,
        (time.monotonic() - started) * 1000,
        len(applied),
        len(missing),
        len(remaining),
    )
    return GapFillResponse(
        reply=turn.reply,
        status="complete" if not remaining else "in_progress",
        missing_fields=remaining,
        applied_fields=applied,
        structured_profile=updated,
        revision=None
        if revision is None
        else RevisionSummary(
            id=revision.id, source=revision.source.value, created_at=revision.created_at
        ),
    )
