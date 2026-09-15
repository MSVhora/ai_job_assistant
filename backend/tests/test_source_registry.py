from pathlib import Path

import pytest

from app.adapters.job_sources import registry
from app.adapters.job_sources.base import (
    ConnectorConfigError,
    JobSearchQuery,
    SourceFilterDecl,
    date_posted_bucket,
)
from app.adapters.job_sources.config import (
    ActorConfig,
    build_actor_input,
    load_actor_configs,
)


@pytest.mark.parametrize(
    ("max_days_old", "bucket"),
    [
        (None, "anyTime"),
        (1, "past24Hours"),
        (2, "pastWeek"),
        (7, "pastWeek"),
        (8, "pastMonth"),
        (30, "pastMonth"),
        (31, "anyTime"),
        (90, "anyTime"),
    ],
)
def test_date_posted_bucket(max_days_old: int | None, bucket: str) -> None:
    assert date_posted_bucket(max_days_old) == bucket


VALID = """
sources:
  - name: apify_test
    type: apify_actor
    actor_id: act_1
    external_id_field: id
    input:
      keywords: "{query}"
      location: "{location}"
      limitPerSource: 25
"""


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "connectors.yaml"
    path.write_text(content)
    return path


def test_package_config_loads() -> None:
    actors = load_actor_configs()

    assert [actor.name for actor in actors] == ["apify_linkedin"]
    assert actors[0].actor_id == "hKByXkMQaC5Qt9UMN"
    assert actors[0].external_id_field == "id"
    assert [decl.key for decl in actors[0].filters] == [
        "distance_miles",
        "under_10_applicants",
        "company_ids",
        "geo_id",
    ]


def test_registry_contains_code_and_actor_sources() -> None:
    names = {source.name for source in registry.all_sources()}

    assert names == {"adzuna", "apify_linkedin"}


def test_loads_valid_config(tmp_path: Path) -> None:
    actors = load_actor_configs(_write(tmp_path, VALID))

    assert len(actors) == 1
    assert actors[0].name == "apify_test"


def test_rejects_unknown_placeholder(tmp_path: Path) -> None:
    content = VALID.replace('keywords: "{query}"', 'keywords: "{bogus}"')

    with pytest.raises(ConnectorConfigError, match="unknown placeholder"):
        load_actor_configs(_write(tmp_path, content))


def test_rejects_duplicate_names(tmp_path: Path) -> None:
    content = VALID.replace("    input:", "    input:", 1) + (
        "  - name: apify_test\n    type: apify_actor\n    actor_id: act_2\n"
        "    external_id_field: id\n    input: {}\n"
    )

    with pytest.raises(ConnectorConfigError, match="duplicate"):
        load_actor_configs(_write(tmp_path, content))


def test_rejects_invalid_shape(tmp_path: Path) -> None:
    with pytest.raises(ConnectorConfigError, match="invalid connector config"):
        load_actor_configs(_write(tmp_path, "sources:\n  - actor_id: missing_name\n"))


def test_rejects_invalid_name_pattern(tmp_path: Path) -> None:
    content = VALID.replace("name: apify_test", "name: Bad Name")

    with pytest.raises(ConnectorConfigError):
        load_actor_configs(_write(tmp_path, content))


def test_build_actor_input_resolves_placeholders() -> None:
    actor = ActorConfig(
        name="apify_x", actor_id="a", external_id_field="id", input={"keywords": "{query}"}
    )
    query = JobSearchQuery(query="python dev", country="us", results_wanted=25)

    built = build_actor_input(actor, query)

    assert built == {"keywords": "python dev"}


def test_build_actor_input_omits_null_location() -> None:
    actor = ActorConfig(
        name="apify_x",
        actor_id="a",
        external_id_field="id",
        input={"keywords": "{query}", "location": "{location}"},
    )
    query = JobSearchQuery(query="python dev", country="us")

    assert build_actor_input(actor, query) == {"keywords": "python dev"}

    located = JobSearchQuery(query="python dev", location="Berlin", country="us")
    assert build_actor_input(actor, located) == {"keywords": "python dev", "location": "Berlin"}


def test_build_actor_input_resolves_posted_bucket() -> None:
    actor = ActorConfig(
        name="apify_x",
        actor_id="a",
        external_id_field="id",
        input={"datePosted": "{date_posted_bucket}"},
    )

    assert build_actor_input(actor, JobSearchQuery(query="x", country="us")) == {
        "datePosted": "anyTime"
    }
    assert build_actor_input(actor, JobSearchQuery(query="x", country="us", max_days_old=7)) == {
        "datePosted": "pastWeek"
    }
    assert build_actor_input(actor, JobSearchQuery(query="x", country="us", max_days_old=30)) == {
        "datePosted": "pastMonth"
    }


def test_build_actor_input_resolves_option_placeholders() -> None:
    actor = ActorConfig(
        name="apify_x",
        actor_id="a",
        external_id_field="id",
        input={
            "distance": "{option:distance_miles}",
            "under10Applicants": "{option:under_10_applicants}",
            "companyIds": "{option:company_ids}",
            "geoId": "{option:geo_id}",
        },
        filters=[
            SourceFilterDecl(key="distance_miles", label="Radius", type="number"),
            SourceFilterDecl(key="under_10_applicants", label="Few applicants", type="boolean"),
            SourceFilterDecl(key="company_ids", label="Companies", type="multiselect"),
            SourceFilterDecl(key="geo_id", label="Geo", type="text"),
        ],
    )

    query = JobSearchQuery(
        query="x",
        country="us",
        options={
            "distance_miles": 25,
            "under_10_applicants": True,
            "company_ids": ["123"],
            "geo_id": "abc",
        },
    )
    assert build_actor_input(actor, query) == {
        "distance": 25,
        "under10Applicants": True,
        "companyIds": ["123"],
        "geoId": "abc",
    }
    assert build_actor_input(actor, JobSearchQuery(query="x", country="us")) == {}


def test_date_posted_bucket_placeholder_derives_from_shared_filter() -> None:
    actor = ActorConfig(
        name="apify_x",
        actor_id="a",
        external_id_field="id",
        input={"datePosted": "{date_posted_bucket}"},
    )

    derived = JobSearchQuery(query="x", country="us", max_days_old=7)
    assert build_actor_input(actor, derived) == {"datePosted": "pastWeek"}


def test_rejects_option_placeholder_for_undeclared_filter(tmp_path: Path) -> None:
    content = VALID.replace('keywords: "{query}"', 'keywords: "{option:bogus}"')

    with pytest.raises(ConnectorConfigError, match="declares no filter"):
        load_actor_configs(_write(tmp_path, content))
