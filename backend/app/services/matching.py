from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, select

from app.models import JobPosting
from app.schemas.matching import MatchFilters


def ranked_postings_query(
    profile_embedding: list[float], filters: MatchFilters
) -> Select[tuple[JobPosting, float]]:
    """Hard-filtered, cosine-ranked posting query (#9 building block).

    Postings without an embedding are excluded from vector ranking; the match
    pipeline (#10) consumes the returned select unchanged.
    """
    distance = JobPosting.embedding.cosine_distance(profile_embedding)
    query: Select[tuple[JobPosting, float]] = (
        select(JobPosting, distance.label("vector_distance"))
        .where(JobPosting.embedding.is_not(None))
        .order_by(distance.asc())
    )
    if filters.location is not None:
        escaped = filters.location.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(JobPosting.location.ilike(f"%{escaped}%", escape="\\"))
    if filters.remote_type is not None:
        query = query.where(JobPosting.remote_type == filters.remote_type)
    if filters.job_type is not None:
        query = query.where(JobPosting.job_type == filters.job_type)
    if filters.posted_within_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=filters.posted_within_days)
        query = query.where(JobPosting.posted_at >= cutoff)
    return query
