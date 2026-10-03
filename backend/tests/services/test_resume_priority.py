import uuid
from datetime import date

import pytest
from fakes import fake_vector, transient_achievement

from app.core.config import Settings, get_settings
from app.schemas.resume_document import WorkEntry
from app.services.resume_priority import (
    BUDGET_SEEDS,
    Candidate,
    alignment,
    base_priority,
    blended,
    candidate_pool_size,
    cosine,
    mmr_order,
    role_priority,
    select_for_writing,
    tailoring_weight,
)

TODAY = date(2026, 10, 1)
CONFIRMED = [{"text": "9 minutes", "verified": "evidence"}]


def base(**fields: object) -> float:
    defaults: dict[str, object] = {"difficulty": 3, "impact_type": "other"}
    return base_priority(transient_achievement(**{**defaults, **fields}), TODAY, get_settings())


def candidate(
    name: str, priority: float, block: str = "b1", skills: frozenset[str] = frozenset()
) -> Candidate:
    return Candidate(
        achievement_id=uuid.uuid5(uuid.NAMESPACE_DNS, name),
        title=name,
        block_id=block,
        base=priority,
        alignment=0.0,
        priority=priority,
        skills=skills,
        embedding=None,
        from_private=False,
    )


def test_base_priority_follows_impact_difficulty_and_recency() -> None:
    plain = base(impact_type="other", difficulty=1, time_start=date(2020, 1, 1))

    assert base(impact_type="revenue", difficulty=1, time_start=date(2020, 1, 1)) > plain
    assert base(impact_type="other", difficulty=5, time_start=date(2020, 1, 1)) > plain
    assert base(impact_type="other", difficulty=1, time_start=date(2026, 9, 1)) > plain
    assert (
        base(impact_type="other", difficulty=1, metrics=CONFIRMED, time_start=date(2020, 1, 1))
        > plain
    )


def test_an_unconfirmed_metric_does_not_raise_priority() -> None:
    unconfirmed = [{"text": "9 minutes", "verified": "needs_confirmation"}]

    assert base(metrics=unconfirmed) == base(metrics=[])


def test_priority_weights_come_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        resume_weight_impact=0.1, resume_weight_difficulty=0.8, resume_weight_recency=0.1
    )
    hard = transient_achievement(difficulty=5, impact_type="other")
    easy = transient_achievement(difficulty=1, impact_type="other")

    assert base_priority(hard, TODAY, settings) - base_priority(
        easy, TODAY, settings
    ) == pytest.approx(0.8)


def test_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match=r"sum to 1\.0"):
        Settings(resume_weight_impact=0.9)


def test_tailoring_weights_follow_the_strength_and_vanish_without_a_jd() -> None:
    settings = get_settings()

    assert tailoring_weight("light", settings, has_jd=True) == pytest.approx(0.15)
    assert tailoring_weight("balanced", settings, has_jd=True) == pytest.approx(0.30)
    assert tailoring_weight("strong", settings, has_jd=True) == pytest.approx(0.50)
    assert tailoring_weight("strong", settings, has_jd=False) == 0.0


def test_without_a_jd_the_blend_is_the_untailored_ordering() -> None:
    items = [(0.4, 0.9), (0.7, 0.0), (0.5, 0.5)]

    untailored = sorted(items, key=lambda pair: -pair[0])
    blended_order = sorted(items, key=lambda pair: -blended(pair[0], pair[1], 0.0))

    assert blended_order == untailored


def test_jd_boost_lifts_aligned_work_without_filtering_the_rest() -> None:
    weight = 0.30
    aligned_modest = blended(0.50, 1.0, weight)
    equal_unaligned = blended(0.50, 0.0, weight)
    high_impact_unaligned = blended(0.85, 0.0, weight)
    low_impact_weak = blended(0.30, 0.2, weight)

    assert aligned_modest > equal_unaligned
    assert high_impact_unaligned > low_impact_weak
    assert high_impact_unaligned > 0


def test_a_strong_setting_lifts_aligned_items_further_but_keeps_everything_ranked() -> None:
    values = [(0.6, 1.0), (0.8, 0.0)]
    light = [blended(b, a, 0.15) for b, a in values]
    strong = [blended(b, a, 0.50) for b, a in values]

    assert strong[0] - strong[1] > light[0] - light[1]
    assert all(value > 0 for value in strong)


def test_alignment_blends_vector_similarity_and_term_hits() -> None:
    vector = fake_vector("kubernetes platform")

    assert alignment(["Kubernetes"], None, {"kubernetes"}, None) == pytest.approx(0.5)
    assert alignment(["Kubernetes", "Kafka"], None, {"kubernetes", "kafka"}, None) == 1.0
    assert alignment(["Python"], None, {"kubernetes"}, None) == 0.0
    assert alignment([], vector, set(), vector) == pytest.approx(0.6)
    assert alignment(["Kubernetes"], vector, set(), None) == 0.0


def test_cosine_is_zero_for_empty_vectors() -> None:
    assert cosine([], []) == 0.0
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_mmr_demotes_a_near_duplicate() -> None:
    same = frozenset({"python"})
    ordered = mmr_order(
        [
            candidate("a", 0.90, skills=same),
            candidate("duplicate", 0.88, skills=same),
            candidate("different", 0.80, skills=frozenset({"kafka"})),
        ]
    )

    assert [item.title for item in ordered] == ["a", "different", "duplicate"]


def test_mmr_is_deterministic_for_ties() -> None:
    items = [candidate(name, 0.5) for name in ("x", "y", "z")]

    assert mmr_order(items) == mmr_order(list(reversed(items)))


def test_role_priority_weights_the_top_three_and_adds_recency() -> None:
    strong = role_priority([0.9, 0.8, 0.7, 0.1], recency=0.5)
    weak = role_priority([0.3, 0.2], recency=0.5)

    assert strong > weak
    assert role_priority([], recency=1.0) == pytest.approx(0.1)
    assert role_priority([0.9, 0.8, 0.7], 0.0) == role_priority([0.9, 0.8, 0.7, 0.01], 0.0)


@pytest.mark.parametrize(("pages", "budget"), [(1, 15), (2, 28), (3, 40), (4, 52)])
def test_budget_seeds_and_pool_size(pages: int, budget: int) -> None:
    assert BUDGET_SEEDS[pages] == budget
    assert candidate_pool_size(pages, 1.3) == -(-budget * 13 // 10)


def test_selection_always_includes_each_blocks_best_candidate() -> None:
    ordered = mmr_order(
        [candidate(f"a{n}", 0.9 - n * 0.01, "big") for n in range(30)]
        + [candidate("lonely", 0.1, "small")]
    )

    selected = select_for_writing(ordered, 1, 1.3)

    assert len(selected) == 20
    assert "lonely" in [item.title for item in selected]
    assert [item.title for item in selected] == [item.title for item in ordered if item in selected]


def test_work_entry_ids_are_part_of_the_schema() -> None:
    assert WorkEntry().id == ""
