from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import litellm

VALID_PROFILE: dict[str, Any] = {
    "contact": {
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "location": "Berlin",
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
