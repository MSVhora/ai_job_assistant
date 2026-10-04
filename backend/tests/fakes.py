import hashlib
import json
import math
import random
import re
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
from app.schemas.resume_document import (
    Basics,
    Bullet,
    BulletCheck,
    EducationEntry,
    ResumeContent,
    WorkEntry,
)
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
        permissions: list[str] | None = None,
    ) -> None:
        self.scripts = scripts or {}
        self.configured = configured
        self.scopes = scopes or []
        self.permissions = permissions or []
        self.seen: list[Any] = []

    def is_configured(self) -> bool:
        return self.configured

    async def identify(self) -> Any:
        from app.schemas.evidence import SourceIdentity

        return SourceIdentity(login="ada", permissions=self.permissions)

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


def golden_profile() -> StructuredProfile:
    """The scrubbed 'Ada' profile with one deliberate instance of every conflict kind."""
    import json
    from pathlib import Path

    path = Path(__file__).parent / "eval" / "golden" / "profile.json"
    return StructuredProfile.model_validate(json.loads(path.read_text()))


def transient_achievement(**fields: Any) -> Any:
    """An in-memory approved achievement for pure (no database) reconciliation tests."""
    import uuid
    from datetime import date

    from app.models import Achievement, AchievementStatus

    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "title": "Faster nightly import",
        "status": AchievementStatus.approved,
        "metrics": [],
        "skills": [],
        "employer_ref": None,
        "project_key": None,
        "time_start": date(2021, 6, 1),
        "time_end": None,
    }
    return Achievement(**{**defaults, **fields})


ACME = {"company": "Acme Corp", "start_date": "Jan 2019", "source": "user"}
BETA = {"company": "Beta Inc", "start_date": "Mar 2022", "source": "user"}
SIDE = {"company": "Side Gig", "start_date": "Jun 2021", "source": "user"}
WORLD_PROFILE: dict[str, Any] = {
    "contact": {"full_name": "Jane Roe", "email": "jane@example.com", "phone": "+44 20 7946 0001"},
    "headline": "Data platform engineer",
    "skills": ["Python", "SQL"],
    "experience": [
        {
            "company": "Beta Inc",
            "title": "Engineer",
            "start_date": "Mar 2022",
            "end_date": None,
            "is_current": True,
            "bullets": ["Owns the deploy tooling"],
        },
        {
            "company": "Acme Corp",
            "title": "Senior Engineer",
            "start_date": "Jan 2019",
            "end_date": "Dec 2021",
            "is_current": False,
            "bullets": ["Built reports"],
        },
    ],
    "projects": [{"name": "pipeline-kit", "bullets": ["Wrote a small ETL toolkit"]}],
}
SIDE_ROLE: dict[str, Any] = {
    "company": "Side Gig",
    "title": "Consultant",
    "start_date": "Jun 2021",
    "end_date": "Sep 2021",
    "is_current": False,
    "bullets": ["Advised on warehouses"],
}
WORLD_ACHIEVEMENTS: list[dict[str, Any]] = [
    {
        "key": "import",
        "title": "Faster nightly import",
        "employer_ref": ACME,
        "body": "Cut the nightly import from 42 minutes to 9 minutes by batching writes in Python "
        "against PostgreSQL",
        "metrics": [
            {"text": "42 minutes to 9 minutes", "source_quote": "q", "verified": "evidence"}
        ],
        "skills": ["Python", "PostgreSQL"],
        "difficulty": 4,
        "impact_type": "performance",
        "start": (2020, 5, 1),
    },
    {
        "key": "retry",
        "title": "Retry budget for the loader",
        "employer_ref": ACME,
        "body": "Contributed a retry budget for the loader",
        "skills": ["Python"],
        "difficulty": 2,
        "impact_type": "reliability",
        "start": (2020, 8, 1),
    },
    {
        "key": "rollout",
        "title": "Kubernetes rollout",
        "employer_ref": BETA,
        "body": "Deployed the services with Helm charts to our cluster",
        "skills": ["Kubernetes"],
        "difficulty": 4,
        "impact_type": "scale",
        "start": (2023, 2, 1),
    },
    {
        "key": "docs",
        "title": "Docs generator",
        "employer_ref": BETA,
        "body": "Wrote a docs generator for the internal API",
        "skills": ["Python"],
        "difficulty": 2,
        "impact_type": "other",
        "start": (2023, 6, 1),
    },
    {
        "key": "toolkit",
        "title": "Streaming toolkit",
        "project_key": "ada/pipeline-kit",
        "body": "Built a streaming toolkit with Kafka consumers",
        "skills": ["Kafka"],
        "difficulty": 3,
        "impact_type": "scale",
        "start": (2022, 4, 1),
    },
]


async def seed_resume_world(
    *,
    extra: "list[dict[str, Any]] | None" = None,
    with_side_role: bool = False,
    private: "set[str] | None" = None,
    embeddings: bool = False,
) -> dict[str, Any]:
    """A candidate, a two-role profile and approved achievements, each with kept evidence."""
    from datetime import UTC, date, datetime

    from app.core.db import session_factory
    from app.models import (
        Achievement,
        AchievementEvidence,
        AchievementStatus,
        Candidate,
        EvidenceItem,
        EvidenceItemStatus,
        EvidenceKind,
        Profile,
    )

    profile_json = {**WORLD_PROFILE}
    if with_side_role:
        profile_json = {**profile_json, "experience": [*WORLD_PROFILE["experience"], SIDE_ROLE]}
    ids: dict[str, Any] = {}
    async with session_factory() as session:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        profile = Profile(candidate_id=candidate.id, name="Jane", structured_profile=profile_json)
        session.add(profile)
        await session.flush()
        for spec in [*WORLD_ACHIEVEMENTS, *(extra or [])]:
            year, month, day = spec["start"]
            is_private = spec["key"] in (private or set())
            item = EvidenceItem(
                candidate_id=candidate.id,
                kind=EvidenceKind.note,
                external_id=f"ev-{spec['key']}",
                project_key=spec.get("project_key"),
                title=spec["title"],
                body=spec["body"],
                occurred_at=datetime(year, month, day, tzinfo=UTC),
                status=EvidenceItemStatus.kept,
                is_private=is_private,
                content_hash=spec["key"].ljust(64, "0"),
            )
            session.add(item)
            await session.flush()
            achievement = Achievement(
                candidate_id=candidate.id,
                status=AchievementStatus.approved,
                title=spec["title"],
                situation="Situation",
                task="Task",
                action=spec["body"],
                metrics=spec.get("metrics", []),
                skills=spec["skills"],
                impact_type=spec["impact_type"],
                difficulty=spec["difficulty"],
                project_key=spec.get("project_key"),
                employer_ref=spec.get("employer_ref"),
                time_start=date(year, month, day),
                embedding=fake_vector(spec["title"]) if embeddings else None,
                derived_from_private=is_private,
            )
            session.add(achievement)
            await session.flush()
            session.add(
                AchievementEvidence(achievement_id=achievement.id, item_id=item.id, role="primary")
            )
            ids[spec["key"]] = achievement.id
        ids["candidate"] = candidate.id
        ids["profile"] = profile.id
        await session.commit()
    return ids


class FakeResumeLLM:
    """Scripted completion handler for the JD, bullet-writer and judge prompts."""

    def __init__(
        self,
        *,
        jd: "dict[str, Any] | None" = None,
        texts: "dict[str, str] | None" = None,
        writer: "Callable[[str, dict[str, Any], bool], str | None] | None" = None,
        judge_fail: "set[str] | None" = None,
        drop_first_write: bool = False,
    ) -> None:
        self.drop_first_write = drop_first_write
        self.jd = jd or {"must_haves": [], "nice_to_haves": [], "keywords": []}
        self.texts = texts or {}
        self.writer = writer
        self.judge_fail = judge_fail or set()
        self.calls: list[dict[str, Any]] = []

    def count(self, kind: str) -> int:
        return sum(1 for call in self.calls if call["kind"] == kind)

    def items(self, title: str) -> "list[dict[str, Any]]":
        """Every writer request item (facts) for the achievement with this title."""
        return [
            item
            for call in self.calls
            if call["kind"] == "write"
            for item in call["facts"].values()
            if item["title"] == title
        ]

    def __call__(self, **kwargs: Any) -> object:
        system = kwargs["messages"][0]["content"]
        prompt = kwargs["messages"][-1]["content"]
        if "analyse a job description" in system:
            self.calls.append({"kind": "jd", "prompt": prompt})
            return llm_response(json.dumps(self.jd))
        if "write resume bullets" in system:
            return llm_response(json.dumps(self._write(prompt)))
        if "check resume bullets" in system:
            return llm_response(json.dumps(self._judge(prompt)))
        msg = "unexpected prompt"
        raise AssertionError(msg)

    def _write(self, prompt: str) -> dict[str, Any]:
        current = "present tense" in prompt
        facts = {
            match.group(1): json.loads(match.group(2))
            for match in re.finditer(r"Item (A\d+):\n(\{.*?\n\})\n<<<EVIDENCE", prompt, re.DOTALL)
        }
        self.calls.append({"kind": "write", "facts": facts, "current": current})
        if self.drop_first_write and self.count("write") == 1:
            return {"bullets": []}
        bullets: list[dict[str, Any]] = []
        for key, item in facts.items():
            text = self.writer(key, item, current) if self.writer else None
            if text is None:
                text = self.texts.get(item["title"]) or (
                    f"{'Deliver' if current else 'Delivered'} {item['title'].lower()} "
                    "for the platform"
                )
            if text == "":
                bullets.append({"key": key, "text": "", "unsupported_reason": "not in evidence"})
            else:
                bullets.append({"key": key, "text": text, "evidence_ids": ["E1"]})
        return {"bullets": bullets}

    def _judge(self, prompt: str) -> dict[str, Any]:
        claims = re.findall(r"Bullet (A\d+): (.*)", prompt)
        self.calls.append({"kind": "judge", "claims": claims})
        verdicts = [
            {
                "key": key,
                "entailed": not any(marker in text for marker in self.judge_fail),
                "reason": "unsupported claim",
            }
            for key, text in claims
        ]
        return {"verdicts": verdicts}


def synthetic_resume(
    roles: int,
    per_role: int,
    *,
    seed: int = 0,
    words: int = 8,
    checks: dict[str, BulletCheck] | None = None,
    pinned: set[str] | None = None,
) -> ResumeContent:
    """A resume with `roles` jobs of `per_role` written bullets with distinct random scores.

    Bullet ids are `r{role}b{index}`; `checks` overrides a bullet's check, `pinned` pins ids.
    """
    rng = random.Random(seed)
    scores = rng.sample(range(1, 10_000), roles * per_role)
    work: list[WorkEntry] = []
    for role in range(roles):
        bullets = [
            Bullet(
                id=f"r{role}b{index}",
                text=" ".join(
                    f"w{rng.randint(0, 999)}" for _ in range(rng.randint(words // 2 + 1, words))
                )
                + f" r{role}b{index}",
                score=scores[role * per_role + index] / 10_000,
                check=(checks or {}).get(f"r{role}b{index}", "passed"),
                pinned=f"r{role}b{index}" in (pinned or set()),
            )
            for index in range(per_role)
        ]
        work.append(
            WorkEntry(
                id=f"role{role}",
                company=f"Company {role}",
                title="Engineer",
                start_date=f"{2010 + role}-01",
                end_date=f"{2011 + role}-01",
                highlights=bullets,
            )
        )
    return ResumeContent(
        basics=Basics(full_name="Ada Lovelace", email="ada@example.com", phone="555 0100"),
        skills=[f"Skill{n}" for n in range(6)],
        work=work,
        education=[EducationEntry(institution="Analytical College", degree="BSc", field="Maths")],
    )


async def seed_employers(*companies: str) -> None:
    """A profile whose experience has one entry per given company name."""
    from sqlalchemy import select

    from app.core.db import session_factory
    from app.models import Profile

    await seed_profile_light()
    async with session_factory() as session:
        profile = (await session.execute(select(Profile))).scalars().first()
        assert profile is not None
        data: dict[str, Any] = dict(profile.structured_profile)
        data["experience"] = [
            {
                "company": company,
                "title": "Engineer",
                "start_date": f"Jan 20{10 + index}",
                "end_date": f"Dec 20{10 + index}",
                "bullets": [],
            }
            for index, company in enumerate(companies)
        ]
        profile.structured_profile = data
        await session.commit()
