import hashlib
from datetime import UTC, date, datetime

from app.models import Achievement
from app.schemas.resume_document import (
    Bullet,
    CommentSection,
    ProjectEntry,
    ResumeContent,
    WorkEntry,
)
from app.services.company_names import Merges
from app.services.profile_derivation import resolve_date
from app.services.resume_writer import bullet_id

Entry = WorkEntry | ProjectEntry


def ensure_ids(content: ResumeContent) -> None:
    """Give every block and bullet a stable id derived from what it is, never a random one."""
    seen: dict[str, int] = {}
    for entry in blocks(content):
        name = entry.company if isinstance(entry, WorkEntry) else entry.name
        base = f"{section_of(entry)}|{name or ''}|{entry.start_date or ''}"
        occurrence = seen.get(base, 0)
        seen[base] = occurrence + 1
        if not entry.id:
            digest = hashlib.sha1(f"{base}|{occurrence}".encode(), usedforsecurity=False)
            entry.id = digest.hexdigest()[:12]
        for bullet in entry.highlights:
            if not bullet.id:
                bullet.id = bullet_id(entry.id, bullet.achievement_id or bullet.text)


def blocks(content: ResumeContent) -> list[Entry]:
    return [*content.work, *content.projects]


def section_of(entry: Entry) -> CommentSection:
    return "work" if isinstance(entry, WorkEntry) else "projects"


def find_block(content: ResumeContent, block_id: str) -> Entry | None:
    return next((entry for entry in blocks(content) if entry.id == block_id), None)


def find_bullet(content: ResumeContent, bullet_id_: str) -> tuple[Entry, Bullet] | None:
    for entry in blocks(content):
        for bullet in entry.highlights:
            if bullet.id == bullet_id_:
                return entry, bullet
    return None


def is_current(entry: Entry) -> bool:
    return isinstance(entry, WorkEntry) and entry.is_current


def header(entry: Entry) -> str:
    if isinstance(entry, WorkEntry):
        return f"{entry.title or 'Role'} at {entry.company or 'an employer'}"
    return f"Project: {entry.name}" + (f" ({entry.role})" if entry.role else "")


def _confirmed(ref: dict[str, object] | None) -> bool:
    return ref is not None and ref.get("kind") != "personal" and ref.get("source") != "suggested"


def _stint_window(job: WorkEntry) -> tuple[date | None, date | None]:
    start = resolve_date(job.start_date)
    end = resolve_date(job.end_date)
    if end is None and job.is_current:
        end = datetime.now(UTC).date()
    return start, end


def _overlap_days(job: WorkEntry, start: date, end: date) -> int:
    job_start, job_end = _stint_window(job)
    if job_start is None:
        return 0
    return (min(end, job_end or job_start) - max(start, job_start)).days + 1


def pick_stint(jobs: list[WorkEntry], start: date | None, end: date | None) -> WorkEntry:
    """Among one employer's stints: the one the dates fall in, else the most recent."""
    if start is not None:
        span_end = max(end or start, start)
        best = max(jobs, key=lambda job: _overlap_days(job, start, span_end))
        if _overlap_days(best, start, span_end) > 0:
            return best

    def recency(job: WorkEntry) -> tuple[bool, date]:
        job_start, job_end = _stint_window(job)
        return (job.is_current, job_end or job_start or date.min)

    return max(jobs, key=recency)


def _employer_stint(
    ref: dict[str, object], achievement: Achievement, content: ResumeContent, merges: Merges
) -> WorkEntry | None:
    company, start_date = ref.get("company"), ref.get("start_date")
    for job in content.work:
        if start_date and job.company == company and job.start_date == start_date:
            return job
    wanted = merges.key(company if isinstance(company, str) else None)
    jobs = [job for job in content.work if wanted != "" and merges.key(job.company) == wanted]
    if not jobs:
        return None
    return pick_stint(jobs, achievement.time_start, achievement.time_end)


def block_for_achievement(
    achievement: Achievement, content: ResumeContent, merges: Merges | None = None
) -> str | None:
    """The work entry the user confirmed for it, else the project it belongs to, else None.

    A company-level employer picks the stint by the achievement's dates (most recent otherwise);
    a legacy reference that names one entry still resolves to exactly that entry.
    """
    ref = achievement.employer_ref
    if ref is not None and _confirmed(ref):
        job = _employer_stint(ref, achievement, content, merges or Merges())
        if job is not None:
            return job.id
    key = (achievement.project_key or "").casefold()
    if key:
        short = key.rsplit("/", 1)[-1]
        for project in content.projects:
            if project.name.casefold() in {key, short}:
                return project.id
    return None
