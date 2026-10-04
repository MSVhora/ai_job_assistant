import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Candidate, Profile
from app.schemas.profile import StructuredProfile
from app.services.company_names import Merges, normalize_company
from app.services.profile_derivation import resolve_date

NON_REPO_PREFIXES = ("resume:", "note:", "link:")
PERSONAL_KIND = "personal"
SPAN_OVERLAP_SHARE = 0.5


@dataclass(frozen=True)
class Experience:
    company: str
    start_raw: str | None
    start: date | None
    end: date | None
    is_current: bool = False


@dataclass(frozen=True)
class EmployerGroup:
    """One employer: every experience entry whose company names are the same company."""

    key: str
    name: str
    entries: tuple[Experience, ...]
    aliases: tuple[str, ...]
    merged_from: tuple[str, ...]

    @property
    def start(self) -> date | None:
        starts = [entry.start for entry in self.entries if entry.start is not None]
        return min(starts) if starts else None

    @property
    def end(self) -> date | None:
        ends = [day for entry in self.entries if (day := entry.end or entry.start) is not None]
        return max(ends) if ends else None

    @property
    def current(self) -> bool:
        return any(entry.is_current for entry in self.entries)


def _group(key: str, entries: list[Experience], merges: Merges) -> EmployerGroup:
    names = Counter(entry.company for entry in entries)
    ranked = sorted(names, key=lambda name: (-names[name], -len(name), name))
    name = merges.canonical(key) or ranked[0]
    members = merges.members(key)
    aliases = tuple(dict.fromkeys([name, *ranked, *members]))
    ordered = sorted(
        entries, key=lambda entry: (entry.start is None, entry.start or date.max, entry.start_raw)
    )
    return EmployerGroup(
        key=key,
        name=name,
        entries=tuple(ordered),
        aliases=aliases,
        merged_from=tuple(member for member in members if member != name),
    )


def group_experiences(
    experiences: list[Experience], merges: Merges | None = None
) -> list[EmployerGroup]:
    """Entries grouped by company (and confirmed merges), most recent employer first."""
    merges = merges or Merges()
    buckets: dict[str, list[Experience]] = {}
    for experience in experiences:
        buckets.setdefault(merges.key(experience.company), []).append(experience)
    groups = [_group(key, entries, merges) for key, entries in buckets.items()]
    groups.sort(key=lambda g: (-(g.end.toordinal() if g.end else 0), g.name.casefold()))
    return groups


@dataclass(frozen=True)
class ProfileFacts:
    skills: list[str] = field(default_factory=list[str])
    experiences: list[Experience] = field(default_factory=list[Experience])
    merges: Merges = field(default_factory=Merges)

    @property
    def groups(self) -> list[EmployerGroup]:
        return group_experiences(self.experiences, self.merges)


def experiences_of(structured: StructuredProfile) -> list[Experience]:
    """One profile's employment entries with their parsed windows (company-less rows skipped)."""
    result: list[Experience] = []
    for job in structured.experience:
        if not job.company:
            continue
        start = resolve_date(job.start_date)
        end = resolve_date(job.end_date)
        if end is None and job.is_current:
            end = date.today()  # noqa: DTZ011
        result.append(
            Experience(
                job.company,
                job.start_date,
                start,
                max(start, end) if start and end else end,
                is_current=job.is_current,
            )
        )
    return result


async def load_profile_facts(session: AsyncSession, candidate_id: uuid.UUID) -> ProfileFacts:
    """Skills and employment entries across all of the candidate's profiles (de-duplicated)."""
    skills: list[str] = []
    experiences: dict[tuple[str, str | None], Experience] = {}
    profiles = (
        (await session.execute(select(Profile).where(Profile.candidate_id == candidate_id)))
        .scalars()
        .all()
    )
    for profile in profiles:
        try:
            structured = StructuredProfile.model_validate(profile.structured_profile)
        except ValidationError:
            continue
        skills.extend(structured.skills)
        for experience in experiences_of(structured):
            experiences.setdefault((experience.company, experience.start_raw), experience)
    candidate = await session.get(Candidate, candidate_id)
    merges = Merges.from_stored(candidate.employer_merges if candidate else None)
    return ProfileFacts(skills=skills, experiences=list(experiences.values()), merges=merges)


def _overlap_days(start: date, end: date, experience: Experience) -> int:
    if experience.start is None:
        return 0
    experience_end = experience.end or experience.start
    return (min(end, experience_end) - max(start, experience.start)).days + 1


def _group_overlap(start: date, end: date, group: EmployerGroup) -> int:
    """Days of [start, end] spent at the employer, over all its stints (never above the span)."""
    total = sum(max(0, _overlap_days(start, end, entry)) for entry in group.entries)
    return min(total, (end - start).days + 1)


def _suggestion(group: EmployerGroup) -> dict[str, object]:
    return {"company": group.name, "start_date": None, "source": "suggested"}


def suggest_employer(
    project_key: str | None, start: date | None, end: date | None, groups: list[EmployerGroup]
) -> dict[str, object] | None:
    """Best date-overlap employer for a repository chunk (a suggestion until the user confirms)."""
    if project_key is None or project_key.startswith(NON_REPO_PREFIXES) or start is None:
        return None
    span_end = end or start
    best: tuple[int, EmployerGroup] | None = None
    for group in groups:
        overlap = _group_overlap(start, span_end, group)
        if overlap > 0 and (best is None or overlap > best[0]):
            best = (overlap, group)
    return None if best is None else _suggestion(best[1])


def suggest_for_scope(
    start: date | None, end: date | None, groups: list[EmployerGroup]
) -> dict[str, object] | None:
    """Suggest an employer only when exactly one employer covers > 50 % of the repo's span."""
    if start is None:
        return None
    span_end = max(end or start, start)
    span_days = (span_end - start).days + 1
    matches = [
        group
        for group in groups
        if _group_overlap(start, span_end, group) > span_days * SPAN_OVERLAP_SHARE
    ]
    return _suggestion(matches[0]) if len(matches) == 1 else None


def group_for_company(groups: list[EmployerGroup], name: object) -> EmployerGroup | None:
    """The employer a stored or submitted company name belongs to (exact alias, else same key)."""
    if not isinstance(name, str) or not name.strip():
        return None
    wanted = name.strip().casefold()
    key = normalize_company(name)
    for group in groups:
        if wanted in {alias.casefold() for alias in group.aliases} or group.key == key:
            return group
    return None


def normalize_employer_ref(
    ref: dict[str, object] | None, groups: list[EmployerGroup]
) -> dict[str, object] | None:
    """Validate a chosen employer; returns the company-level shape stored, or raises ValueError."""
    if ref is None:
        return None
    if ref.get("kind") == PERSONAL_KIND:
        return {"kind": PERSONAL_KIND, "source": "user"}
    group = group_for_company(groups, ref.get("company"))
    if group is None:
        msg = "employer must be one of your employers or personal"
        raise ValueError(msg)
    return {"company": group.name, "start_date": None, "source": "user"}
