import pytest

from app.services.company_names import Merges, normalize_company


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Reliance Jio Infocom Ltd.", "reliance jio infocom"),
        ("Flashcloud Intelligence Asia Pvt. Ltd.", "flashcloud intelligence asia"),
        ("Orderat LLC", "orderat"),
        ("ACME, Inc.", "acme"),
        ("acme", "acme"),
        ("  Acme   Corporation ", "acme"),
        ("Café Ünïcode GmbH", "cafe unicode"),
        ("AT&T", "at t"),
        ("Samsung", "samsung"),
        ("Samsung Research Institute", "samsung research institute"),
        ("Co", "co"),
        ("Company Inc", "company"),
        ("株式会社テスト", "株式会社テスト"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_company_drops_case_accents_punctuation_and_legal_suffixes(
    name: str | None, expected: str
) -> None:
    assert normalize_company(name) == expected


def test_different_companies_stay_different_until_merged() -> None:
    assert normalize_company("Samsung") != normalize_company("Samsung Research Institute")


def test_merges_resolve_every_member_to_one_key_and_one_display_name() -> None:
    merges = Merges([("Samsung", ["Samsung Research Institute"])])

    assert merges.key("Samsung Research Institute") == merges.key("SAMSUNG Ltd.") == "samsung"
    assert merges.canonical("samsung") == "Samsung"
    assert merges.members("samsung") == ("Samsung", "Samsung Research Institute")
    assert merges.key("Acme Inc") == "acme"


def test_merges_round_trip_through_the_stored_shape() -> None:
    merges = Merges([("Samsung", ["Samsung Research Institute"]), ("Alle", ["Alle Labs"])])

    stored = merges.to_stored()
    again = Merges.from_stored(stored)

    assert stored == {
        "groups": [
            {"canonical": "Samsung", "members": ["Samsung", "Samsung Research Institute"]},
            {"canonical": "Alle", "members": ["Alle", "Alle Labs"]},
        ]
    }
    assert again.key("Alle Labs") == "alle"
    assert again.keys() == ["samsung", "alle"]


@pytest.mark.parametrize(
    "raw",
    [None, "nope", [], {}, {"groups": "x"}, {"groups": [1, None]}, {"groups": [{"members": []}]}],
)
def test_a_missing_or_malformed_stored_value_means_no_merges(raw: object) -> None:
    assert Merges.from_stored(raw).keys() == []


def test_a_partly_valid_stored_value_keeps_the_usable_groups() -> None:
    merges = Merges.from_stored(
        {"groups": [{"canonical": "Samsung", "members": ["Samsung RI", 5, None]}, {"nope": 1}]}
    )

    assert merges.key("Samsung RI") == "samsung"
    assert merges.keys() == ["samsung"]
