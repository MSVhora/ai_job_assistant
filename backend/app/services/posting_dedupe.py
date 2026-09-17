"""Cross-source posting dedupe — canonical grouping (issue #38).

Dedupe line one is the `(source, external_id)` unique constraint (a source
re-finding its own posting refreshes in place). This module is line two:
postings from *different* sources describing the same job are grouped under
one canonical row — same resolved `country`, same normalized company, and
pg_trgm title similarity ≥ `posting_dedupe_similarity`.

Grouping is incremental: the pass runs inside `_run_source` over the
just-upserted batch and never reclusters the whole table. Pre-#38 pairs
collapse opportunistically when a source re-finds one of them. The canonical
is deterministically the oldest row (`fetched_at`, then `id`), so two
concurrent runs (allowed across sources by #36) converge on the same winner
without coordination. Invariant: `canonical_id` only ever points at a row
whose own `canonical_id` IS NULL — targets are resolved on write, no chains.
"""

import logging
import re
import uuid

from sqlalchemy import select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import JobPosting

logger = logging.getLogger(__name__)

_CORPORATE_SUFFIXES = {
    "ab",
    "ag",
    "as",
    "bv",
    "bhd",
    "co",
    "company",
    "corp",
    "corporation",
    "gmbh",
    "holdings",
    "inc",
    "incorporated",
    "kk",
    "kg",
    "limited",
    "llc",
    "llp",
    "lp",
    "ltd",
    "nv",
    "oy",
    "plc",
    "pte",
    "pty",
    "sa",
    "sdn",
    "ug",
}

_PUNCTUATION = re.compile(r"[^\w\s]")


def normalize_company(name: str | None) -> str | None:
    """Deterministic company key for the dedupe grouping guard (#38).

    Lowercase, punctuation stripped, whitespace collapsed, trailing corporate
    suffix tokens dropped repeatedly ("Acme, Inc." and "Acme Ltd" both map to
    "acme"). None never matches anything.
    """
    if name is None:
        return None
    cleaned = _PUNCTUATION.sub("", name.lower()).split()
    while cleaned and cleaned[-1] in _CORPORATE_SUFFIXES:
        cleaned.pop()
    return " ".join(cleaned) or None


async def _set_similarity_threshold(session: AsyncSession) -> None:
    threshold = get_settings().posting_dedupe_similarity
    await session.execute(
        text("SELECT set_config('pg_trgm.similarity_threshold', :threshold, true)"),
        {"threshold": str(threshold)},
    )


def _candidate_query(posting: JobPosting):
    """Indexed trigram candidate lookup, guarded to 'would beat self' rows.

    `title % :title` is served by `ix_job_posting_title_trgm` (the threshold
    is set per-transaction above — an explicit `similarity() >=` comparison
    would be sequential). Country is NULL-safe equal; only rows that are
    their own canonical may absorb a duplicate; the tuple comparison keeps
    the deterministic oldest-row winner (`fetched_at`, then `id`).
    """
    older = tuple_(JobPosting.fetched_at, JobPosting.id) < tuple_(posting.fetched_at, posting.id)
    country_condition = (
        JobPosting.country.is_(None)
        if posting.country is None
        else JobPosting.country == posting.country
    )
    return (
        select(JobPosting)
        .where(
            JobPosting.id != posting.id,
            JobPosting.canonical_id.is_(None),
            country_condition,
            JobPosting.title.op("%")(posting.title),
            older,
        )
        .order_by(JobPosting.fetched_at.asc(), JobPosting.id.asc())
        .limit(50)
    )


def _merge_into_canonical(canonical: JobPosting, duplicate: JobPosting) -> None:
    """Issue merge rules: freshest posted_at, richest description, URL record."""
    if duplicate.posted_at is not None and (
        canonical.posted_at is None or duplicate.posted_at > canonical.posted_at
    ):
        canonical.posted_at = duplicate.posted_at
    if duplicate.description and len(duplicate.description) > len(canonical.description or ""):
        canonical.description = duplicate.description
    entry = {"source": duplicate.source, "url": duplicate.url}
    merged = list(canonical.source_urls or [])
    if entry not in merged:
        merged.append(entry)
        canonical.source_urls = merged


async def dedupe_postings(session: AsyncSession, posting_ids: list[uuid.UUID]) -> int:
    """Group the given (just-upserted) postings into existing canonicals.

    Returns the number of postings that gained a `canonical_id`. Rows already
    grouped are skipped, so re-running over the same ids is a no-op.
    """
    if not posting_ids:
        return 0
    rows = (
        (await session.execute(select(JobPosting).where(JobPosting.id.in_(posting_ids))))
        .scalars()
        .all()
    )
    ordered = sorted(rows, key=lambda row: (row.fetched_at, row.id))
    await _set_similarity_threshold(session)
    grouped = 0
    for posting in ordered:
        if posting.canonical_id is not None:
            continue
        normalized_company = normalize_company(posting.company)
        if normalized_company is None:
            continue
        candidates = (await session.execute(_candidate_query(posting))).scalars().all()
        winner = next(
            (
                candidate
                for candidate in candidates
                if normalize_company(candidate.company) == normalized_company
            ),
            None,
        )
        if winner is None:
            continue
        posting.canonical_id = winner.id
        grouped += 1
        _merge_into_canonical(winner, posting)
    logger.info("ingestion.dedupe batch=%d grouped=%d", len(posting_ids), grouped)
    return grouped
