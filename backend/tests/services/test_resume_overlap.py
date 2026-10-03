from datetime import date

from app.schemas.resume_document import WorkEntry
from app.services.resume_priority import RoleSpan, overlap_days, resolve_overlaps, role_span

TODAY = date(2026, 10, 1)


def role(
    block: str,
    start: str | None,
    end: str | None,
    priority: float,
    *,
    current: bool = False,
) -> RoleSpan:
    entry = WorkEntry(
        id=block,
        company=block,
        title="Engineer",
        start_date=start,
        end_date=end,
        is_current=current,
    )
    return role_span(entry, priority, TODAY)


def resolve(
    roles: list[RoleSpan], forced: frozenset[str] = frozenset()
) -> tuple[list[str], dict[str, str]]:
    kept, omitted = resolve_overlaps(roles, 60, forced)
    return [r.block_id for r in kept], {o.role.block_id: o.blocker.block_id for o in omitted}


def test_the_higher_priority_overlapping_role_is_kept() -> None:
    roles = [role("a", "Jan 2020", "Dec 2021", 0.4), role("b", "Jun 2021", "Dec 2022", 0.7)]

    assert resolve(roles) == (["b"], {"a": "b"})


def test_a_tie_keeps_the_more_recent_role() -> None:
    roles = [role("old", "Jan 2020", "Dec 2021", 0.5), role("new", "Jun 2021", "Dec 2022", 0.5)]

    assert resolve(roles) == (["new"], {"old": "new"})


def test_an_overlap_shorter_than_the_threshold_keeps_both() -> None:
    roles = [role("a", "Jan 2020", "Jan 2021", 0.4), role("b", "Jan 2021", "Dec 2022", 0.7)]

    assert overlap_days(roles[0], roles[1]) < 60
    assert resolve(roles) == (["a", "b"], {})


def test_the_current_role_ends_today_when_checking_overlap() -> None:
    roles = [
        role("done", "Jan 2025", "Sep 2026", 0.4),
        role("now", "Jan 2026", None, 0.7, current=True),
    ]

    assert resolve(roles) == (["now"], {"done": "now"})


def test_a_finished_role_before_the_current_one_does_not_overlap() -> None:
    roles = [
        role("done", "Jan 2020", "Dec 2021", 0.4),
        role("now", "Jan 2022", None, 0.7, current=True),
    ]

    assert resolve(roles) == (["done", "now"], {})


def test_unparsable_or_missing_dates_are_never_omitted() -> None:
    roles = [
        role("a", "sometime", "later", 0.1),
        role("b", "Jan 2020", "Dec 2021", 0.9),
        role("c", None, None, 0.2),
    ]

    assert resolve(roles) == (["a", "b", "c"], {})


def test_include_anyway_keeps_both_and_does_not_block_the_other_role() -> None:
    roles = [role("a", "Jan 2020", "Dec 2021", 0.4), role("b", "Jun 2021", "Dec 2022", 0.7)]

    assert resolve(roles, frozenset({"a"})) == (["a", "b"], {})


def test_kept_roles_stay_in_input_order_and_non_overlapping_roles_are_untouched() -> None:
    roles = [
        role("first", "Jan 2023", None, 0.2, current=True),
        role("second", "Jan 2020", "Dec 2020", 0.9),
        role("third", "Jun 2020", "Dec 2020", 0.1),
    ]

    assert resolve(roles) == (["first", "second"], {"third": "second"})


def test_a_year_only_end_date_is_read_like_the_reconciliation_detector() -> None:
    span = role("y", "2020", "2021", 0.5)

    assert span.start == date(2020, 1, 1)
    assert span.end is not None
