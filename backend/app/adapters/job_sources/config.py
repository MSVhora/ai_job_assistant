from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.adapters.job_sources.base import ConnectorConfigError, JobSearchQuery

DEFAULT_CONFIG_PATH = Path(__file__).parent / "connectors.yaml"

_PLACEHOLDER_KEYS = ("query", "location", "country", "results_wanted")

_OMIT = object()


class ActorConfig(BaseModel):
    name: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    actor_id: str = Field(min_length=1)
    external_id_field: str = Field(min_length=1)
    input: dict[str, object] = Field(default_factory=dict)


class ConnectorsConfig(BaseModel):
    sources: list[ActorConfig] = Field(default_factory=list)


def build_actor_input(actor: ActorConfig, query: JobSearchQuery) -> dict[str, object]:
    built: dict[str, object] = {}
    for key, value in actor.input.items():
        resolved = _resolve_value(value, query)
        if resolved is not _OMIT:
            built[key] = resolved
    return built


def _resolve_value(value: object, query: JobSearchQuery) -> object:
    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
        match value[1:-1]:
            case "query":
                return query.query
            case "location":
                return query.location if query.location is not None else _OMIT
            case "country":
                return query.country
            case "results_wanted":
                return query.results_wanted
    return value


def load_actor_configs(path: Path = DEFAULT_CONFIG_PATH) -> list[ActorConfig]:
    try:
        raw = yaml.safe_load(path.read_text())
    except OSError as exc:
        raise ConnectorConfigError(f"cannot read connector config {path}: {exc}") from exc
    try:
        config = ConnectorsConfig.model_validate(raw)
    except (ValidationError, TypeError) as exc:
        raise ConnectorConfigError(f"invalid connector config {path}: {exc}") from exc
    names = [actor.name for actor in config.sources]
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise ConnectorConfigError(f"duplicate source names in config: {sorted(duplicates)}")
    for actor in config.sources:
        _validate_placeholders(actor)
    return config.sources


def _validate_placeholders(actor: ActorConfig) -> None:
    for value in actor.input.values():
        if not isinstance(value, str):
            continue
        stripped = value.strip("{}")
        if value.startswith("{") and value.endswith("}") and stripped not in _PLACEHOLDER_KEYS:
            raise ConnectorConfigError(
                f"actor {actor.name}: unknown placeholder {{{stripped}}} "
                f"(supported: {_PLACEHOLDER_KEYS})"
            )
