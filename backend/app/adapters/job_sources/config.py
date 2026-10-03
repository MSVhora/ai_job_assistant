from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.adapters.job_sources.base import (
    ConnectorConfigError,
    JobSearchQuery,
    SourceFilterDecl,
    date_posted_bucket,
)
from app.core.config import get_settings

DEFAULT_CONFIG_PATH = Path(__file__).parent / "connectors.yaml"

_PLACEHOLDER_KEYS = (
    "query",
    "keywords",
    "location",
    "country",
    "results_wanted",
    "date_posted_bucket",
)

_OPTION_PLACEHOLDER_PREFIX = "option:"

_OMIT = object()


class ActorConfig(BaseModel):
    name: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    actor_id: str = Field(min_length=1)
    external_id_field: str = Field(min_length=1)
    input: dict[str, object] = Field(default_factory=dict)
    filters: list[SourceFilterDecl] = Field(default_factory=list[SourceFilterDecl])


class ConnectorsConfig(BaseModel):
    sources: list[ActorConfig] = Field(default_factory=list[ActorConfig])


def build_actor_input(actor: ActorConfig, query: JobSearchQuery) -> dict[str, object]:
    built: dict[str, object] = {}
    for key, value in actor.input.items():
        resolved = _resolve_value(value, query)
        if resolved is not _OMIT:
            built[key] = resolved
    return built


def _resolve_value(value: object, query: JobSearchQuery) -> object:
    plan = query.term_plan
    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
        token = value[1:-1]
        if token.startswith(_OPTION_PLACEHOLDER_PREFIX):
            option_key = token.removeprefix(_OPTION_PLACEHOLDER_PREFIX)
            return query.options.get(option_key, _OMIT)
        match token:
            case "query":
                return query.query
            case "keywords":
                return plan.keywords if plan is not None and plan.keywords is not None else _OMIT
            case "location":
                fallback = _OMIT if query.location is None else query.location
                return plan.location if plan is not None and plan.location is not None else fallback
            case "country":
                return query.country
            case "results_wanted":
                max_results = get_settings().max_apify_results_per_run
                return min(query.results_wanted, max_results)
            case "date_posted_bucket":
                bucket = date_posted_bucket(query.max_days_old)
                return (
                    plan.date_posted
                    if plan is not None and plan.date_posted is not None
                    else bucket
                )
            case _:
                pass
    return value


def load_actor_configs(path: Path = DEFAULT_CONFIG_PATH) -> list[ActorConfig]:
    try:
        raw = yaml.safe_load(path.read_text())
    except OSError as exc:
        msg = f"cannot read connector config {path}: {exc}"
        raise ConnectorConfigError(msg) from exc
    try:
        config = ConnectorsConfig.model_validate(raw)
    except (ValidationError, TypeError) as exc:
        msg = f"invalid connector config {path}: {exc}"
        raise ConnectorConfigError(msg) from exc
    names = [actor.name for actor in config.sources]
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        msg = f"duplicate source names in config: {sorted(duplicates)}"
        raise ConnectorConfigError(msg)
    for actor in config.sources:
        _validate_placeholders(actor)
    return config.sources


def _validate_placeholders(actor: ActorConfig) -> None:
    declared_option_keys = {decl.key for decl in actor.filters}
    for value in actor.input.values():
        if not isinstance(value, str):
            continue
        stripped = value.strip("{}")
        if not (value.startswith("{") and value.endswith("}")):
            continue
        if stripped.startswith(_OPTION_PLACEHOLDER_PREFIX):
            option_key = stripped.removeprefix(_OPTION_PLACEHOLDER_PREFIX)
            if option_key not in declared_option_keys:
                msg = (
                    f"actor {actor.name}: placeholder {{{stripped}}} declares no filter; "
                    f"declared filters: {_describe_filters(actor)}"
                )
                raise ConnectorConfigError(msg)
        elif stripped not in _PLACEHOLDER_KEYS:
            msg = (
                f"actor {actor.name}: unknown placeholder {{{stripped}}} "
                f"(supported: {_PLACEHOLDER_KEYS} or {{option:<declared filter key>}})"
            )
            raise ConnectorConfigError(msg)


def _describe_filters(actor: ActorConfig) -> str:
    if not actor.filters:
        return "(none)"
    return ", ".join(decl.key for decl in actor.filters)
