import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def banned_apis() -> set[str]:
    config = tomllib.loads(PYPROJECT.read_text())
    return set(config["tool"]["ruff"]["lint"]["flake8-tidy-imports"]["banned-api"])


def test_config_and_provider_sdk_bans_stay_enforced_by_ruff() -> None:
    assert {
        "os.getenv",
        "os.environ",
        "openai",
        "anthropic",
        "google.generativeai",
    } <= banned_apis()
