"""Backfill embeddings for postings ingested before the embedding pipeline existed,
or whose embed call failed at ingest time.

Uses the service layer only (job_embed_text + embed_texts), then re-scores every
embedded profile so match rows appear without waiting for a re-search. Re-rank is
NOT run here — rationales are produced by the next search run, as designed.

It prints an estimated embedding cost first and asks for confirmation; pass --yes to
skip the prompt (the estimate is still printed).

Run inside the API container (it has the Gemini key and DB access):
    docker cp backend/scripts/backfill_embeddings.py ai_job_assistant-api-1:/tmp/
    docker exec -it ai_job_assistant-api-1 python /tmp/backfill_embeddings.py [--yes]
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Callable

import sqlalchemy as sa

from app.adapters.llm import estimate_cost, estimate_tokens
from app.core.config import get_settings
from app.core.db import session_factory
from app.models import JobPosting, Match, Profile
from app.services import matching
from app.services.embedding import embed_texts, job_embed_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill")

BATCH_SIZE = 25


def describe_estimate(texts: list[str]) -> str:
    model = get_settings().embedding_model
    tokens = sum(
        estimate_tokens([{"role": "user", "content": text}], model=model) for text in texts
    )
    cost = estimate_cost(model, tokens)
    price = "cost unavailable for this model" if cost.usd is None else f"about ${cost.usd:.4f}"
    return f"{len(texts)} posting(s), roughly {tokens} tokens with {model}: {price}"


async def backfill(*, assume_yes: bool = False, confirm: Callable[[str], str] = input) -> bool:
    async with session_factory() as session:
        postings = (
            (
                await session.execute(
                    sa.select(JobPosting).where(
                        JobPosting.embedding.is_(None),
                        JobPosting.description.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        embeddable = []
        for posting in postings:
            text = job_embed_text(posting.title, posting.description)
            if text is not None:
                embeddable.append((posting, text))
        logger.info(
            "postings to embed: %d (skipping %d with no text)",
            len(embeddable),
            len(postings) - len(embeddable),
        )

        print(f"Estimated embedding cost: {describe_estimate([text for _, text in embeddable])}")
        if embeddable and not assume_yes and confirm("Proceed? [y/N] ").strip().lower() != "y":
            logger.info("aborted before calling the provider")
            return False

        updated = 0
        for start in range(0, len(embeddable), BATCH_SIZE):
            batch = embeddable[start : start + BATCH_SIZE]
            vectors = await embed_texts([text for _, text in batch])
            for (posting, _), vector in zip(batch, vectors, strict=True):
                posting.embedding = vector
                updated += 1
            await session.flush()
            logger.info("embedded %d/%d", updated, len(embeddable))

        profiles = (
            (await session.execute(sa.select(Profile).where(Profile.embedding.is_not(None))))
            .scalars()
            .all()
        )
        for profile in profiles:
            scored = await matching.rescore_matches(session, profile, invalidate_rationales=False)
            logger.info("rescored profile=%s against %d postings", profile.name, scored)

        total = await session.scalar(sa.select(sa.func.count()).select_from(Match))
        await session.commit()
        logger.info("done: %d postings embedded, %d match rows total", updated, total)
        return True


if __name__ == "__main__":
    arguments = argparse.ArgumentParser(description="Backfill missing posting embeddings")
    arguments.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    options = arguments.parse_args()
    sys.exit(0 if asyncio.run(backfill(assume_yes=options.yes)) else 1)
