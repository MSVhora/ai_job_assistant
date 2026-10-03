from collections import Counter
from datetime import date
from typing import Any

from fakes import golden_profile, transient_achievement

from app.core.config import get_settings
from app.schemas.profile import ContactInfo, ExperienceItem, StructuredProfile
from app.schemas.resume_document import Conflict
from app.services.resume_reconcile import GitHubIdentity, reconcile

ENGINE = {"company": "Engine Co", "start_date": "Jan 2020", "source": "user"}
BABBAGE = {"company": "Babbage Systems", "start_date": "Jul 2023", "source": "user"}
GHOST = {"company": "Ghost Corp", "start_date": "2019", "source": "user"}
CONFIRMED_LATENCY = {
    "text": "reduced p95 latency by 40%",
    "source_quote": "p95 fell 40%",
    "evidence_ids": [],
    "verified": "evidence",
}
IDENTITY = GitHubIdentity(
    name="Augusta Byron", location="London, England", emails=("ada@example.com",)
)


def golden_achievements() -> list[Any]:
    return [
        transient_achievement(
            title="Outside Babbage", employer_ref=BABBAGE, time_start=date(2021, 3, 1)
        ),
        transient_achievement(title="Ghost work", employer_ref=GHOST, time_start=date(2019, 5, 1)),
        transient_achievement(
            title="Latency",
            employer_ref=ENGINE,
            time_start=date(2021, 5, 1),
            metrics=[CONFIRMED_LATENCY],
            skills=["Python", "Kubernetes"],
        ),
        transient_achievement(title="Platform", employer_ref=ENGINE, skills=["SQL", "terraform"]),
        transient_achievement(title="OSS", employer_ref={"kind": "personal", "source": "user"}),
    ]


def kinds(conflicts: list[Conflict]) -> Counter[str]:
    return Counter(conflict.kind for conflict in conflicts)


def test_every_conflict_kind_is_detected_exactly_once_on_the_golden_profile() -> None:
    conflicts = reconcile(golden_profile(), golden_achievements(), IDENTITY)

    assert kinds(conflicts) == {
        "date_outside_employment": 1,
        "employer_not_in_profile": 1,
        "identity_mismatch": 1,
        "skill_missing_in_profile": 1,
        "skill_without_evidence": 1,
        "metric_contradiction": 1,
        "overlapping_roles": 1,
    }


def test_conflicts_name_what_they_refer_to() -> None:
    by_kind = {c.kind: c for c in reconcile(golden_profile(), golden_achievements(), IDENTITY)}

    assert by_kind["identity_mismatch"].refs == {"field": "name"}
    assert by_kind["skill_missing_in_profile"].refs == {"skill": "kubernetes"}
    assert by_kind["skill_without_evidence"].refs == {"skill": "rust"}
    assert by_kind["employer_not_in_profile"].refs["company"] == "Ghost Corp"
    assert set(by_kind["overlapping_roles"].refs.values()) == {
        "Analytical Ltd|Oct 2022",
        "Engine Co|Jan 2020",
    }
    assert by_kind["metric_contradiction"].severity == "error"
    assert by_kind["skill_without_evidence"].suggested_actions == ["keep_as_is"]


def test_a_clean_profile_has_no_conflicts() -> None:
    profile = StructuredProfile(
        contact=ContactInfo(full_name="Ada Lovelace", email="ada@example.com", location="London"),
        skills=["Python", "SQL"],
        experience=[
            ExperienceItem(
                company="Engine Co",
                start_date="Jan 2020",
                end_date="Dec 2022",
                bullets=["Cut p95 latency by 40% across the ingest service"],
            )
        ],
    )
    achievements = [
        transient_achievement(
            employer_ref=ENGINE, skills=["python", "SQL"], metrics=[CONFIRMED_LATENCY]
        )
    ]
    identity = GitHubIdentity(
        name="Ada Lovelace", location="London, England", emails=("ADA@example.com",)
    )

    assert reconcile(profile, achievements, identity) == []


def test_keys_are_stable_across_reruns_and_independent_of_input_order() -> None:
    achievements = golden_achievements()

    first = reconcile(golden_profile(), achievements, IDENTITY)
    second = reconcile(golden_profile(), list(reversed(achievements)), IDENTITY)

    assert {c.key for c in first} == {c.key for c in second}
    assert len({c.key for c in first}) == len(first)


def test_without_a_github_identity_the_identity_check_is_skipped() -> None:
    conflicts = reconcile(golden_profile(), golden_achievements(), None)

    assert "identity_mismatch" not in kinds(conflicts)


def test_email_mismatch_is_reported_only_when_github_exposes_an_email() -> None:
    profile = golden_profile()
    other = GitHubIdentity(name="Ada Lovelace", location="London", emails=("other@example.com",))
    private = GitHubIdentity(name="Ada Lovelace", location="London", emails=())

    flagged = [c.refs for c in reconcile(profile, [], other) if c.kind == "identity_mismatch"]
    assert flagged == [{"field": "email"}]
    assert "identity_mismatch" not in kinds(reconcile(profile, [], private))


def test_suggested_employer_mappings_and_unconfirmed_metrics_are_ignored() -> None:
    suggested = {**GHOST, "source": "suggested"}
    pending = {**CONFIRMED_LATENCY, "verified": "needs_confirmation"}
    achievements = [
        transient_achievement(employer_ref=suggested),
        transient_achievement(employer_ref=ENGINE, metrics=[pending]),
    ]

    conflicts = reconcile(golden_profile(), achievements)

    assert not {"employer_not_in_profile", "metric_contradiction"} & set(kinds(conflicts))


def test_unparsable_dates_never_produce_a_date_conflict() -> None:
    undated = {"company": "Undated Labs", "start_date": None, "source": "user"}
    achievements = [transient_achievement(employer_ref=undated, time_start=date(1999, 1, 1))]

    assert "date_outside_employment" not in kinds(reconcile(golden_profile(), achievements))


def test_month_and_year_granularity_does_not_cause_false_date_conflicts() -> None:
    profile = StructuredProfile(
        contact=ContactInfo(full_name="Ada"),
        skills=["Python"],
        experience=[
            ExperienceItem(company="A", start_date="Jan 2020", end_date="Dec 2020"),
            ExperienceItem(company="B", start_date="2021", end_date="2022"),
        ],
    )
    a = {"company": "A", "start_date": "Jan 2020", "source": "user"}
    b = {"company": "B", "start_date": "2021", "source": "user"}
    achievements = [
        transient_achievement(employer_ref=a, time_start=date(2020, 12, 28)),
        transient_achievement(employer_ref=b, time_start=date(2022, 11, 30)),
    ]

    assert "date_outside_employment" not in kinds(reconcile(profile, achievements))


def test_metric_must_share_a_topic_and_unit_to_contradict() -> None:
    unrelated = {**CONFIRMED_LATENCY, "text": "grew revenue by 40%"}
    other_unit = {**CONFIRMED_LATENCY, "text": "reduced p95 latency by 40 ms"}
    achievements = [
        transient_achievement(employer_ref=ENGINE, metrics=[unrelated]),
        transient_achievement(employer_ref=ENGINE, metrics=[other_unit]),
    ]

    assert "metric_contradiction" not in kinds(reconcile(golden_profile(), achievements))


def test_a_matching_figure_is_not_a_contradiction() -> None:
    same = {**CONFIRMED_LATENCY, "text": "cut p95 latency by 60%"}

    conflicts = reconcile(
        golden_profile(), [transient_achievement(employer_ref=ENGINE, metrics=[same])]
    )

    assert "metric_contradiction" not in kinds(conflicts)


def test_project_bullets_are_checked_through_the_repository_name() -> None:
    metric = {**CONFIRMED_LATENCY, "text": "reduced cold-start time by 35%"}
    achievements = [transient_achievement(project_key="ada/engine", metrics=[metric])]

    conflicts = reconcile(golden_profile(), achievements)

    assert kinds(conflicts)["metric_contradiction"] == 1


def test_overlap_below_the_threshold_is_not_reported(monkeypatch: Any) -> None:
    monkeypatch.setattr(get_settings(), "resume_overlap_min_days", 90)

    assert "overlapping_roles" not in kinds(reconcile(golden_profile(), []))


def test_current_role_overlap_uses_today() -> None:
    profile = StructuredProfile(
        contact=ContactInfo(full_name="Ada"),
        skills=["Python"],
        experience=[
            ExperienceItem(company="A", start_date="Jan 2025", is_current=True),
            ExperienceItem(company="B", start_date="Jun 2025", is_current=True),
        ],
    )

    assert kinds(reconcile(profile, []))["overlapping_roles"] == 1


def test_no_approved_evidence_means_no_skill_noise() -> None:
    assert not {"skill_missing_in_profile", "skill_without_evidence"} & set(
        kinds(reconcile(golden_profile(), []))
    )


def test_reconciling_never_mutates_the_profile() -> None:
    profile = golden_profile()
    before = profile.model_dump()

    reconcile(profile, golden_achievements(), IDENTITY)

    assert profile.model_dump() == before
