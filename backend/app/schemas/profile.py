import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

RevisionSourceLiteral = Literal["ai_extraction", "manual_edit", "gap_fill", "reupload_merge"]

RemotePreference = Literal["remote", "hybrid", "onsite", "flexible"]

SeniorityLevel = Literal[
    "intern",
    "junior",
    "mid",
    "senior",
    "staff",
    "lead",
    "principal",
    "manager",
    "director",
    "executive",
]


class SourceLink(BaseModel):
    label: str | None = Field(default=None, description="e.g. LinkedIn, GitHub, portfolio")
    url: str


class ContactInfo(BaseModel):
    full_name: str = Field(min_length=1)
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[SourceLink] = []


class ExperienceItem(BaseModel):
    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: str | None = Field(default=None, description="verbatim as written on the resume")
    end_date: str | None = Field(default=None, description="verbatim as written on the resume")
    is_current: bool = False
    bullets: list[str] = []


class EducationItem(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class CertificationItem(BaseModel):
    name: str
    issuer: str | None = None
    issued_date: str | None = None


class AwardItem(BaseModel):
    title: str
    issuer: str | None = None
    issued_date: str | None = Field(default=None, description="verbatim as written on the resume")


class ProjectItem(BaseModel):
    name: str
    role: str | None = None
    url: str | None = None
    start_date: str | None = Field(default=None, description="verbatim as written on the resume")
    end_date: str | None = Field(default=None, description="verbatim as written on the resume")
    description: str | None = None
    bullets: list[str] = []
    technologies: list[str] = []


class ExtraSection(BaseModel):
    title: str = Field(
        min_length=1,
        description=(
            "original resume section title: Awards, Publications, Languages, Volunteer, ..."
        ),
    )
    entries: list[str] = Field(min_length=1, description="one entry per line/bullet, verbatim")


class Preferences(BaseModel):
    target_title: str | None = None
    target_location: str | None = None
    remote_preference: RemotePreference | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    currency: str | None = None
    seniority: SeniorityLevel | None = None
    work_authorization: str | None = Field(default=None, max_length=200)


class StructuredProfile(BaseModel):
    contact: ContactInfo
    headline: str | None = None
    summary: str | None = None
    skills: list[str] = []
    experience: list[ExperienceItem] = []
    projects: list[ProjectItem] = []
    education: list[EducationItem] = []
    certifications: list[CertificationItem] = []
    awards: list[AwardItem] = []
    extra_sections: list[ExtraSection] = []
    preferences: Preferences | None = None

    @model_validator(mode="after")
    def require_some_content(self) -> "StructuredProfile":
        if not (
            self.skills or self.experience or self.projects or self.awards or self.extra_sections
        ):
            raise ValueError(
                "profile must contain at least one skill, experience, project, "
                "or extra section entry"
            )
        return self


class RevisionSummary(BaseModel):
    id: uuid.UUID
    source: RevisionSourceLiteral
    created_at: datetime


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    structured_profile: StructuredProfile
    source_resume_id: uuid.UUID | None = Field(
        default=None,
        description="resume whose AI draft this profile is created from",
    )


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    structured_profile: StructuredProfile | None = None
    source_resume_id: uuid.UUID | None = Field(
        default=None,
        description="resume whose AI draft this save is reviewed from",
    )


class ProfileResponse(BaseModel):
    profile_id: uuid.UUID
    name: str
    structured_profile: StructuredProfile
    source_resume_id: uuid.UUID | None
    source_resume_filename: str | None
    updated_at: datetime
    last_revision: RevisionSummary | None = None


class ProfileSummary(BaseModel):
    profile_id: uuid.UUID
    name: str
    source_resume_filename: str | None
    created_at: datetime
    updated_at: datetime
