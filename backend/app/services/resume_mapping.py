from app.schemas.profile import (
    AwardItem,
    CertificationItem,
    ContactInfo,
    EducationItem,
    ExperienceItem,
    ExtraSection,
    ProjectItem,
    StructuredProfile,
)
from app.schemas.resume_document import (
    AwardEntry,
    Basics,
    Bullet,
    CertificateEntry,
    EducationEntry,
    ExtraEntry,
    ProjectEntry,
    ResumeContent,
    WorkEntry,
)

# Server-managed profile fields that never travel through a resume document.
EXCLUDED_PROFILE_FIELDS = frozenset({"preferences", "years_of_experience"})


def _verbatim(texts: list[str]) -> list[Bullet]:
    return [Bullet(text=text, origin="profile_verbatim") for text in texts]


def profile_to_content(profile: StructuredProfile) -> ResumeContent:
    """Copy a profile into a document; its own bullets become `profile_verbatim` bullets."""
    contact = profile.contact
    return ResumeContent(
        basics=Basics(
            full_name=contact.full_name,
            label=profile.headline,
            summary=profile.summary,
            email=contact.email,
            phone=contact.phone,
            location=contact.location,
            country=contact.country,
            links=list(contact.links),
        ),
        skills=list(profile.skills),
        work=[
            WorkEntry(
                company=job.company,
                title=job.title,
                location=job.location,
                start_date=job.start_date,
                end_date=job.end_date,
                is_current=job.is_current,
                highlights=_verbatim(job.bullets),
            )
            for job in profile.experience
        ],
        education=[EducationEntry(**item.model_dump()) for item in profile.education],
        projects=[
            ProjectEntry(
                name=project.name,
                role=project.role,
                url=project.url,
                start_date=project.start_date,
                end_date=project.end_date,
                description=project.description,
                technologies=list(project.technologies),
                highlights=_verbatim(project.bullets),
            )
            for project in profile.projects
        ],
        awards=[AwardEntry(**item.model_dump()) for item in profile.awards],
        certificates=[CertificateEntry(**item.model_dump()) for item in profile.certifications],
        extra_sections=[ExtraEntry(**item.model_dump()) for item in profile.extra_sections],
    )


def content_to_structured_profile(
    content: ResumeContent, base: StructuredProfile | None = None
) -> StructuredProfile:
    """Flatten a document back to a profile; `base` supplies the server-managed fields."""
    basics = content.basics
    return StructuredProfile(
        contact=ContactInfo(
            full_name=basics.full_name,
            email=basics.email,
            phone=basics.phone,
            location=basics.location,
            country=basics.country,
            links=list(basics.links),
        ),
        headline=basics.label,
        summary=basics.summary,
        skills=list(content.skills),
        experience=[
            ExperienceItem(
                company=job.company,
                title=job.title,
                location=job.location,
                start_date=job.start_date,
                end_date=job.end_date,
                is_current=job.is_current,
                bullets=[bullet.text for bullet in job.highlights],
            )
            for job in content.work
        ],
        projects=[
            ProjectItem(
                name=project.name,
                role=project.role,
                url=project.url,
                start_date=project.start_date,
                end_date=project.end_date,
                description=project.description,
                bullets=[bullet.text for bullet in project.highlights],
                technologies=list(project.technologies),
            )
            for project in content.projects
        ],
        education=[EducationItem(**item.model_dump()) for item in content.education],
        certifications=[CertificationItem(**item.model_dump()) for item in content.certificates],
        awards=[AwardItem(**item.model_dump()) for item in content.awards],
        extra_sections=[ExtraSection(**item.model_dump()) for item in content.extra_sections],
        preferences=base.preferences if base else None,
        years_of_experience=base.years_of_experience if base else None,
    )


def _drop_empty(values: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in values.items() if value not in (None, "", [])}


def _highlights(bullets: list[Bullet]) -> list[str]:
    return [bullet.text for bullet in bullets]


def to_json_resume(content: ResumeContent) -> dict[str, object]:
    """The https://jsonresume.org/schema field names; bullets flattened to strings."""
    basics = content.basics
    document: dict[str, object] = {
        "basics": _drop_empty(
            {
                "name": basics.full_name,
                "label": basics.label,
                "email": basics.email,
                "phone": basics.phone,
                "summary": basics.summary,
                "location": _drop_empty(
                    {"address": basics.location, "countryCode": basics.country}
                ),
                "profiles": [
                    _drop_empty({"network": link.label, "url": link.url}) for link in basics.links
                ],
            }
        ),
        "work": [
            _drop_empty(
                {
                    "name": job.company,
                    "position": job.title,
                    "location": job.location,
                    "startDate": job.start_date,
                    "endDate": job.end_date,
                    "highlights": _highlights(job.highlights),
                }
            )
            for job in content.work
        ],
        "education": [
            _drop_empty(
                {
                    "institution": item.institution,
                    "area": item.field,
                    "studyType": item.degree,
                    "startDate": item.start_date,
                    "endDate": item.end_date,
                }
            )
            for item in content.education
        ],
        "skills": [{"name": "Skills", "keywords": list(content.skills)}] if content.skills else [],
        "projects": [
            _drop_empty(
                {
                    "name": project.name,
                    "description": project.description,
                    "url": project.url,
                    "startDate": project.start_date,
                    "endDate": project.end_date,
                    "roles": [project.role] if project.role else [],
                    "keywords": list(project.technologies),
                    "highlights": _highlights(project.highlights),
                }
            )
            for project in content.projects
        ],
        "awards": [
            _drop_empty({"title": item.title, "awarder": item.issuer, "date": item.issued_date})
            for item in content.awards
        ],
        "certificates": [
            _drop_empty({"name": item.name, "issuer": item.issuer, "date": item.issued_date})
            for item in content.certificates
        ],
    }
    return {key: value for key, value in document.items() if value not in ([], {})}
