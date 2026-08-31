import pytest
from fakes import VALID_PROFILE
from pydantic import ValidationError

from app.schemas.profile import StructuredProfile


def test_full_profile_validates() -> None:
    profile = StructuredProfile.model_validate(VALID_PROFILE)

    assert profile.contact.full_name == "Jane Doe"
    assert profile.contact.email == "jane@example.com"
    assert profile.experience[0].company == "Acme Corp"
    assert profile.experience[0].is_current is True
    assert profile.education[0].degree == "MSc"
    assert profile.certifications[0].issuer == "AWS"


def test_dates_preserved_as_verbatim_strings() -> None:
    profile = StructuredProfile.model_validate(VALID_PROFILE)

    assert profile.experience[0].start_date == "Mar 2021"
    assert profile.certifications[0].issued_date == "2022"


def test_minimal_profile_validates_with_defaults() -> None:
    profile = StructuredProfile.model_validate(
        {"contact": {"full_name": "Jane Doe"}, "skills": ["SQL"]}
    )

    assert profile.headline is None
    assert profile.experience == []
    assert profile.projects == []
    assert profile.education == []
    assert profile.extra_sections == []
    assert profile.preferences is None


def test_projects_awards_and_extra_sections_validate() -> None:
    profile = StructuredProfile.model_validate(VALID_PROFILE)

    assert profile.projects[0].name == "OpenPipeline"
    assert profile.projects[0].technologies == ["Python", "dbt"]
    assert profile.awards[0].title == "Winner, HackX 2023"
    assert profile.awards[0].issuer == "HackX"
    assert profile.awards[1].issued_date is None
    assert profile.extra_sections[0].title == "Publications"
    assert profile.extra_sections[1].title == "Languages"


def test_awards_only_profile_validates() -> None:
    profile = StructuredProfile.model_validate(
        {"contact": {"full_name": "J"}, "awards": [{"title": "HackX winner"}]}
    )

    assert profile.awards[0].title == "HackX winner"
    assert profile.skills == []


def test_extra_section_without_entries_rejected() -> None:
    with pytest.raises(ValidationError):
        StructuredProfile.model_validate(
            {
                "contact": {"full_name": "J"},
                "skills": ["SQL"],
                "extra_sections": [{"title": "Awards", "entries": []}],
            }
        )


def test_extra_sections_only_profile_validates() -> None:
    profile = StructuredProfile.model_validate(
        {
            "contact": {"full_name": "J"},
            "extra_sections": [{"title": "Awards", "entries": ["HackX winner"]}],
        }
    )

    assert profile.skills == []
    assert profile.extra_sections[0].entries == ["HackX winner"]


def test_skills_only_profile_validates() -> None:
    profile = StructuredProfile.model_validate(
        {"contact": {"full_name": "Jane"}, "skills": ["SQL"], "experience": []}
    )

    assert profile.skills == ["SQL"]


def test_all_null_content_rejected() -> None:
    with pytest.raises(ValidationError, match="at least one skill"):
        StructuredProfile.model_validate({"contact": {"full_name": "Jane Doe"}})


def test_empty_skills_without_experience_rejected() -> None:
    with pytest.raises(ValidationError):
        StructuredProfile.model_validate({"contact": {"full_name": "J"}, "skills": []})


def test_missing_full_name_rejected() -> None:
    with pytest.raises(ValidationError):
        StructuredProfile.model_validate({"contact": {"email": "j@example.com"}, "skills": ["SQL"]})


def test_invalid_remote_preference_rejected() -> None:
    with pytest.raises(ValidationError):
        StructuredProfile.model_validate(
            {
                "contact": {"full_name": "J"},
                "skills": ["SQL"],
                "preferences": {"remote_preference": "anywhere"},
            }
        )


def test_preferences_extracted_only_when_stated() -> None:
    payload = {
        **VALID_PROFILE,
        "preferences": {
            "target_title": "Senior Data Analyst",
            "remote_preference": "hybrid",
            "salary_min": 70000,
            "currency": "EUR",
        },
    }

    profile = StructuredProfile.model_validate(payload)

    assert profile.preferences is not None
    assert profile.preferences.remote_preference == "hybrid"
    assert profile.preferences.target_location is None
