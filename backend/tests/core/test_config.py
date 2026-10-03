import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_evidence_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.github_token is None
    assert settings.github_api_url == "https://api.github.com"
    assert settings.github_max_requests_per_run == 1500
    assert settings.github_min_remaining_pct == 10
    assert settings.evidence_lookback_years == 6
    assert "dependabot" in settings.evidence_bot_logins


def test_blank_github_token_becomes_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "  ")

    assert Settings(_env_file=None).github_token is None


def test_github_token_is_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_example")

    assert Settings(_env_file=None).github_token == "ghp_example"  # noqa: S105


def test_evidence_bot_logins_parse_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVIDENCE_BOT_LOGINS", '["ci-robot","renovate"]')

    assert Settings(_env_file=None).evidence_bot_logins == ["ci-robot", "renovate"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("github_max_requests_per_run", 0),
        ("github_max_requests_per_run", 5001),
        ("github_min_remaining_pct", -1),
        ("github_min_remaining_pct", 91),
        ("evidence_lookback_years", 0),
        ("evidence_lookback_years", 31),
    ],
)
def test_evidence_settings_reject_out_of_bounds(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
