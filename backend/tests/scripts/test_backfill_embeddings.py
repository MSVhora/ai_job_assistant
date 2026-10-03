import pytest
import sqlalchemy as sa

from app.core.db import session_factory
from app.models import JobPosting
from scripts.backfill_embeddings import backfill

pytestmark = pytest.mark.usefixtures("clean_tables")


async def seed_unembedded_posting() -> None:
    async with session_factory() as session:
        session.add(
            JobPosting(
                source="adzuna",
                external_id="ext-1",
                title="Data Engineer",
                description="Build python pipelines. " * 10,
                raw_payload={},
            )
        )
        await session.commit()


async def embedded_count() -> int:
    async with session_factory() as session:
        return (
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(JobPosting)
                .where(JobPosting.embedding.is_not(None))
            )
        ) or 0


async def test_backfill_asks_for_confirmation_and_stops_on_no(
    fake_embedding: list[dict[str, object]], capsys: pytest.CaptureFixture[str]
) -> None:
    await seed_unembedded_posting()
    asked: list[str] = []

    def decline(prompt: str) -> str:
        asked.append(prompt)
        return "n"

    proceeded = await backfill(confirm=decline)

    assert proceeded is False
    assert len(asked) == 1
    assert "Estimated embedding cost" in capsys.readouterr().out
    assert fake_embedding == []
    assert await embedded_count() == 0


async def test_backfill_with_yes_skips_the_prompt_and_embeds(
    fake_embedding: list[dict[str, object]], capsys: pytest.CaptureFixture[str]
) -> None:
    await seed_unembedded_posting()

    def fail(_: str) -> str:
        pytest.fail("no confirmation expected with --yes")

    proceeded = await backfill(assume_yes=True, confirm=fail)

    assert proceeded is True
    assert "Estimated embedding cost" in capsys.readouterr().out
    assert len(fake_embedding) == 1
    assert await embedded_count() == 1


async def test_backfill_proceeds_after_a_yes_answer(
    fake_embedding: list[dict[str, object]],
) -> None:
    await seed_unembedded_posting()

    assert await backfill(confirm=lambda _: "y") is True
    assert await embedded_count() == 1
