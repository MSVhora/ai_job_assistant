from datetime import UTC, datetime, timedelta

import pytest

from app.core.db import session_factory
from app.models import JobPosting, JobType, RemoteType
from app.schemas.matching import MatchFilters
from app.services.matching import ranked_postings_query

pytestmark = pytest.mark.usefixtures("clean_tables")

NOW = datetime.now(UTC)


def axis_vector(index: int, sign: float = 1.0) -> list[float]:
    vector = [0.0] * 768
    vector[index] = sign
    return vector


def posting(
    external_id: str,
    *,
    location: str | None = "Berlin, Germany",
    remote: RemoteType = RemoteType.remote,
    job_type: JobType = JobType.full_time,
    posted_at: datetime | None = NOW - timedelta(days=2),
    embedding: list[float] | None = None,
) -> JobPosting:
    return JobPosting(
        source="adzuna",
        external_id=external_id,
        title=f"Job {external_id}",
        location=location,
        remote_type=remote,
        job_type=job_type,
        posted_at=posted_at,
        description="desc",
        embedding=embedding,
        raw_payload={"id": external_id},
    )


async def insert_postings() -> None:
    async with session_factory() as session:
        session.add_all(
            [
                posting("near", embedding=axis_vector(0)),
                posting(
                    "far",
                    location="Munich, Germany",
                    remote=RemoteType.on_site,
                    job_type=JobType.contract,
                    posted_at=NOW - timedelta(days=40),
                    embedding=axis_vector(1),
                ),
                posting("opposite", embedding=axis_vector(0, -1.0)),
                posting("no_embed", embedding=None),
                posting("null_date", posted_at=None, embedding=axis_vector(2)),
                posting("wildcard", location="100% Remote", embedding=axis_vector(3)),
            ]
        )
        await session.commit()


async def run_query(embedding: list[float], filters: MatchFilters) -> list[tuple[str, float]]:
    async with session_factory() as session:
        result = await session.execute(ranked_postings_query(embedding, filters))
        return [(row[0].external_id, row[1]) for row in result.all()]


async def test_orders_by_cosine_distance_excluding_unembedded() -> None:
    await insert_postings()

    rows = await run_query(axis_vector(0), MatchFilters())

    ids = [external_id for external_id, _ in rows]
    assert ids[0] == "near"
    assert ids[-1] == "opposite"
    assert "no_embed" not in ids
    distances = [distance for _, distance in rows]
    assert distances == sorted(distances)
    assert abs(distances[0]) < 1e-6
    assert all(0.0 <= distance <= 2.0 for distance in distances)


async def test_location_filter_is_case_insensitive_substring() -> None:
    await insert_postings()

    rows = await run_query(axis_vector(0), MatchFilters(location="BERLIN"))

    ids = {external_id for external_id, _ in rows}
    assert ids == {"near", "opposite", "null_date"}


async def test_location_filter_escapes_wildcards() -> None:
    await insert_postings()

    rows = await run_query(axis_vector(0), MatchFilters(location="100%"))
    underscore_rows = await run_query(axis_vector(0), MatchFilters(location="Ber_in"))

    assert [external_id for external_id, _ in rows] == ["wildcard"]
    assert underscore_rows == []


async def test_remote_and_job_type_filters() -> None:
    await insert_postings()

    remote_rows = await run_query(axis_vector(0), MatchFilters(remote_type=RemoteType.remote))
    contract_rows = await run_query(axis_vector(0), MatchFilters(job_type=JobType.contract))

    assert {external_id for external_id, _ in remote_rows} == {
        "near",
        "opposite",
        "null_date",
        "wildcard",
    }
    assert {external_id for external_id, _ in contract_rows} == {"far"}


async def test_posted_within_excludes_old_and_null_dates() -> None:
    await insert_postings()

    rows = await run_query(axis_vector(0), MatchFilters(posted_within_days=30))

    ids = {external_id for external_id, _ in rows}
    assert "far" not in ids
    assert "null_date" not in ids
    assert {"near", "opposite", "wildcard"} <= ids


async def test_combined_filters() -> None:
    await insert_postings()

    rows = await run_query(
        axis_vector(0),
        MatchFilters(location="Berlin", remote_type=RemoteType.remote, posted_within_days=30),
    )

    assert {external_id for external_id, _ in rows} == {"near", "opposite"}


async def test_null_posted_at_rows_rank_without_date_filter() -> None:
    await insert_postings()

    rows = await run_query(axis_vector(0), MatchFilters())

    assert "null_date" in [external_id for external_id, _ in rows]
