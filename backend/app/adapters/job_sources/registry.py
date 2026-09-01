from app.adapters.job_sources.adzuna import AdzunaJobSource
from app.adapters.job_sources.apify import ApifyActorSource
from app.adapters.job_sources.base import ConnectorConfigError, JobSource
from app.adapters.job_sources.config import load_actor_configs


def _build_registry() -> tuple[JobSource, ...]:
    sources: tuple[JobSource, ...] = (AdzunaJobSource(),)
    for actor_config in load_actor_configs():
        sources += (ApifyActorSource(actor_config),)
    names = [source.name for source in sources]
    if len(set(names)) != len(names):
        raise ConnectorConfigError(f"duplicate source names in registry: {names}")
    return sources


_REGISTRY: tuple[JobSource, ...] = _build_registry()


def all_sources() -> tuple[JobSource, ...]:
    return _REGISTRY


def get_source(name: str) -> JobSource | None:
    return next((source for source in all_sources() if source.name == name), None)
