from collections import Counter
from datetime import date

from fakes import transient_achievement

from app.schemas.profile import ContactInfo, ExperienceItem, StructuredProfile
from app.schemas.resume_document import Basics, Conflict, ResumeContent, WorkEntry
from app.services.company_names import Merges
from app.services.resume_blocks import block_for_achievement, pick_stint
from app.services.resume_priority import RoleSpan, resolve_overlaps, role_span
from app.services.resume_reconcile import reconcile

TODAY = date(2026, 10, 1)
ACME = {"company": "Acme Corp", "start_date": None, "source": "user"}


def job(
    block: str, company: str, start: str, end: str | None, *, current: bool = False
) -> WorkEntry:
    return WorkEntry(
        id=block,
        company=company,
        title="Engineer",
        start_date=start,
        end_date=end,
        is_current=current,
    )


def content(*jobs: WorkEntry) -> ResumeContent:
    return ResumeContent(basics=Basics(full_name="Ada"), work=list(jobs))


TWO_STINTS = content(
    job("early", "Acme Corp", "Jan 2019", "Dec 2020"),
    job("late", "Acme Corp", "Mar 2022", None, current=True),
    job("other", "Other Co", "Jan 2015", "Dec 2018"),
)


def placed(ref: dict[str, object] | None, started: date | None = date(2019, 6, 1), **kw: object):
    achievement = transient_achievement(employer_ref=ref, time_start=started, **kw)
    return block_for_achievement(achievement, TWO_STINTS)


def test_a_company_level_employer_places_the_bullet_under_the_stint_its_dates_fall_in() -> None:
    assert placed(ACME, date(2019, 6, 1)) == "early"
    assert placed(ACME, date(2023, 1, 1)) == "late"


def test_dates_between_stints_or_missing_fall_back_to_the_most_recent_stint() -> None:
    assert placed(ACME, date(2021, 6, 1)) == "late"
    assert placed(ACME, None) == "late"


def test_an_achievement_spanning_both_stints_goes_to_the_one_it_overlaps_most() -> None:
    achievement = transient_achievement(
        employer_ref=ACME, time_start=date(2020, 6, 1), time_end=date(2023, 6, 1)
    )

    assert block_for_achievement(achievement, TWO_STINTS) == "late"


def test_a_legacy_reference_naming_one_entry_still_resolves_to_exactly_that_entry() -> None:
    legacy = {"company": "Acme Corp", "start_date": "Jan 2019", "source": "user"}

    assert placed(legacy, date(2024, 1, 1)) == "early"


def test_an_unknown_company_is_not_placed_and_personal_or_suggested_never_are() -> None:
    assert placed({"company": "Nowhere", "start_date": None, "source": "user"}) is None
    assert placed({"kind": "personal", "source": "user"}) is None
    assert placed({**ACME, "source": "suggested"}) is None
    assert placed(None) is None


def test_a_merged_name_places_the_bullet_under_the_merged_employers_entries() -> None:
    merged = content(job("sri", "Samsung Research Institute", "Jul 2017", "Sep 2018"))
    merges = Merges([("Samsung", ["Samsung Research Institute"])])
    achievement = transient_achievement(
        employer_ref={"company": "Samsung", "start_date": None, "source": "user"}
    )

    assert block_for_achievement(achievement, merged) is None
    assert block_for_achievement(achievement, merged, merges) == "sri"


def test_pick_stint_prefers_the_current_one_when_nothing_overlaps() -> None:
    jobs = [job("a", "X", "Jan 2019", "Dec 2019"), job("b", "X", "Jan 2022", None, current=True)]

    assert pick_stint(jobs, date(2020, 6, 1), None).id == "b"


def profile(*jobs: ExperienceItem) -> StructuredProfile:
    return StructuredProfile(
        contact=ContactInfo(full_name="Ada"), skills=["Python"], experience=list(jobs)
    )


ACME_STINTS = profile(
    ExperienceItem(company="Acme Corp", start_date="Jan 2019", end_date="Dec 2019"),
    ExperienceItem(company="Acme Corp", start_date="Jan 2022", end_date="Dec 2022"),
)


def kinds(conflicts: list[Conflict]) -> Counter[str]:
    return Counter(conflict.kind for conflict in conflicts)


def test_a_date_inside_any_stint_of_the_employer_is_not_a_conflict() -> None:
    early = transient_achievement(employer_ref=ACME, time_start=date(2019, 5, 1))
    late = transient_achievement(employer_ref=ACME, time_start=date(2022, 5, 1))

    assert "date_outside_employment" not in kinds(reconcile(ACME_STINTS, [early, late]))


def test_a_date_outside_every_stint_is_still_a_conflict() -> None:
    gap = transient_achievement(employer_ref=ACME, time_start=date(2020, 8, 1))

    assert kinds(reconcile(ACME_STINTS, [gap]))["date_outside_employment"] == 1


def test_a_missing_employer_is_reported_once_however_the_references_were_dated() -> None:
    achievements = [
        transient_achievement(
            employer_ref={"company": "Ghost Corp", "start_date": "2019", "source": "user"}
        ),
        transient_achievement(
            employer_ref={"company": "Ghost Corp", "start_date": "2020", "source": "user"}
        ),
        transient_achievement(
            employer_ref={"company": "ghost corp", "start_date": None, "source": "user"}
        ),
    ]

    conflicts = [
        c for c in reconcile(ACME_STINTS, achievements) if c.kind == "employer_not_in_profile"
    ]

    assert len(conflicts) == 1
    assert "3 achievement(s)" in conflicts[0].message


def test_a_contradicting_bullet_in_any_stint_of_the_employer_is_found() -> None:
    p = profile(
        ExperienceItem(company="Acme Corp", start_date="Jan 2019", end_date="Dec 2019", bullets=[]),
        ExperienceItem(
            company="Acme Corp",
            start_date="Jan 2022",
            end_date="Dec 2022",
            bullets=["Reduced p95 latency by 25% for the checkout service"],
        ),
    )
    achievement = transient_achievement(
        employer_ref=ACME,
        metrics=[
            {
                "text": "reduced p95 latency by 40%",
                "source_quote": "p95 fell 40%",
                "evidence_ids": [],
                "verified": "evidence",
            }
        ],
    )

    assert kinds(reconcile(p, [achievement]))["metric_contradiction"] == 1


def test_two_stints_at_one_company_never_count_as_overlapping_roles() -> None:
    p = profile(
        ExperienceItem(company="Acme Corp", start_date="Jan 2020", end_date="Dec 2022"),
        ExperienceItem(company="ACME Inc.", start_date="Jun 2021", end_date="Dec 2023"),
    )

    assert "overlapping_roles" not in kinds(reconcile(p, []))


def test_merged_names_count_as_one_employer_for_every_check() -> None:
    p = profile(
        ExperienceItem(company="Samsung", start_date="Jan 2020", end_date="Dec 2022"),
        ExperienceItem(
            company="Samsung Research Institute", start_date="Jun 2021", end_date="Dec 2023"
        ),
    )
    merges = Merges([("Samsung", ["Samsung Research Institute"])])
    mapped = transient_achievement(
        employer_ref={"company": "Samsung", "start_date": None, "source": "user"},
        time_start=date(2023, 5, 1),
    )

    assert "overlapping_roles" in kinds(reconcile(p, []))
    merged = kinds(reconcile(p, [mapped], merges=merges))
    assert "overlapping_roles" not in merged
    assert "date_outside_employment" not in merged


def role_at(block: str, company: str, start: str, end: str, priority: float) -> RoleSpan:
    return role_span(job(block, company, start, end), priority, TODAY)


def test_concurrent_roles_at_one_company_are_both_kept() -> None:
    roles = [
        role_at("a", "Acme Corp", "Jan 2020", "Dec 2021", 0.4),
        role_at("b", "Acme Inc.", "Jun 2021", "Dec 2022", 0.7),
    ]

    kept, omitted = resolve_overlaps(roles, 60)

    assert [r.block_id for r in kept] == ["a", "b"]
    assert omitted == []


def test_concurrent_roles_at_different_companies_are_still_resolved() -> None:
    roles = [
        role_at("a", "Acme", "Jan 2020", "Dec 2021", 0.4),
        role_at("b", "Other", "Jun 2021", "Dec 2022", 0.7),
    ]

    kept, omitted = resolve_overlaps(roles, 60)

    assert [r.block_id for r in kept] == ["b"]
    assert [o.role.block_id for o in omitted] == ["a"]


def test_merged_companies_are_exempt_too() -> None:
    roles = [
        role_at("a", "Samsung", "Jan 2020", "Dec 2021", 0.4),
        role_at("b", "Samsung Research Institute", "Jun 2021", "Dec 2022", 0.7),
    ]
    merges = Merges([("Samsung", ["Samsung Research Institute"])])

    assert len(resolve_overlaps(roles, 60)[0]) == 1
    assert len(resolve_overlaps(roles, 60, company_key=merges.key)[0]) == 2
