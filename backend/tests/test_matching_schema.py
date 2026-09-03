import pytest
from pydantic import ValidationError

from app.models import JobType, RemoteType
from app.schemas.matching import MatchFilters


def test_blank_location_normalizes_to_none() -> None:
    assert MatchFilters(location="   ").location is None


def test_location_rejects_over_long_value() -> None:
    with pytest.raises(ValidationError):
        MatchFilters(location="x" * 201)


def test_posted_within_days_bounds() -> None:
    assert MatchFilters(posted_within_days=1).posted_within_days == 1
    assert MatchFilters(posted_within_days=90).posted_within_days == 90
    with pytest.raises(ValidationError):
        MatchFilters(posted_within_days=0)
    with pytest.raises(ValidationError):
        MatchFilters(posted_within_days=91)


def test_enum_values_coerce_and_reject_unknown() -> None:
    filters = MatchFilters(remote_type="remote", job_type="full_time")
    assert filters.remote_type is RemoteType.remote
    assert filters.job_type is JobType.full_time
    with pytest.raises(ValidationError):
        MatchFilters(remote_type="bogus")
    with pytest.raises(ValidationError):
        MatchFilters(job_type="bogus")


def test_all_fields_optional() -> None:
    assert MatchFilters().model_dump() == {
        "location": None,
        "remote_type": None,
        "job_type": None,
        "posted_within_days": None,
    }
