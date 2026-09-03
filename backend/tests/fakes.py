import hashlib
import math
import random
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import litellm

from app.adapters.job_sources.base import (
    ConnectorError,
    JobPostingData,
    JobSearchQuery,
    RawJobPosting,
)

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
            "end_date": None,
            "is_current": True,
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
    ) -> None:
        self.name = name
        self.is_official_api = False
        self.disclosure_required = disclosure_required
        self.supports_exclusions = supports_exclusions
        self._configured = configured
        self._postings = postings or []
        self._error = error
        self.queries: list[JobSearchQuery] = []

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
        raise ConnectorError(f"un-mappable posting {raw.external_id}")


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
