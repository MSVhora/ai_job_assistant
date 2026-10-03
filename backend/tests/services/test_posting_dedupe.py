"""Cross-source canonical grouping (issue #38) — dedupe service + collapse.

The `(source, external_id)` unique constraint stays dedupe line one; these
tests pin line two: pg_trgm-similarity grouping across sources, the merge
rules, the deterministic canonical choice, and the match collapse in
`rescore_matches` (same job from two sources → one match row).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fakes import VALID_PROFILE, fake_vector
from sqlalchemy import select

from app.core.db import session_factory
from app.models import JobPosting, JobSearch, JobSearchStatus, Match, Profile, SearchPosting
from app.schemas.profile import ProfileCreate, StructuredProfile
from app.services import matching, posting_dedupe
from app.services.profile_service import create_profile as create_profile_service

pytestmark = pytest.mark.usefixtures("clean_tables")

TITLE = "Senior Python Developer"


async def seed_posting(
    *,
    source: str,
    external_id: str,
    title: str = TITLE,
    company: str | None = "Acme",
    country: str | None = "de",
    fetched_at: datetime | None = None,
    posted_at: datetime | None = None,
    description: str | None = None,
    url: str | None = None,
) -> JobPosting:
    async with session_factory() as session:
        posting = JobPosting(
            source=source,
            external_id=external_id,
            title=title,
            company=company,
            country=country,
            url=url,
            description=description,
            posted_at=posted_at,
            fetched_at=fetched_at or datetime.now(UTC),
            raw_payload={"id": external_id},
        )
        session.add(posting)
        await session.commit()
        await session.refresh(posting)
        return posting


async def fetch_posting(posting_id: uuid.UUID) -> JobPosting:
    async with session_factory() as session:
        posting = await session.get(JobPosting, posting_id)
        assert posting is not None
        return posting


async def run_dedupe(posting_ids: list[uuid.UUID]) -> int:
    async with session_factory() as session:
        grouped = await posting_dedupe.dedupe_postings(session, posting_ids)
        await session.commit()
        return grouped


def normalize_company_cases() -> list[tuple[str | None, str | None]]:
    return [
        ("Acme, Inc.", "acme"),
        ("Acme Ltd", "acme"),
        ("Acme Corp.", "acme"),
        ("ACME GmbH", "acme"),
        ("Acme Holdings Ltd", "acme"),
        ("Acme", "acme"),
        ("  Acme  ", "acme"),
        (None, None),
        ("   ", None),
    ]


@pytest.mark.parametrize(("raw", "expected"), normalize_company_cases())
def test_normalize_company_strips_suffixes_and_punctuation(
    raw: str | None, expected: str | None
) -> None:
    assert posting_dedupe.normalize_company(raw) == expected


async def test_cross_source_duplicates_group_under_existing_canonical() -> None:
    existing = await seed_posting(
        source="adzuna",
        external_id="a-1",
        fetched_at=datetime.now(UTC) - timedelta(days=1),
        url="https://adzuna.example/a-1",
        posted_at=datetime.now(UTC) - timedelta(days=2),
        description="Short description",
    )
    duplicate = await seed_posting(
        source="apify_linkedin",
        external_id="li-1",
        url="https://linkedin.example/li-1",
        posted_at=datetime.now(UTC),
        description="A much richer and longer description of the very same role",
    )

    grouped = await run_dedupe([duplicate.id])

    assert grouped == 1
    duplicate_row = await fetch_posting(duplicate.id)
    assert duplicate_row.canonical_id == existing.id
    canonical = await fetch_posting(existing.id)
    assert canonical.canonical_id is None
    assert canonical.posted_at == duplicate_row.posted_at
    assert canonical.description == "A much richer and longer description of the very same role"
    assert canonical.source_urls == [
        {"source": "apify_linkedin", "url": "https://linkedin.example/li-1"}
    ]
    assert canonical.url == "https://adzuna.example/a-1"
    assert canonical.source == "adzuna"


async def test_merge_appends_url_record_once_per_duplicate() -> None:
    existing = await seed_posting(
        source="adzuna", external_id="a-1", fetched_at=datetime.now(UTC) - timedelta(days=1)
    )
    duplicate = await seed_posting(source="apify_linkedin", external_id="li-1")

    await run_dedupe([duplicate.id])
    await run_dedupe([duplicate.id])

    canonical = await fetch_posting(existing.id)
    assert (canonical.source_urls or []).count({"source": "apify_linkedin", "url": None}) == 1


async def test_fresher_posted_at_on_canonical_side_wins() -> None:
    older = await seed_posting(
        source="adzuna",
        external_id="a-1",
        posted_at=datetime.now(UTC) - timedelta(days=9),
        fetched_at=datetime.now(UTC) - timedelta(days=1),
    )
    newer = await seed_posting(
        source="apify_linkedin", external_id="li-1", posted_at=datetime.now(UTC)
    )

    await run_dedupe([newer.id])

    canonical = await fetch_posting(older.id)
    assert canonical.posted_at == newer.posted_at


async def test_same_title_different_company_never_groups() -> None:
    existing = await seed_posting(
        source="adzuna",
        external_id="a-1",
        company="Acme",
        fetched_at=datetime.now(UTC) - timedelta(days=1),
    )
    other = await seed_posting(source="apify_linkedin", external_id="li-1", company="Globex")

    assert await run_dedupe([other.id]) == 0
    assert (await fetch_posting(other.id)).canonical_id is None
    assert (await fetch_posting(existing.id)).canonical_id is None


async def test_same_title_company_different_country_never_groups() -> None:
    await seed_posting(
        source="adzuna",
        external_id="a-1",
        country="de",
        fetched_at=datetime.now(UTC) - timedelta(days=1),
    )
    other = await seed_posting(source="apify_linkedin", external_id="li-1", country="fr")

    assert await run_dedupe([other.id]) == 0
    assert (await fetch_posting(other.id)).canonical_id is None


async def test_below_threshold_title_never_groups() -> None:
    await seed_posting(
        source="adzuna",
        external_id="a-1",
        title="Senior Python Developer",
        fetched_at=datetime.now(UTC) - timedelta(days=1),
    )
    other = await seed_posting(
        source="apify_linkedin", external_id="li-1", title="Graduate Marketing Assistant"
    )

    assert await run_dedupe([other.id]) == 0
    assert (await fetch_posting(other.id)).canonical_id is None


async def test_null_company_or_country_never_groups() -> None:
    existing = await seed_posting(
        source="adzuna",
        external_id="a-1",
        company=None,
        fetched_at=datetime.now(UTC) - timedelta(days=1),
    )
    other = await seed_posting(source="apify_linkedin", external_id="li-1", company=None)

    assert await run_dedupe([other.id]) == 0

    legacy = await seed_posting(
        source="adzuna",
        external_id="a-2",
        country=None,
        fetched_at=datetime.now(UTC) - timedelta(days=1),
    )
    new_run = await seed_posting(source="apify_linkedin", external_id="li-2")

    assert await run_dedupe([new_run.id]) == 0
    assert (await fetch_posting(legacy.id)).canonical_id is None
    assert (await fetch_posting(existing.id)).canonical_id is None


async def test_newer_row_never_steals_canonical_from_older_existing() -> None:
    """Canonical choice is deterministic: oldest (fetched_at, id) wins."""
    older = await seed_posting(
        source="adzuna", external_id="a-1", fetched_at=datetime.now(UTC) - timedelta(days=2)
    )
    newer = await seed_posting(
        source="apify_linkedin",
        external_id="li-1",
        fetched_at=datetime.now(UTC) - timedelta(days=1),
    )

    assert await run_dedupe([newer.id]) == 1
    assert (await fetch_posting(newer.id)).canonical_id == older.id

    assert await run_dedupe([older.id, newer.id]) == 0
    assert (await fetch_posting(older.id)).canonical_id is None


async def test_chain_resolves_on_write_and_stays_single_level() -> None:
    canonical = await seed_posting(
        source="adzuna", external_id="a-1", fetched_at=datetime.now(UTC) - timedelta(days=3)
    )
    duplicate = await seed_posting(
        source="adzuna", external_id="a-2", fetched_at=datetime.now(UTC) - timedelta(days=2)
    )
    assert await run_dedupe([duplicate.id]) == 1

    third = await seed_posting(
        source="apify_linkedin", external_id="li-1", fetched_at=datetime.now(UTC)
    )

    assert await run_dedupe([third.id]) == 1
    assert (await fetch_posting(third.id)).canonical_id == canonical.id
    assert (await fetch_posting(duplicate.id)).canonical_id == canonical.id
    assert (await fetch_posting(canonical.id)).canonical_id is None


async def test_later_duplicate_converges_on_same_canonical() -> None:
    canonical = await seed_posting(
        source="adzuna", external_id="a-1", fetched_at=datetime.now(UTC) - timedelta(days=2)
    )
    first = await seed_posting(
        source="apify_linkedin", external_id="li-1", fetched_at=datetime.now(UTC)
    )
    assert await run_dedupe([first.id]) == 1

    second = await seed_posting(
        source="other", external_id="o-1", fetched_at=datetime.now(UTC) + timedelta(minutes=1)
    )
    assert await run_dedupe([second.id]) == 1

    assert (await fetch_posting(first.id)).canonical_id == canonical.id
    assert (await fetch_posting(second.id)).canonical_id == canonical.id
    assert (await fetch_posting(canonical.id)).canonical_id is None


# --- match collapse (rescore_matches keys on the canonical representative) ---


async def seed_profile_with_embedding(name: str = "Deduper") -> tuple[uuid.UUID, list[float]]:
    async with session_factory() as session:
        response = await create_profile_service(
            session,
            ProfileCreate(
                name=name,
                structured_profile=StructuredProfile.model_validate(VALID_PROFILE),
            ),
        )
        await session.commit()
        profile = await session.get(Profile, response.profile_id)
        assert profile is not None and profile.embedding is not None
        return profile.id, profile.embedding


async def seed_corpus_postings(
    profile_id: uuid.UUID, specs: list[dict[str, Any]], source: str = "adzuna"
) -> list[JobPosting]:
    async with session_factory() as session:
        search = JobSearch(
            profile_id=profile_id,
            source=source,
            status=JobSearchStatus.succeeded,
            query={"profile_id": str(profile_id), "source": source},
        )
        session.add(search)
        await session.flush()
        postings = []
        for spec in specs:
            posting = JobPosting(
                source=spec.get("source", source),
                external_id=spec["external_id"],
                title=spec["title"],
                company=spec.get("company", "Acme"),
                country=spec.get("country", "de"),
                description=spec.get("description"),
                embedding=spec.get("embedding"),
                fetched_at=spec.get("fetched_at", datetime.now(UTC)),
                raw_payload={"id": spec["external_id"]},
            )
            session.add(posting)
            postings.append(posting)
        await session.flush()
        for posting in postings:
            session.add(SearchPosting(search_id=search.id, posting_id=posting.id))
        await session.commit()
        for posting in postings:
            await session.refresh(posting)
        return postings


async def fetch_matches(profile_id: uuid.UUID) -> list[Match]:
    async with session_factory() as session:
        result = await session.execute(select(Match).where(Match.profile_id == profile_id))
        return list(result.scalars().all())


async def test_two_source_duplicates_collapse_to_one_match_row() -> None:
    profile_id, _ = await seed_profile_with_embedding()
    adzuna, linkedin = await seed_corpus_postings(
        profile_id,
        [
            {"external_id": "a-1", "title": TITLE, "embedding": fake_vector(TITLE)},
            {"external_id": "li-1", "source": "apify_linkedin", "title": TITLE},
        ],
    )
    assert await run_dedupe([linkedin.id]) == 1

    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        outcome = await matching.rescore_matches(session, profile, invalidate_rationales=False)
        await session.commit()

    assert outcome == 1
    matches = await fetch_matches(profile_id)
    assert len(matches) == 1
    assert matches[0].job_posting_id == adzuna.id


async def test_stale_duplicate_match_is_deleted_canonical_match_kept() -> None:
    profile_id, _ = await seed_profile_with_embedding()
    adzuna, linkedin = await seed_corpus_postings(
        profile_id,
        [
            {"external_id": "a-1", "title": TITLE, "embedding": fake_vector(TITLE)},
            {"external_id": "li-1", "source": "apify_linkedin", "title": TITLE},
        ],
    )

    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        await matching.rescore_matches(session, profile, invalidate_rationales=False)
        await session.commit()

    pre_matches = await fetch_matches(profile_id)
    assert {match.job_posting_id for match in pre_matches} == {adzuna.id, linkedin.id}
    linkedin_match = next(m for m in pre_matches if m.job_posting_id == linkedin.id)
    async with session_factory() as session:
        stored = await session.get(Match, linkedin_match.id)
        assert stored is not None
        stored.rationale = "Ranked before the dedupe."
        await session.commit()

    assert await run_dedupe([linkedin.id]) == 1
    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        await matching.rescore_matches(session, profile, invalidate_rationales=False)
        await session.commit()

    matches = await fetch_matches(profile_id)
    assert len(matches) == 1
    assert matches[0].job_posting_id == adzuna.id
    assert matches[0].rationale is None


async def test_rescore_without_duplicates_leaves_matches_untouched() -> None:
    profile_id, _ = await seed_profile_with_embedding()
    first, second = await seed_corpus_postings(
        profile_id,
        [
            {"external_id": "a-1", "title": "Data Engineer", "embedding": fake_vector("de-1")},
            {"external_id": "a-2", "title": "Platform Engineer", "embedding": fake_vector("pe-1")},
        ],
    )

    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        await matching.rescore_matches(session, profile, invalidate_rationales=False)
        await session.commit()

    matches = await fetch_matches(profile_id)
    assert {match.job_posting_id for match in matches} == {first.id, second.id}

    assert await run_dedupe([first.id, second.id]) == 0
    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        await matching.rescore_matches(session, profile, invalidate_rationales=False)
        await session.commit()

    matches = await fetch_matches(profile_id)
    assert {match.job_posting_id for match in matches} == {first.id, second.id}
    assert all(match.vector_score is not None for match in matches)
