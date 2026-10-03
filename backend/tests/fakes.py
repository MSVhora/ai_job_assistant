import hashlib
import math
import random
from collections.abc import Callable
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import litellm

from app.adapters.job_sources.base import (
    ConnectorError,
    JobPostingData,
    JobSearchQuery,
    RawJobPosting,
    SourceFilterDecl,
)
from app.schemas.profile import StructuredProfile
from app.services import profile_derivation

if TYPE_CHECKING:
    import uuid

VALID_PROFILE: dict[str, Any] = {
    "contact": {
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "location": "Berlin",
        "country": "de",
        "links": [
            {"url": "https://www.linkedin.com/in/janedoe", "label": None},
            {"url": "https://github.com/janedoe", "label": None},
            {"url": "https://janedoe.dev", "label": None},
        ],
    },
    "headline": "Senior Data Analyst",
    "skills": ["SQL", "Python", "Tableau"],
    "experience": [
        {
            "company": "Acme Corp",
            "title": "Senior Data Analyst",
            "start_date": "Mar 2021",
            "end_date": "Dec 2022",
            "is_current": False,
            "bullets": ["Led reporting", "Built dashboards"],
        }
    ],
    "projects": [
        {
            "name": "OpenPipeline",
            "url": "https://github.com/janedoe/openpipeline",
            "bullets": ["Built ETL toolkit"],
            "technologies": ["Python", "dbt"],
        }
    ],
    "education": [{"institution": "TU Berlin", "degree": "MSc", "field": "Statistics"}],
    "certifications": [{"name": "AWS Data Engineer", "issuer": "AWS", "issued_date": "2022"}],
    "awards": [
        {"title": "Winner, HackX 2023", "issuer": "HackX", "issued_date": "2023"},
        {"title": "Employee of the Year 2022"},
    ],
    "extra_sections": [
        {"title": "Publications", "entries": ["Doe J. Efficient Pipelines, 2022"]},
        {"title": "Languages", "entries": ["English - native", "German - fluent"]},
    ],
}


def derived_valid_profile() -> dict[str, Any]:
    """VALID_PROFILE as the extraction/save pipeline stores it post-#32."""
    profile = StructuredProfile.model_validate(VALID_PROFILE)
    profile_derivation.apply_derived_fields(profile)
    return profile.model_dump(mode="json")


def llm_response(
    content: str, *, prompt_tokens: int = 10, completion_tokens: int = 5
) -> SimpleNamespace:
    return SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


class ProviderError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"provider error {status_code}")
        self.status_code = status_code


def install_acompletion(monkeypatch: Any, handler: Callable[..., object]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    async def _spy(**kwargs: Any) -> object:
        calls.append(kwargs)
        result = handler(**kwargs)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(litellm, "acompletion", _spy)
    return calls


def fake_posting(external_id: str, **overrides: Any) -> JobPostingData:
    defaults: dict[str, Any] = {
        "external_id": external_id,
        "title": f"Job {external_id}",
        "raw_payload": {"id": external_id},
    }
    return JobPostingData(**{**defaults, **overrides})


class FakeJobSource:
    def __init__(
        self,
        name: str = "fake",
        *,
        configured: bool = True,
        disclosure_required: bool = False,
        supports_exclusions: bool = False,
        postings: list[JobPostingData] | None = None,
        error: Exception | None = None,
        filters: list[SourceFilterDecl] | None = None,
    ) -> None:
        self.name = name
        self.is_official_api = False
        self.disclosure_required = disclosure_required
        self.supports_exclusions = supports_exclusions
        self._configured = configured
        self._postings = postings or []
        self._error = error
        self._filters = filters or []
        self.queries: list[JobSearchQuery] = []

    def filters(self) -> list[SourceFilterDecl]:
        return self._filters

    def is_configured(self) -> bool:
        return self._configured

    async def search(self, query: JobSearchQuery) -> list[RawJobPosting]:
        self.queries.append(query)
        if self._error is not None:
            raise self._error
        return [
            RawJobPosting(external_id=posting.external_id, payload=posting.raw_payload)
            for posting in self._postings
        ]

    def normalize(self, raw: RawJobPosting) -> JobPostingData:
        for posting in self._postings:
            if posting.external_id == raw.external_id:
                return posting
        msg = f"un-mappable posting {raw.external_id}"
        raise ConnectorError(msg)


def fake_vector(text: str, dim: int = 768) -> list[float]:
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    vector = [rng.uniform(-1.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def embedding_response(vectors: list[list[float]], *, prompt_tokens: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        data=[{"embedding": vector} for vector in vectors],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens),
    )


def install_aembedding(monkeypatch: Any, handler: Callable[..., object]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    async def _spy(**kwargs: Any) -> object:
        calls.append(kwargs)
        result = handler(**kwargs)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(litellm, "aembedding", _spy)
    return calls


async def seed_profile_light(name: str = "Seeker") -> Any:
    """Create a profile (no embedding) and return its id."""

    from sqlalchemy import select

    from app.core.db import session_factory
    from app.models import Candidate, Profile
    from app.schemas.profile import StructuredProfile

    async with session_factory() as session:
        result = await session.execute(select(Candidate).limit(1))
        candidate = result.scalars().first()
        if candidate is None:
            candidate = Candidate()
            session.add(candidate)
            await session.flush()
        profile = Profile(
            candidate_id=candidate.id,
            name=name,
            structured_profile=StructuredProfile.model_validate(VALID_PROFILE).model_dump(
                mode="json"
            ),
        )
        session.add(profile)
        await session.flush()
        profile_id: uuid.UUID = profile.id
        await session.commit()
        return profile_id


class ScriptedEvidenceSource:
    """Evidence source driven by a per-scope script of pages, errors, or blocking events."""

    name = "github"

    def __init__(
        self,
        scripts: dict[str, list[Any]] | None = None,
        *,
        configured: bool = True,
        scopes: list[Any] | None = None,
    ) -> None:
        self.scripts = scripts or {}
        self.configured = configured
        self.scopes = scopes or []
        self.seen: list[Any] = []

    def is_configured(self) -> bool:
        return self.configured

    async def identify(self) -> Any:
        from app.schemas.evidence import SourceIdentity

        return SourceIdentity(login="ada")

    async def list_scopes(self) -> list[Any]:
        return self.scopes

    async def sync_scope(self, scope: Any) -> Any:
        import asyncio

        self.seen.append(scope)
        for step in self.scripts.get(scope.ref, []):
            if isinstance(step, Exception):
                raise step
            if isinstance(step, asyncio.Event):
                await step.wait()
                continue
            yield step

    def normalize(self, raw: Any) -> Any:
        raise NotImplementedError


def install_evidence_source(monkeypatch: Any, source: ScriptedEvidenceSource) -> None:
    from app.adapters.evidence_sources import registry

    monkeypatch.setitem(registry._FACTORIES, source.name, lambda: source)


async def seed_evidence_chunk(
    *,
    bodies: list[str],
    text: str | None = None,
    project_key: str = "ada/engine",
    private: bool = False,
    candidate_id: "uuid.UUID | None" = None,
    when: Any = None,
    scope_employer: dict[str, Any] | None = None,
) -> tuple["uuid.UUID", "uuid.UUID", list["uuid.UUID"]]:
    """Seed one candidate-owned chunk with one commit item per body; returns the ids."""
    from datetime import UTC, datetime

    from app.core.db import session_factory
    from app.models import (
        Candidate,
        EvidenceChunk,
        EvidenceChunkItem,
        EvidenceItem,
        EvidenceKind,
        EvidenceScope,
        EvidenceSourceAccount,
    )

    stamp = when or datetime(2024, 6, 1, tzinfo=UTC)
    chunk_text = text if text is not None else "\n".join(bodies)
    async with session_factory() as session:
        if candidate_id is None:
            candidate = Candidate()
            session.add(candidate)
            await session.flush()
            candidate_id = candidate.id
        scope_id = None
        if scope_employer is not None:
            account = EvidenceSourceAccount(candidate_id=candidate_id, kind="github")
            session.add(account)
            await session.flush()
            scope = EvidenceScope(
                source_id=account.id, ref=project_key, enabled=True, employer_ref=scope_employer
            )
            session.add(scope)
            await session.flush()
            scope_id = scope.id
        chunk = EvidenceChunk(
            candidate_id=candidate_id,
            kind="commit_cluster",
            project_key=project_key,
            title=f"{project_key}: {len(bodies)} commits",
            text=chunk_text,
            token_count=len(chunk_text) // 4,
            content_hash=hashlib.sha256(chunk_text.encode()).hexdigest(),
            chunker_version="chunker_v1",
            contains_private=private,
            time_start=stamp,
            time_end=stamp,
        )
        session.add(chunk)
        await session.flush()
        item_ids: list[uuid.UUID] = []
        for index, body in enumerate(bodies):
            item = EvidenceItem(
                candidate_id=candidate_id,
                scope_id=scope_id,
                kind=EvidenceKind.commit,
                external_id=f"{index:02d}-{hashlib.sha256(f'{chunk.id}:{index}'.encode()).hexdigest()}",
                project_key=project_key,
                title=body[:60],
                body=body,
                occurred_at=stamp,
                is_private=private,
                content_hash=hashlib.sha256(body.encode()).hexdigest(),
            )
            session.add(item)
            await session.flush()
            session.add(EvidenceChunkItem(chunk_id=chunk.id, item_id=item.id))
            item_ids.append(item.id)
        await session.commit()
        return candidate_id, chunk.id, item_ids


async def seed_achievement(
    candidate_id: "uuid.UUID",
    *,
    item_ids: "list[uuid.UUID] | None" = None,
    status: str = "draft",
    title: str = "Faster nightly import",
    metrics: "list[dict[str, Any]] | None" = None,
    flags: "list[str] | None" = None,
    project_key: str | None = "ada/engine",
    embedding: "list[float] | None" = None,
    time_start: Any = None,
    time_end: Any = None,
    difficulty: int = 3,
    private: bool = False,
    stale: bool = False,
    skills: "list[str] | None" = None,
) -> "uuid.UUID":
    """Seed an achievement linked (first one primary) to the given evidence items."""
    from datetime import UTC, date, datetime

    from app.core.db import session_factory
    from app.models import Achievement, AchievementEvidence, AchievementStatus

    async with session_factory() as session:
        achievement = Achievement(
            candidate_id=candidate_id,
            status=AchievementStatus(status),
            title=title,
            situation="Situation",
            task="Task",
            action="Action",
            result="Result",
            metrics=metrics or [],
            skills=skills or [],
            impact_type="performance",
            difficulty=difficulty,
            project_key=project_key,
            embedding=embedding,
            time_start=time_start or date(2024, 6, 1),
            time_end=time_end,
            review_flags=flags or [],
            derived_from_private=private,
            evidence_stale_at=datetime.now(UTC) if stale else None,
        )
        session.add(achievement)
        await session.flush()
        for index, item_id in enumerate(item_ids or []):
            session.add(
                AchievementEvidence(
                    achievement_id=achievement.id,
                    item_id=item_id,
                    role="primary" if index == 0 else "supporting",
                )
            )
        await session.commit()
        return achievement.id
