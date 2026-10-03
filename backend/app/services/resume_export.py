from app.schemas.resume_document import Bullet, ResumeContent
from app.services.resume_mapping import to_json_resume

__all__ = ["to_json_resume", "to_markdown", "to_plain_text"]

Section = tuple[str, list[str]]


def _dates(start: str | None, end: str | None, *, current: bool = False) -> str:
    finish = "Present" if current and not end else end
    return " - ".join(part for part in (start, finish) if part)


def _line(*parts: str | None, sep: str = ", ") -> str:
    return sep.join(part for part in parts if part)


def _contact(content: ResumeContent) -> list[str]:
    basics = content.basics
    details = _line(basics.email, basics.phone, basics.location, sep=" | ")
    links = [link.url for link in basics.links]
    return [line for line in (details, " | ".join(links)) if line]


def _bullets(bullets: list[Bullet]) -> list[str]:
    return [f"- {bullet.text}" for bullet in bullets]


def _experience(content: ResumeContent) -> list[Section]:
    lines: list[str] = []
    for job in content.work:
        lines.append(_line(job.title, job.company, job.location))
        when = _dates(job.start_date, job.end_date, current=job.is_current)
        if when:
            lines.append(when)
        lines.extend(_bullets(job.highlights))
    return [("Experience", lines)] if lines else []


def _education(content: ResumeContent) -> list[Section]:
    lines: list[str] = []
    for item in content.education:
        lines.append(_line(item.degree, item.field, item.institution))
        when = _dates(item.start_date, item.end_date)
        if when:
            lines.append(when)
    return [("Education", lines)] if lines else []


def _projects(content: ResumeContent) -> list[Section]:
    lines: list[str] = []
    for project in content.projects:
        lines.append(_line(project.name, project.role, project.url))
        if project.description:
            lines.append(project.description)
        if project.technologies:
            lines.append("Technologies: " + ", ".join(project.technologies))
        lines.extend(_bullets(project.highlights))
    return [("Projects", lines)] if lines else []


def _credentials(content: ResumeContent) -> list[Section]:
    certificates = [_line(c.name, c.issuer, c.issued_date) for c in content.certificates]
    awards = [_line(a.title, a.issuer, a.issued_date) for a in content.awards]
    sections: list[Section] = []
    if certificates:
        sections.append(("Certifications", certificates))
    if awards:
        sections.append(("Awards", awards))
    return sections


def _sections(content: ResumeContent) -> list[Section]:
    """Section title plus plain lines; shared by every text format so they cannot drift."""
    summary: list[Section] = (
        [("Summary", [content.basics.summary])] if content.basics.summary else []
    )
    skills: list[Section] = [("Skills", [", ".join(content.skills)])] if content.skills else []
    extras: list[Section] = [
        (extra.title, [f"- {entry}" for entry in extra.entries]) for extra in content.extra_sections
    ]
    return [
        *summary,
        *_experience(content),
        *_education(content),
        *skills,
        *_projects(content),
        *_credentials(content),
        *extras,
    ]


def to_plain_text(content: ResumeContent) -> str:
    """Clean text: no private marks, badges or provenance; contact comes from the content."""
    lines = [content.basics.full_name, *_contact(content)]
    for title, body in _sections(content):
        lines.extend(["", title.upper(), *body])
    return "\n".join(lines) + "\n"


def to_markdown(content: ResumeContent) -> str:
    lines = [f"# {content.basics.full_name}", "", *_contact(content)]
    for title, body in _sections(content):
        lines.extend(["", f"## {title}", ""])
        lines.extend(body)
    return "\n".join(lines) + "\n"
