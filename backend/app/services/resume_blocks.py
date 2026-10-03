import hashlib

from app.models import Achievement
from app.schemas.resume_document import (
    Bullet,
    CommentSection,
    ProjectEntry,
    ResumeContent,
    WorkEntry,
)
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


def block_for_achievement(achievement: Achievement, content: ResumeContent) -> str | None:
    """The work entry the user confirmed for it, else the project it belongs to, else None."""
    ref = achievement.employer_ref
    if ref is not None and _confirmed(ref):
        for job in content.work:
            if job.company == ref.get("company") and job.start_date == ref.get("start_date"):
                return job.id
    key = (achievement.project_key or "").casefold()
    if key:
        short = key.rsplit("/", 1)[-1]
        for project in content.projects:
            if project.name.casefold() in {key, short}:
                return project.id
    return None
