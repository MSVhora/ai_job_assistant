import sqlalchemy as sa

from scripts.seed_demo import DEMO_EMAIL, DEMO_EXTERNAL_PREFIX, _reset, seed


async def test_seed_creates_profile_postings_and_matches(clean_tables) -> None:
    from app.core.db import session_factory
    from app.models import JobPosting, Match, Profile

    await seed(6, rerank=False)

    async with session_factory() as session:
        profile = (
            await session.execute(
                sa.select(Profile).where(
                    Profile.structured_profile["contact"]["email"].astext == DEMO_EMAIL
                )
            )
        ).scalar_one()
        assert profile.embedding is not None

        assert (await session.scalar(sa.select(sa.func.count()).select_from(JobPosting))) == 6
        demo_ids = (
            (
                await session.execute(
                    sa.select(JobPosting.external_id).where(
                        JobPosting.external_id.like(f"{DEMO_EXTERNAL_PREFIX}%")
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(demo_ids) == 6

        match_count = await session.scalar(
            sa.select(sa.func.count()).select_from(Match).where(Match.profile_id == profile.id)
        )
        assert match_count == 6
        seeded_match = (
            await session.execute(sa.select(Match).where(Match.profile_id == profile.id).limit(1))
        ).scalar_one()
        assert seeded_match.rationale is None
        assert seeded_match.role_fit is None


async def test_reset_removes_only_demo_data(clean_tables) -> None:
    from app.core.db import session_factory
    from app.models import Candidate, JobPosting, Match, Profile

    await seed(4, rerank=False)

    async with session_factory() as session:
        session.add(
            JobPosting(
                source="adzuna",
                external_id="real-1",
                title="Real job",
                description="A real posting",
                raw_payload={"id": "real-1"},
                embedding=[0.0] * 768,
            )
        )
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        session.add(
            Profile(
                candidate_id=candidate.id,
                name="Real User",
                structured_profile={"contact": {"full_name": "Real User"}, "skills": ["SQL"]},
            )
        )
        await session.commit()

    await _reset()

    async with session_factory() as session:
        remaining_postings = (
            (await session.execute(sa.select(JobPosting.external_id))).scalars().all()
        )
        assert remaining_postings == ["real-1"]
        remaining_profiles = (await session.execute(sa.select(Profile.name))).scalars().all()
        assert remaining_profiles == ["Real User"]
        assert (await session.scalar(sa.select(sa.func.count()).select_from(Match))) == 0
        assert (await session.scalar(sa.select(sa.func.count()).select_from(Candidate))) == 1
