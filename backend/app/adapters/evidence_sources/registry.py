from collections.abc import Callable

from app.adapters.evidence_sources.base import EvidenceSource, EvidenceSourceConfigError
from app.adapters.evidence_sources.github import GitHubSource

# Factories, not instances: a sync run owns per-run state (request budget, identity cache).
_FACTORIES: dict[str, Callable[[], EvidenceSource]] = {"github": GitHubSource}


def registered_sources() -> tuple[EvidenceSource, ...]:
    return tuple(factory() for factory in _FACTORIES.values())


def get_source(name: str) -> EvidenceSource:
    try:
        factory = _FACTORIES[name]
    except KeyError:
        msg = f"unknown evidence source: {name!r}"
        raise EvidenceSourceConfigError(msg) from None
    return factory()
