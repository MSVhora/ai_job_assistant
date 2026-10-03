import pytest

from app.services.redaction import redact, restore

SHA = "9fceb02d0ae598e95dc970b74767f19372d61af8"
UUID = "123e4567-e89b-12d3-a456-426614174000"
PK = "PRIVATE " + "KEY"


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("clone https://ada:hunter2pass@github.com/ada/repo.git", "URL_CREDENTIALS"),
        (
            f"-----BEGIN RSA {PK}-----\nMIIabc\ndef\n-----END RSA {PK}-----",
            "PRIVATE_KEY",
        ),
        ("token ghp_" + "a" * 36, "TOKEN"),
        ("github_pat_" + "A1b2C3d4E5" * 4, "TOKEN"),
        ("gho_" + "x" * 30, "TOKEN"),
        ("aws " + "AKIA" + "ABCDEFGHIJKLMNOP" + " key", "TOKEN"),
        ("openai sk-" + "q" * 30, "TOKEN"),
        ("google AIza" + "B" * 35, "TOKEN"),
        ("slack xoxb-1234567890-abcdef", "TOKEN"),
        ("jwt eyJhbGciOiJI.eyJzdWIiOiIx.SflKxwRJSMeKKF2QT4", "TOKEN"),
        ("mail ada.lovelace+jobs@example.co.uk now", "EMAIL"),
        ("call +1 (415) 555-0132 today", "PHONE"),
        ("call 020 7946 0958", "PHONE"),
        ("host 192.168.10.25 is down", "IP"),
        ("host 2001:db8:85a3:0:0:8a2e:370:7334 up", "IP"),
        ("password = " + "Zx9fK2mQ8v" + "L4nB7cT1", "SECRET"),
        ("api_key: " + "abcd1234efgh" + "5678ijkl", "SECRET"),
    ],
)
def test_redact_replaces_each_sensitive_shape(text: str, label: str) -> None:
    result = redact(text)

    assert result.counts.get(label, 0) >= 1
    assert f"<{label}_1>" in result.text
    for original in result.placeholders.values():
        assert original not in result.text


@pytest.mark.parametrize(
    "text",
    [
        f"fixes regression introduced in {SHA}",
        f"short sha 9fceb02 and uuid {UUID}",
        "version 1.2.3.4 of the client",
        "upgrade to v10.20.30.40 soon",
        "uptime 14:50:41 and 2:15:00",
        "released 2026-10-03 14:50:41",
        "opened issue #1234567 and PR 98765",
        "Fix race in token refresh",
        "token budget is 4096 per request",
        "build 20261003123456789012345 finished",
        "ada@localhost is not an address",
    ],
)
def test_redact_leaves_look_alikes_alone(text: str) -> None:
    result = redact(text)

    assert result.text == text
    assert result.counts == {}


def test_redact_is_idempotent() -> None:
    text = "mail ada@example.com from 10.0.0.1 token ghp_" + "z" * 36 + " call +44 20 7946 0958"

    once = redact(text)

    assert redact(once.text).text == once.text
    assert redact(once.text).counts == {}


def test_redact_reuses_one_placeholder_for_repeated_values() -> None:
    result = redact("ada@example.com wrote to bob@example.com and ada@example.com")

    assert result.text == "<EMAIL_1> wrote to <EMAIL_2> and <EMAIL_1>"
    assert result.counts == {"EMAIL": 2}


def test_restore_round_trips_the_original_text() -> None:
    text = "ping ada@example.com at 10.1.2.3 with ghp_" + "k" * 36 + f" ({SHA})"

    result = redact(text)

    assert result.text != text
    assert restore(result.text, result.placeholders) == text


def test_restore_leaves_unknown_placeholders_untouched() -> None:
    assert restore("see <EMAIL_9>", {}) == "see <EMAIL_9>"


def test_redact_url_credentials_keep_the_host_readable() -> None:
    result = redact("https://ada:hunter2pass@github.com/ada/repo")

    assert result.text.endswith("@github.com/ada/repo")
    assert "hunter2pass" not in result.text
