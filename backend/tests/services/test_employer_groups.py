from datetime import date

import pytest

from app.services.company_names import Merges
from app.services.employer_mapping import (
    Experience,
    group_experiences,
    normalize_employer_ref,
    suggest_employer,
    suggest_for_scope,
)


def exp(
    company: str,
    start: tuple[int, int] | None,
    end: tuple[int, int] | None,
    raw: str | None = None,
    *,
    current: bool = False,
) -> Experience:
    return Experience(
        company,
        raw if raw is not None else (f"{start[0]}-{start[1]:02d}" if start else None),
        date(*start, 1) if start else None,
        date(*end, 28) if end else None,
        is_current=current,
    )


WEMSQUARE = [
    exp("Wemsquare Technologies", (2018, 6), (2018, 8), "June 2018"),
    exp("Wemsquare Technologies", (2018, 9), (2018, 11), "09/2018"),
    exp("Wemsquare Technologies", (2018, 12), (2020, 4), "Dec 2018"),
    exp("Wemsquare Technologies", (2020, 11), (2021, 2), "Nov 2020"),
]
SAMSUNG = [
    exp("Samsung", (2017, 1), (2017, 6)),
    exp("Samsung Research Institute", (2017, 7), (2018, 9)),
]


def test_entries_of_one_company_become_one_employer_with_their_whole_span() -> None:
    (group,) = group_experiences(WEMSQUARE)

    assert group.name == "Wemsquare Technologies"
    assert group.key == "wemsquare technologies"
    assert len(group.entries) == 4
    assert [entry.start_raw for entry in group.entries] == [
        "June 2018",
        "09/2018",
        "Dec 2018",
        "Nov 2020",
    ]
    assert (group.start, group.end) == (date(2018, 6, 1), date(2021, 2, 28))


def test_name_variants_that_normalize_alike_are_one_employer_named_by_the_most_common() -> None:
    groups = group_experiences(
        [
            exp("Acme Inc.", (2020, 1), (2020, 6)),
            exp("ACME", (2020, 7), (2020, 12)),
            exp("Acme Inc.", (2021, 1), (2021, 6)),
        ]
    )

    assert [(g.name, len(g.entries)) for g in groups] == [("Acme Inc.", 3)]
    assert groups[0].aliases == ("Acme Inc.", "ACME")


def test_employers_are_listed_most_recent_first() -> None:
    groups = group_experiences([*SAMSUNG, *WEMSQUARE])

    assert [g.name for g in groups] == [
        "Wemsquare Technologies",
        "Samsung Research Institute",
        "Samsung",
    ]


def test_differently_named_companies_are_separate_until_the_user_merges_them() -> None:
    assert len(group_experiences(SAMSUNG)) == 2

    (merged,) = group_experiences(SAMSUNG, Merges([("Samsung", ["Samsung Research Institute"])]))

    assert merged.name == "Samsung"
    assert len(merged.entries) == 2
    assert merged.merged_from == ("Samsung Research Institute",)
    assert set(merged.aliases) == {"Samsung", "Samsung Research Institute"}


def test_an_entry_without_dates_is_kept_and_listed_last_within_its_employer() -> None:
    (group,) = group_experiences([exp("Acme", None, None, None), exp("Acme", (2020, 1), (2020, 6))])

    assert [entry.start for entry in group.entries] == [date(2020, 1, 1), None]
    assert group.start == date(2020, 1, 1)


def test_an_employer_is_current_when_any_stint_is() -> None:
    (group,) = group_experiences(
        [exp("Acme", (2020, 1), (2020, 6)), exp("Acme", (2024, 1), None, current=True)]
    )

    assert group.current is True


def test_a_company_level_ref_is_stored_without_a_start_date() -> None:
    groups = group_experiences(WEMSQUARE)

    stored = normalize_employer_ref({"company": "wemsquare technologies"}, groups)

    assert stored == {"company": "Wemsquare Technologies", "start_date": None, "source": "user"}


def test_a_legacy_ref_naming_one_entry_resolves_to_its_employer() -> None:
    groups = group_experiences(WEMSQUARE)

    stored = normalize_employer_ref(
        {"company": "Wemsquare Technologies", "start_date": "Nov 2020"}, groups
    )

    assert stored == {"company": "Wemsquare Technologies", "start_date": None, "source": "user"}


def test_a_merged_name_resolves_to_the_canonical_employer() -> None:
    groups = group_experiences(SAMSUNG, Merges([("Samsung", ["Samsung Research Institute"])]))

    stored = normalize_employer_ref({"company": "Samsung Research Institute"}, groups)

    assert stored == {"company": "Samsung", "start_date": None, "source": "user"}


def test_personal_and_none_pass_through_and_unknown_employers_are_rejected() -> None:
    groups = group_experiences(WEMSQUARE)

    assert normalize_employer_ref(None, groups) is None
    assert normalize_employer_ref({"kind": "personal"}, groups) == {
        "kind": "personal",
        "source": "user",
    }
    with pytest.raises(ValueError, match="your employers"):
        normalize_employer_ref({"company": "Nowhere Inc"}, groups)
    with pytest.raises(ValueError, match="your employers"):
        normalize_employer_ref({"company": "  "}, groups)
    with pytest.raises(ValueError, match="your employers"):
        normalize_employer_ref({"kind": "experience"}, groups)


def test_stints_that_each_cover_under_half_a_repo_but_together_most_of_it_still_match() -> None:
    groups = group_experiences(
        [
            exp("Acme", (2020, 1), (2020, 6)),
            exp("Acme", (2020, 7), (2020, 12)),
            exp("Other", (2021, 1), (2021, 12)),
        ]
    )

    suggestion = suggest_for_scope(date(2020, 1, 1), date(2020, 12, 31), groups)

    assert suggestion == {"company": "Acme", "start_date": None, "source": "suggested"}


def test_a_repo_spanning_two_employers_gets_no_scope_suggestion() -> None:
    groups = group_experiences(
        [exp("Acme", (2020, 1), (2020, 12)), exp("Other", (2021, 1), (2021, 12))]
    )

    assert suggest_for_scope(date(2020, 1, 1), date(2021, 12, 31), groups) is None


def test_a_chunk_is_suggested_the_employer_it_overlaps_most() -> None:
    groups = group_experiences(
        [exp("Acme", (2020, 1), (2020, 3)), exp("Other", (2020, 3), (2020, 12))]
    )

    chosen = suggest_employer("ada/engine", date(2020, 2, 1), date(2020, 6, 1), groups)

    assert chosen == {"company": "Other", "start_date": None, "source": "suggested"}
