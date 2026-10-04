from dataclasses import dataclass
from typing import get_args

from app.schemas.resume_document import (
    Bullet,
    ProjectEntry,
    ResumeContent,
    ResumeTemplate,
    WorkEntry,
)

TEMPLATES: tuple[str, ...] = get_args(ResumeTemplate)


@dataclass(frozen=True)
class Preset:
    name: str
    font_pt: float
    margin_in: float
    tight: bool


PRESETS = (
    Preset("P0", 10.5, 0.7, tight=False),
    Preset("P1", 10.0, 0.6, tight=False),
    Preset("P2", 9.5, 0.5, tight=True),
)

JsonObject = dict[str, object]


def _line(*parts: str | None, sep: str = ", ") -> str:
    return sep.join(part for part in parts if part)


def _dates(start: str | None, end: str | None, *, current: bool = False) -> str:
    finish = "Present" if current and not end else end
    return " - ".join(part for part in (start, finish) if part)


def _entry(
    head: str,
    sub: str = "",
    dates: str = "",
    note: str = "",
    bullets: list[str] | None = None,
) -> JsonObject:
    return {"head": head, "sub": sub, "dates": dates, "note": note, "bullets": bullets or []}


def _kept(bullets: list[Bullet], included: frozenset[str]) -> list[str]:
    return [bullet.text for bullet in bullets if bullet.id in included]


def _work(content: ResumeContent, included: frozenset[str]) -> list[JsonObject]:
    entries: list[JsonObject] = []
    for job in content.work:
        bullets = _kept(job.highlights, included)
        if bullets:
            entries.append(_work_entry(job, bullets))
    return entries


def _work_entry(job: WorkEntry, bullets: list[str]) -> JsonObject:
    return _entry(
        _line(job.title, job.company) or "Role",
        sub=job.location or "",
        dates=_dates(job.start_date, job.end_date, current=job.is_current),
        bullets=bullets,
    )


def _projects(content: ResumeContent, included: frozenset[str]) -> list[JsonObject]:
    entries: list[JsonObject] = []
    for project in content.projects:
        bullets = _kept(project.highlights, included)
        if bullets:
            entries.append(_project_entry(project, bullets))
    return entries


def _project_entry(project: ProjectEntry, bullets: list[str]) -> JsonObject:
    technologies = ", ".join(project.technologies)
    return _entry(
        _line(project.name, project.role),
        sub=_line(technologies, project.url, sep=" | "),
        dates=_dates(project.start_date, project.end_date),
        note=project.description or "",
        bullets=bullets,
    )


def _education(content: ResumeContent) -> list[JsonObject]:
    entries: list[JsonObject] = []
    for item in content.education:
        qualification = _line(item.degree, item.field)
        entries.append(
            _entry(
                qualification or item.institution or "Education",
                sub=(item.institution or "") if qualification else "",
                dates=_dates(item.start_date, item.end_date),
            )
        )
    return entries


def _credentials(content: ResumeContent) -> list[JsonObject]:
    return [
        _entry(c.name, sub=c.issuer or "", dates=c.issued_date or "") for c in content.certificates
    ]


def _awards(content: ResumeContent) -> list[JsonObject]:
    return [_entry(a.title, sub=a.issuer or "", dates=a.issued_date or "") for a in content.awards]


def _sections(content: ResumeContent, included: frozenset[str]) -> list[JsonObject]:
    """Standard headings in a fixed order; a section with nothing to show is left out."""
    candidates: list[JsonObject] = []
    if content.basics.summary:
        candidates.append(_text("Summary", [content.basics.summary]))
    candidates.append(_entries("Experience", _work(content, included)))
    candidates.append(_entries("Education", _education(content)))
    if content.skills:
        candidates.append(_text("Skills", [", ".join(content.skills)]))
    candidates.append(_entries("Projects", _projects(content, included)))
    candidates.append(_entries("Certifications", _credentials(content)))
    candidates.append(_entries("Awards", _awards(content)))
    candidates.extend(
        {"title": extra.title, "kind": "bullets", "lines": list(extra.entries), "entries": []}
        for extra in content.extra_sections
    )
    return [section for section in candidates if section["lines"] or section["entries"]]


def _text(title: str, lines: list[str]) -> JsonObject:
    return {"title": title, "kind": "text", "lines": lines, "entries": []}


def _entries(title: str, entries: list[JsonObject]) -> JsonObject:
    return {"title": title, "kind": "entries", "lines": [], "entries": entries}


def _contact(content: ResumeContent) -> list[str]:
    basics = content.basics
    details = [basics.email, basics.phone, _line(basics.location, basics.country)]
    return [item for item in (*details, *(link.url for link in basics.links)) if item]


def build_data(
    content: ResumeContent, included: frozenset[str], preset: Preset, template: str
) -> JsonObject:
    """Everything the Typst template reads; the template never receives markup."""
    return {
        "variant": template,
        "font_pt": preset.font_pt,
        "margin_in": preset.margin_in,
        "tight": preset.tight,
        "name": content.basics.full_name,
        "label": content.basics.label or "",
        "contact": _contact(content),
        "sections": _sections(content, included),
    }
