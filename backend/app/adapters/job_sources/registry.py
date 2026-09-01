from app.adapters.job_sources.adzuna import AdzunaJobSource
from app.adapters.job_sources.base import JobSource

_REGISTRY: tuple[JobSource, ...] = (AdzunaJobSource(),)


def all_sources() -> tuple[JobSource, ...]:
    return _REGISTRY


def get_source(name: str) -> JobSource | None:
    return next((source for source in _REGISTRY if source.name == name), None)


def enabled_sources() -> list[JobSource]:
    return [source for source in _REGISTRY if source.is_configured()]
