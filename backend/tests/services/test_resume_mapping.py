from typing import Any

from fakes import derived_valid_profile, golden_profile
from pydantic import BaseModel

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
from app.schemas.resume_document import ResumeContent
from app.services.resume_mapping import (
    EXCLUDED_PROFILE_FIELDS,
    content_to_structured_profile,
    profile_to_content,
    to_json_resume,
)

NESTED = (
    ContactInfo,
    ExperienceItem,
    ProjectItem,
    EducationItem,
    CertificationItem,
    AwardItem,
    ExtraSection,
)


def populated(model: type[BaseModel], instances: list[Any]) -> set[str]:
    return {
        name
        for name in model.model_fields
        for instance in instances
        if getattr(instance, name) not in (None, "", [], False)
    }


def test_round_trip_loses_nothing_for_the_golden_profile() -> None:
    profile = golden_profile()

    content = profile_to_content(profile)
    back = content_to_structured_profile(content, base=profile)

    assert back.model_dump() == profile.model_dump()


def test_round_trip_loses_nothing_for_the_standard_fixture() -> None:
    profile = StructuredProfile.model_validate(derived_valid_profile())

    back = content_to_structured_profile(profile_to_content(profile), base=profile)

    assert back.model_dump() == profile.model_dump()


def test_round_trip_survives_json_storage() -> None:
    profile = golden_profile()
    stored = profile_to_content(profile).model_dump(mode="json")

    back = content_to_structured_profile(ResumeContent.model_validate(stored), base=profile)

    assert back == profile


def test_every_profile_field_is_carried_or_explicitly_excluded() -> None:
    profile = golden_profile()
    carried = set(StructuredProfile.model_fields) - EXCLUDED_PROFILE_FIELDS
    without_base = content_to_structured_profile(profile_to_content(profile))

    for name in carried:
        assert getattr(profile, name), f"golden profile must populate {name}"
        assert getattr(without_base, name) == getattr(profile, name), f"{name} was lost"
    assert without_base.preferences is None
    assert without_base.years_of_experience is None


def test_golden_profile_populates_every_nested_field_so_a_new_field_fails_loudly() -> None:
    profile = golden_profile()
    groups = {
        ContactInfo: [profile.contact],
        ExperienceItem: profile.experience,
        ProjectItem: profile.projects,
        EducationItem: profile.education,
        CertificationItem: profile.certifications,
        AwardItem: profile.awards,
        ExtraSection: profile.extra_sections,
    }

    for model in NESTED:
        assert populated(model, groups[model]) == set(model.model_fields), model.__name__


def test_profile_bullets_become_verbatim_bullets_without_achievements() -> None:
    content = profile_to_content(golden_profile())

    bullets = [bullet for job in content.work for bullet in job.highlights]
    bullets += [bullet for project in content.projects for bullet in project.highlights]

    assert bullets
    assert {bullet.origin for bullet in bullets} == {"profile_verbatim"}
    assert {bullet.achievement_id for bullet in bullets} == {None}


def test_json_resume_export_uses_the_json_resume_field_names() -> None:
    document: dict[str, Any] = to_json_resume(profile_to_content(golden_profile()))

    assert document["basics"]["name"] == "Ada Lovelace"
    assert document["basics"]["location"] == {"address": "London, UK", "countryCode": "gb"}
    work = document["work"][0]
    assert work["name"] == "Engine Co"
    assert work["position"] == "Senior Engineer"
    assert work["highlights"] == [
        "Cut p95 latency by 60% across the ingest service",
        "Led the platform team",
    ]
    assert document["skills"] == [
        {"name": "Skills", "keywords": ["Python", "SQL", "Terraform", "Rust"]}
    ]
    assert document["education"][0]["studyType"] == "BSc"
    assert document["certificates"][0]["issuer"] == "CNCF"
    assert document["awards"][0]["awarder"] == "Engine Co"


def test_json_resume_export_omits_empty_sections() -> None:
    profile = StructuredProfile(contact=ContactInfo(full_name="Jo"), skills=["Go"])

    document = to_json_resume(profile_to_content(profile))

    assert set(document) == {"basics", "skills"}
