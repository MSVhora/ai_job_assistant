import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from app.core.config import get_settings
from app.models import Achievement
from app.schemas.profile import ExperienceItem, StructuredProfile
from app.schemas.resume_document import Conflict, ConflictAction, ConflictKind, ConflictSeverity
from app.services.employer_mapping import Experience, experiences_of
from app.services.profile_derivation import resolve_date
from app.services.skill_canon import load_aliases

CONFIRMED_METRICS = ("evidence", "user")
YEAR_ONLY = re.compile(r"^\d{4}$")
WORDS = re.compile(r"[a-z][a-z0-9]{2,}")
QUANTITY = re.compile(
    r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>%|x\b|ms\b|seconds?\b|secs?\b|s\b|minutes?\b|mins?\b|hours?\b|hrs?\b|h\b"
    r"|days?\b|gb\b|mb\b|kb\b|k\b)",
    re.IGNORECASE,
)
UNIT_ALIASES = {
    "second": "s",
    "seconds": "s",
    "sec": "s",
    "secs": "s",
    "minute": "min",
    "minutes": "min",
    "mins": "min",
    "hour": "h",
    "hours": "h",
    "hr": "h",
    "hrs": "h",
    "day": "d",
    "days": "d",
}
STOPWORDS = frozenset(
    {"the", "and", "for", "with", "from", "that", "this", "into", "over", "per", "our", "was"}
)
MIN_SHARED_WORDS = 2


@dataclass(frozen=True)
class GitHubIdentity:
    name: str | None = None
    location: str | None = None
    emails: tuple[str, ...] = field(default_factory=tuple)


def conflict_key(kind: str, refs: dict[str, str]) -> str:
    payload = json.dumps([kind, sorted(refs.items())], separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _conflict(
    kind: ConflictKind,
    severity: ConflictSeverity,
    message: str,
    refs: dict[str, str],
    *,
    can_edit_profile: bool = True,
) -> Conflict:
    actions: list[ConflictAction] = (
        ["edit_profile", "keep_as_is"] if can_edit_profile else ["keep_as_is"]
    )
    return Conflict(
        key=conflict_key(kind, refs),
        kind=kind,
        severity=severity,
        message=message,
        refs=refs,
        suggested_actions=actions,
    )


def _short(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]


def _skill_key(skill: str) -> str:
    cleaned = skill.strip().lower()
    return load_aliases().get(cleaned, cleaned).lower()


def _month(value: date) -> tuple[int, int]:
    return (value.year, value.month)


def _window(job: ExperienceItem) -> tuple[date, date] | None:
    """Employment window; month-level compare is applied by callers, year-only ends widen."""
    start = resolve_date(job.start_date)
    if start is None:
        return None
    end = resolve_date(job.end_date)
    if job.end_date and YEAR_ONLY.match(job.end_date.strip()) and end is not None:
        end = date(end.year, 12, 31)
    if end is None:
        if not job.is_current:
            return None
        end = resolve_date("Present")
    if end is None:
        return None
    return start, max(start, end)


def _employer_job(profile: StructuredProfile, ref: dict[str, object]) -> ExperienceItem | None:
    for job in profile.experience:
        if job.company == ref.get("company") and job.start_date == ref.get("start_date"):
            return job
    return None


def _is_confirmed_employer(ref: dict[str, object] | None) -> bool:
    return ref is not None and ref.get("kind") != "personal" and ref.get("source") != "suggested"


def detect_date_outside_employment(
    profile: StructuredProfile, achievements: Iterable[Achievement]
) -> list[Conflict]:
    found: list[Conflict] = []
    for achievement in achievements:
        ref = achievement.employer_ref
        if not _is_confirmed_employer(ref) or ref is None or achievement.time_start is None:
            continue
        job = _employer_job(profile, ref)
        window = _window(job) if job else None
        if window is None:
            continue
        starts = achievement.time_start
        ends = achievement.time_end or starts
        if _month(ends) < _month(window[0]) or _month(starts) > _month(window[1]):
            found.append(
                _conflict(
                    "date_outside_employment",
                    "warning",
                    f"'{achievement.title}' is dated outside your time at {ref.get('company')}.",
                    {"achievement_id": str(achievement.id)},
                )
            )
    return found


def detect_employer_not_in_profile(
    profile: StructuredProfile, achievements: Iterable[Achievement]
) -> list[Conflict]:
    missing: dict[tuple[str, str], int] = {}
    for achievement in achievements:
        ref = achievement.employer_ref
        if not _is_confirmed_employer(ref) or ref is None or _employer_job(profile, ref):
            continue
        key = (str(ref.get("company") or ""), str(ref.get("start_date") or ""))
        missing[key] = missing.get(key, 0) + 1
    return [
        _conflict(
            "employer_not_in_profile",
            "warning",
            f"{count} achievement(s) are mapped to {company}, which is not in your profile.",
            {"company": company, "start_date": start_date},
        )
        for (company, start_date), count in missing.items()
    ]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def _differs(github: str | None, profile_value: str | None) -> bool:
    if not github or not profile_value:
        return False
    return not (_tokens(github) & _tokens(profile_value))


def detect_identity_mismatch(
    profile: StructuredProfile, identity: GitHubIdentity | None
) -> list[Conflict]:
    if identity is None:
        return []
    contact = profile.contact
    findings: list[tuple[str, str]] = []
    if _differs(identity.name, contact.full_name):
        findings.append(("name", "GitHub name differs from your profile name."))
    if _differs(identity.location, contact.location):
        findings.append(("location", "GitHub location differs from your profile location."))
    if (
        contact.email
        and identity.emails
        and contact.email.casefold() not in {email.casefold() for email in identity.emails}
    ):
        findings.append(("email", "GitHub's public email differs from your profile email."))
    return [
        _conflict("identity_mismatch", "warning", message, {"field": field_name})
        for field_name, message in findings
    ]


def _profile_skills(profile: StructuredProfile) -> dict[str, str]:
    return {_skill_key(skill): skill for skill in profile.skills if skill.strip()}


def _evidence_skills(achievements: list[Achievement]) -> dict[str, str]:
    skills: dict[str, str] = {}
    for achievement in achievements:
        for skill in achievement.skills:
            if skill.strip():
                skills.setdefault(_skill_key(skill), skill)
    return skills


def detect_skill_conflicts(
    profile: StructuredProfile, achievements: list[Achievement]
) -> list[Conflict]:
    if not achievements:
        return []
    own = _profile_skills(profile)
    backed = _evidence_skills(achievements)
    missing = [
        _conflict(
            "skill_missing_in_profile",
            "info",
            f"Your evidence shows {name}, which your profile does not list.",
            {"skill": key},
        )
        for key, name in backed.items()
        if key not in own
    ]
    unbacked = [
        _conflict(
            "skill_without_evidence",
            "info",
            f"No approved evidence yet for {name}; it stays on your resume.",
            {"skill": key},
            can_edit_profile=False,
        )
        for key, name in own.items()
        if key not in backed
    ]
    return missing + unbacked


def _quantities(text: str) -> list[tuple[Decimal, str]]:
    found: list[tuple[Decimal, str]] = []
    for match in QUANTITY.finditer(text):
        unit = match.group("unit").lower()
        try:
            value = Decimal(match.group("value").replace(",", ""))
        except InvalidOperation:
            continue
        found.append((value, UNIT_ALIASES.get(unit, unit)))
    return found


def _topic(text: str) -> set[str]:
    return {word for word in WORDS.findall(text.casefold()) if word not in STOPWORDS}


def _contradicts(metric: str, bullet: str) -> bool:
    if len(_topic(metric) & _topic(bullet)) < MIN_SHARED_WORDS:
        return False
    bullet_values = _quantities(bullet)
    for value, unit in _quantities(metric):
        same_unit = [other for other, other_unit in bullet_values if other_unit == unit]
        if same_unit and value not in same_unit:
            return True
    return False


def _scoped_bullets(profile: StructuredProfile, achievement: Achievement) -> list[str]:
    ref = achievement.employer_ref
    if _is_confirmed_employer(ref) and ref is not None:
        job = _employer_job(profile, ref)
        if job is not None:
            return list(job.bullets)
    key = (achievement.project_key or "").casefold()
    short = key.rsplit("/", 1)[-1]
    for project in profile.projects:
        if key and project.name.casefold() in {key, short}:
            return list(project.bullets)
    return []


def detect_metric_contradiction(
    profile: StructuredProfile, achievements: Iterable[Achievement]
) -> list[Conflict]:
    found: list[Conflict] = []
    for achievement in achievements:
        bullets = _scoped_bullets(profile, achievement)
        metrics = [
            str(metric.get("text") or "")
            for metric in achievement.metrics
            if metric.get("verified") in CONFIRMED_METRICS
        ]
        for metric in metrics:
            found.extend(
                _conflict(
                    "metric_contradiction",
                    "error",
                    f"A profile bullet states a different figure than the confirmed "
                    f"metric '{metric}'.",
                    {
                        "achievement_id": str(achievement.id),
                        "metric": _short(metric),
                        "bullet": _short(bullet),
                    },
                )
                for bullet in bullets
                if _contradicts(metric, bullet)
            )
    return found


def _overlap_days(first: Experience, second: Experience) -> int:
    if first.start is None or second.start is None:
        return 0
    first_end = first.end or first.start
    second_end = second.end or second.start
    return (min(first_end, second_end) - max(first.start, second.start)).days + 1


def detect_overlapping_roles(profile: StructuredProfile) -> list[Conflict]:
    minimum = get_settings().resume_overlap_min_days
    roles = experiences_of(profile)
    found: list[Conflict] = []
    for index, first in enumerate(roles):
        for second in roles[index + 1 :]:
            if first.start is None or second.start is None:
                continue
            days = _overlap_days(first, second)
            if days < minimum:
                continue
            ordered = sorted(
                [(first.company, first.start_raw or ""), (second.company, second.start_raw or "")]
            )
            found.append(
                _conflict(
                    "overlapping_roles",
                    "info",
                    f"{first.company} and {second.company} overlap by {days} days; the higher-"
                    "priority role is kept when a resume is written.",
                    {
                        "role_a": f"{ordered[0][0]}|{ordered[0][1]}",
                        "role_b": f"{ordered[1][0]}|{ordered[1][1]}",
                    },
                    can_edit_profile=False,
                )
            )
    return found


def reconcile(
    profile: StructuredProfile,
    achievements: list[Achievement],
    github_identity: GitHubIdentity | None = None,
) -> list[Conflict]:
    """Every conflict between the profile and approved evidence; nothing is changed or resolved."""
    return [
        *detect_date_outside_employment(profile, achievements),
        *detect_employer_not_in_profile(profile, achievements),
        *detect_identity_mismatch(profile, github_identity),
        *detect_skill_conflicts(profile, achievements),
        *detect_metric_contradiction(profile, achievements),
        *detect_overlapping_roles(profile),
    ]
