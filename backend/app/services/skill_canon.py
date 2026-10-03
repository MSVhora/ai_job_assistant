from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

import yaml

from app.adapters.job_sources.base import json_array, json_object

ALIASES_PATH = Path(__file__).resolve().parent.parent / "resources" / "skill_aliases.yaml"
MAX_SKILLS = 12


@lru_cache(maxsize=1)
def load_aliases() -> dict[str, str]:
    """alias (lowercase) -> canonical name, including each canonical name itself."""
    raw = json_object(yaml.safe_load(ALIASES_PATH.read_text())) or {}
    aliases: dict[str, str] = {}
    for canonical, names in raw.items():
        aliases[canonical.lower()] = canonical
        for name in json_array(names) or []:
            if isinstance(name, str):
                aliases[name.strip().lower()] = canonical
    return aliases


def canonicalize(skills: Iterable[str], profile_skills: Iterable[str] = ()) -> list[str]:
    """Canonical, de-duplicated tags; a skill the user already lists keeps their spelling."""
    aliases = load_aliases()
    own = {skill.strip().lower(): skill.strip() for skill in profile_skills if skill.strip()}
    result: list[str] = []
    seen: set[str] = set()
    for skill in skills:
        cleaned = skill.strip()
        if not cleaned:
            continue
        canonical = aliases.get(cleaned.lower(), cleaned)
        final = own.get(canonical.lower(), canonical)
        if final.lower() not in seen:
            seen.add(final.lower())
            result.append(final)
    return result[:MAX_SKILLS]
