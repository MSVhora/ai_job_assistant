"""Seed a synthetic demo dataset: one profile ("Jane Doe", no real resume data)
plus deterministic job postings and vector-scored matches — zero LLM/Apify
spend by default (--rerank opts into a real re-rank for rationales).

Run inside the API container (it has DB access; no Gemini key needed):

    docker cp backend/scripts/seed_demo.py ai_job_assistant-api-1:/tmp/
    docker exec ai_job_assistant-api-1 python /tmp/seed_demo.py [--postings 30] [--rerank]
    docker exec ai_job_assistant-api-1 python /tmp/seed_demo.py --reset   # remove demo data

Seeded postings carry the `demo-` external_id prefix so --reset never touches
real data. Do not run --reset while a background search is active.
"""

import argparse
import asyncio
import hashlib
import logging
import math
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from app.core.db import session_factory
from app.models import Candidate, JobPosting, Profile
from app.schemas.profile import StructuredProfile
from app.services import matching

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_demo")

DEMO_EMAIL = "jane@example.com"
DEMO_EXTERNAL_PREFIX = "demo-"
DEMO_SOURCES = ("adzuna", "apify_linkedin")


# Mirrors tests/fakes.py fake_vector(): deterministic embeddings so seeded
# postings score stably against the seeded profile without any LLM call.
def fake_vector(text: str, dim: int = 768) -> list[float]:
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    vector = [rng.uniform(-1.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


DEMO_PROFILE: dict[str, Any] = {
    "contact": {
        "full_name": "Jane Doe",
        "email": DEMO_EMAIL,
        "location": "Berlin",
        "country": "de",
        "links": [{"url": "https://github.com/janedoe", "label": None}],
    },
    "headline": "Senior Data Analyst",
    "skills": ["SQL", "Python", "Tableau", "dbt", "Airflow"],
    "experience": [
        {
            "company": "Acme Corp",
            "title": "Senior Data Analyst",
            "start_date": "Mar 2021",
            "end_date": None,
            "is_current": True,
            "bullets": ["Led reporting", "Built dashboards"],
        }
    ],
    "education": [{"institution": "TU Berlin", "degree": "MSc", "field": "Statistics"}],
}

POSTING_TEMPLATES: list[dict[str, Any]] = [
    {
        "title": "Senior Data Analyst",
        "company": "Nordwind Analytics",
        "location": "Berlin, Germany",
        "salary": (65000, 85000),
        "description": (
            "You will own reporting for our commercial teams: build and maintain "
            "dashboards in Tableau, write SQL against our warehouse, and partner "
            "with stakeholders to define metrics. Strong SQL and dashboarding "
            "experience required; Python is a plus."
        ),
    },
    {
        "title": "Analytics Engineer",
        "company": "Spree Digital",
        "location": "Berlin, Germany (hybrid)",
        "salary": (70000, 90000),
        "description": (
            "Shape the data platform: model data in dbt, orchestrate pipelines "
            "with Airflow, and ensure data quality end to end. You know SQL "
            "deeply and care about testing and documentation."
        ),
    },
    {
        "title": "BI Analyst - Growth",
        "company": "Kraftwerk Labs",
        "location": "Remote (EU)",
        "salary": (60000, 78000),
        "description": (
            "Support the growth team with experiment analysis and self-serve "
            "dashboards. Comfortable with SQL and Python for ad-hoc analysis; "
            "experience with product metrics preferred."
        ),
    },
    {
        "title": "Junior Data Analyst",
        "company": "Brandenburger Health",
        "location": "Potsdam, Germany",
        "salary": (45000, 55000),
        "description": (
            "Entry-level role supporting clinical reporting: extract data with "
            "SQL, prepare reports, and learn our data warehouse. Curiosity and "
            "attention to detail matter more than years of experience."
        ),
    },
    {
        "title": "Data Engineer - Pipeline Tools",
        "company": "Hafen Systems",
        "location": "Hamburg, Germany",
        "salary": (75000, 95000),
        "description": (
            "Build and operate batch pipelines in Airflow with heavy Python. "
            "You will also contribute to our internal ETL toolkit used by "
            "analysts across the company."
        ),
    },
    {
        "title": "Marketing Data Analyst",
        "company": "Linden Media",
        "location": "Berlin, Germany",
        "salary": (55000, 70000),
        "description": (
            "Own marketing performance reporting: SQL extraction, Tableau "
            "dashboards, and channel attribution analysis for the media team."
        ),
    },
    {
        "title": "Quantitative Analyst",
        "company": "Alster Capital",
        "location": "Hamburg, Germany (hybrid)",
        "salary": (85000, 110000),
        "description": (
            "Backtest trading strategies with Python, validate data pipelines, "
            "and communicate findings to portfolio managers. MSc in a "
            "quantitative field required."
        ),
    },
    {
        "title": "Data Analyst Internship",
        "company": "Spree Digital",
        "location": "Berlin, Germany",
        "salary": None,
        "description": (
            "Six-month internship supporting the analytics team: SQL queries, "
            "dashboard maintenance, and a capstone analysis project."
        ),
    },
]


async def _reset() -> None:
    async with session_factory() as session:
        profiles = (
            (
                await session.execute(
                    sa.select(Profile).where(
                        Profile.structured_profile["contact"]["email"].astext == DEMO_EMAIL
                    )
                )
            )
            .scalars()
            .all()
        )
        candidate_ids = {profile.candidate_id for profile in profiles}
        for profile in profiles:
            await session.delete(profile)
        await session.flush()
        for candidate_id in candidate_ids:
            remaining = await session.scalar(
                sa.select(sa.func.count())
                .select_from(Profile)
                .where(Profile.candidate_id == candidate_id)
            )
            if remaining == 0:
                await session.execute(sa.delete(Candidate).where(Candidate.id == candidate_id))
        demo_postings = (
            (
                await session.execute(
                    sa.select(JobPosting).where(
                        JobPosting.external_id.like(f"{DEMO_EXTERNAL_PREFIX}%")
                    )
                )
            )
            .scalars()
            .all()
        )
        for posting in demo_postings:
            await session.delete(posting)
        await session.commit()
        logger.info(
            "reset: removed %d profile(s), %d demo posting(s)", len(profiles), len(demo_postings)
        )


def _posting_rows(count: int) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        template = POSTING_TEMPLATES[index % len(POSTING_TEMPLATES)]
        source = DEMO_SOURCES[index % len(DEMO_SOURCES)]
        description = template["description"]
        salary = template["salary"]
        rows.append(
            {
                "source": source,
                "external_id": f"{DEMO_EXTERNAL_PREFIX}{source}-{index:03d}",
                "title": template["title"],
                "company": template["company"],
                "url": f"https://example.com/jobs/{index:03d}",
                "location": template["location"],
                "description": description,
                "embedding": fake_vector(f"{template['title']} {description}"),
                "posted_at": now - timedelta(days=index % 21),
                "salary_min": Decimal(salary[0]) if salary else None,
                "salary_max": Decimal(salary[1]) if salary else None,
                "currency": "EUR" if salary else None,
                "raw_payload": {"id": index, "demo": True},
            }
        )
    return rows


async def seed(count: int, *, rerank: bool) -> None:
    profile_data = StructuredProfile.model_validate(DEMO_PROFILE)
    async with session_factory() as session:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        profile = Profile(
            candidate_id=candidate.id,
            name=f"{profile_data.contact.full_name} (demo)",
            structured_profile=profile_data.model_dump(mode="json"),
        )
        session.add(profile)
        await session.flush()
        headline = profile_data.headline or profile_data.contact.full_name
        profile.embedding = fake_vector(headline)

        for row in _posting_rows(count):
            session.add(JobPosting(**row))
        await session.flush()

        scored = await matching.rescore_matches(session, profile, invalidate_rationales=True)
        await session.commit()
        logger.info("seeded profile=%s postings=%d matches=%d", profile.name, count, scored)

    if rerank:
        async with session_factory() as session:
            outcome = await matching.refresh_matches_for_profile(session, profile.id)
            await session.commit()
            logger.info("rerank: status=%s warning=%s", outcome.status, outcome.warning)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic demo data")
    parser.add_argument("--postings", type=int, default=30)
    parser.add_argument("--reset", action="store_true", help="remove demo data and exit")
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="run a real LLM re-rank after seeding (needs the Gemini key)",
    )
    args = parser.parse_args()
    if args.reset:
        await _reset()
    else:
        await seed(args.postings, rerank=args.rerank)


if __name__ == "__main__":
    asyncio.run(main())
