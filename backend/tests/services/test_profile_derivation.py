from datetime import date

from app.schemas.profile import ExperienceItem, Preferences, StructuredProfile
from app.services import profile_derivation
from app.services.profile_derivation import (
    apply_derived_fields,
    derive_seniority,
    parse_years_of_experience,
    resolve_date,
)


def _item(start: str | None = None, end: str | None = None, **overrides: object) -> dict:
    return {"start_date": start, "end_date": end, **overrides}


def _experience(*items: dict) -> list[ExperienceItem]:
    return [ExperienceItem.model_validate(item) for item in items]


def _profile(experience_items: list[ExperienceItem], **extra: object) -> StructuredProfile:
    payload: dict = {
        "contact": {"full_name": "Jane Doe"},
        "experience": [item.model_dump(mode="json") for item in experience_items],
    }
    payload.update(extra)
    return StructuredProfile.model_validate(payload)


def test_no_parseable_dates_yield_none() -> None:
    empty = _experience({"title": "Dev", "start_date": None, "end_date": None})
    assert parse_years_of_experience(empty) is None


def test_no_experience_items_yield_none() -> None:
    assert parse_years_of_experience([]) is None


def test_fixed_past_span_is_exact() -> None:
    years = parse_years_of_experience(_experience(_item("Mar 2021", "Dec 2022")))
    # Mar 2021 to Dec 2022 is one year and change (640 days).
    assert years == 1


def test_month_names_full_abbreviated_and_period() -> None:
    assert resolve_date("March 2021") == resolve_date("Mar 2021") == resolve_date("Mar. 2021")


def test_year_only_parses_to_january() -> None:
    assert resolve_date("2019").month == 1


def test_numeric_month_formats() -> None:
    assert resolve_date("2020-05") == resolve_date("05/2020")
    assert resolve_date("2020-05-14").day == 14


def test_present_words_map_to_today() -> None:
    assert resolve_date("Present") == date.today()
    assert resolve_date("Current") == date.today()
    assert resolve_date("Now") == date.today()


def test_unparseable_strings_return_none() -> None:
    assert resolve_date("some time last year") is None
    assert resolve_date("") is None
    assert resolve_date(None) is None


def test_far_future_dates_rejected() -> None:
    assert resolve_date("Jan 2099") is None
    # A future-only span clamps to non-positive → None (no YOE signal).
    assert parse_years_of_experience(_experience(_item("Jan 2099", None))) is None


def test_current_role_extends_to_now() -> None:
    items = _experience(_item("Mar 2021", None, is_current=True))
    expected = (date.today() - date(2021, 3, 1)).days
    assert parse_years_of_experience(items) == int(expected // 365.25)


def test_span_not_sum_for_overlapping_roles() -> None:
    items = _experience(_item("Jan 2019", "Jan 2022"), _item("Jan 2021", "Jan 2024"))
    # Span 2019 → 2024, not the summed 2 + 3.
    assert parse_years_of_experience(items) == 4


def test_items_without_parseable_start_are_skipped() -> None:
    items = _experience(_item("way back when", "Jan 2105"), _item("Jan 2019", "Jan 2021"))
    assert parse_years_of_experience(items) == 2


def test_unparseable_end_treated_as_current() -> None:
    items = _experience(_item("Mar 2021", "way back then"))
    expected = (date.today() - date(2021, 3, 1)).days
    assert parse_years_of_experience(items) == int(expected // 365.25)


def test_derive_seniority_band_boundaries() -> None:
    settings = profile_derivation.get_settings()
    mid, senior, staff, principal = (
        settings.seniority_band_mid,
        settings.seniority_band_senior,
        settings.seniority_band_staff,
        settings.seniority_band_principal,
    )
    assert derive_seniority(0) == "junior"
    assert derive_seniority(mid - 1) == "junior"
    assert derive_seniority(mid) == "mid"
    assert derive_seniority(senior - 1) == "mid"
    assert derive_seniority(senior) == "senior"
    assert derive_seniority(staff - 1) == "senior"
    assert derive_seniority(staff) == "staff"
    assert derive_seniority(principal - 1) == "staff"
    assert derive_seniority(principal) == "principal"


def test_configured_bands_are_monotonic() -> None:
    settings = profile_derivation.get_settings()
    bands = (
        settings.seniority_band_mid,
        settings.seniority_band_senior,
        settings.seniority_band_staff,
        settings.seniority_band_principal,
    )
    assert list(bands) == sorted(bands)


def test_apply_fills_absent_seniority_and_marks_derived() -> None:
    profile = _profile(_experience(_item("Mar 2021", "Dec 2022")))
    assert apply_derived_fields(profile) is True
    assert profile.years_of_experience == 1
    assert profile.preferences is not None
    assert profile.preferences.seniority == "junior"
    assert profile.preferences.seniority_source == "derived"


def test_apply_never_touches_user_set_seniority() -> None:
    profile = _profile(
        _experience(_item("Mar 2015", "Dec 2022")),
        preferences={"seniority": "principal", "seniority_source": "user"},
    )
    assert apply_derived_fields(profile) is True  # YOE still updated
    assert profile.years_of_experience == 7
    assert profile.preferences.seniority == "principal"
    assert profile.preferences.seniority_source == "user"


def test_apply_never_touches_legacy_seniority() -> None:
    profile = _profile(
        _experience(_item("Mar 2000", None, is_current=True)),
        preferences=Preferences(seniority="mid").model_dump(mode="json"),
    )
    apply_derived_fields(profile)
    assert profile.preferences.seniority == "mid"
    assert profile.preferences.seniority_source is None


def test_apply_rederives_derived_seniority_when_yoe_changes() -> None:
    profile = _profile(_experience(_item("Mar 2021", "Dec 2022")))
    assert apply_derived_fields(profile) is True
    assert profile.preferences.seniority == "junior"

    profile.experience[0].end_date = "Mar 2024"
    assert apply_derived_fields(profile) is True
    assert profile.years_of_experience == 3
    assert profile.preferences.seniority == "mid"
    assert profile.preferences.seniority_source == "derived"


def test_apply_is_idempotent() -> None:
    profile = _profile(_experience(_item("Mar 2021", "Dec 2022")))
    apply_derived_fields(profile)
    stable = profile.model_copy(deep=True)
    assert apply_derived_fields(profile) is False
    assert profile == stable


def test_apply_clears_stale_derived_seniority_without_dates() -> None:
    profile = _profile(
        _experience(_item("Mar 2021", "Dec 2022")),
        skills=["SQL"],
    )
    apply_derived_fields(profile)
    assert profile.preferences.seniority_source == "derived"

    profile.experience[0].start_date = "whenever"
    profile.experience[0].end_date = "sort of then"
    assert apply_derived_fields(profile) is True
    assert profile.years_of_experience is None
    assert profile.preferences.seniority is None
    assert profile.preferences.seniority_source is None
