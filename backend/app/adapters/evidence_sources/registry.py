from app.adapters.evidence_sources.base import EvidenceSource, EvidenceSourceConfigError

_REGISTRY: dict[str, EvidenceSource] = {}


def registered_sources() -> tuple[EvidenceSource, ...]:
    return tuple(_REGISTRY.values())


def get_source(name: str) -> EvidenceSource:
    try:
        return _REGISTRY[name]
    except KeyError:
        msg = f"unknown evidence source: {name!r}"
        raise EvidenceSourceConfigError(msg) from None
