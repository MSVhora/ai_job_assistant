import re
from pathlib import Path

from app.core.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
NON_SETTINGS_KEYS = {
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "NEXT_PUBLIC_API_BASE_URL",
}
KEY_LINE = re.compile(r"^#?\s*([A-Z][A-Z0-9_]*)=")


def _example_keys() -> set[str]:
    keys: set[str] = set()
    for line in ENV_EXAMPLE.read_text().splitlines():
        match = KEY_LINE.match(line)
        if match:
            keys.add(match.group(1))
    return keys


def test_env_example_matches_settings_fields() -> None:
    settings_keys = {name.upper() for name in Settings.model_fields}
    example_keys = _example_keys() - NON_SETTINGS_KEYS

    missing = sorted(settings_keys - example_keys)
    unknown = sorted(example_keys - settings_keys)

    assert not missing, f".env.example is missing settings: {missing}"
    assert not unknown, f".env.example has keys that are not settings: {unknown}"
