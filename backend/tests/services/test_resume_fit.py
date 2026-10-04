import math

import pytest
from fakes import synthetic_resume

from app.core.errors import CannotFitError, InvalidResumeDocumentError
from app.schemas.resume_document import Generation, Layout, OmittedRole, PoolEntry, ResumeContent
from app.services.resume_render import fit
from app.services.resume_render.fit import Meter, fit_layout, priority_order
from app.services.resume_render.page_meter import compile_pdf, count_pages, measure_pages
from app.services.resume_render.typst_data import PRESETS, JsonObject, build_data

LINES_PER_PAGE = {10.5: 20, 10.0: 25, 9.5: 32}
TARGETS = (1, 2, 3, 4)


def lines(data: JsonObject) -> int:
    sections = data["sections"]
    assert isinstance(sections, list)
    used = 6
    for section in sections:
        used += 1 + len(section["lines"])
        used += sum(1 + len(entry["bullets"]) for entry in section["entries"])
    return used


def fake_meter(data: JsonObject) -> int:
    """A deterministic stand-in: lines used over lines per page at the preset's type size."""
    font = data["font_pt"]
    assert isinstance(font, float)
    return math.ceil(lines(data) / LINES_PER_PAGE[font])


def run(
    content: ResumeContent,
    target: int,
    meter: Meter = fake_meter,
    limit: int = 30,
    generation: Generation | None = None,
) -> Layout:
    return fit_layout(content, generation or Generation(), target, "classic", meter, limit)


def reference(content: ResumeContent, target: int) -> tuple[str, set[str]] | None:
    """Brute force over every prefix of the same ordering: best mass, ties to the roomier preset."""
    usable, _ = fit._eligible(content)
    ordering = priority_order(usable)
    best: tuple[float, str, set[str]] | None = None
    for preset in PRESETS:
        fitting = [
            count
            for count in range(len(ordering) + 1)
            if fake_meter(
                build_data(content, frozenset(b.id for b in ordering[:count]), preset, "classic")
            )
            <= target
        ]
        if not fitting:
            continue
        count = max(fitting)
        mass = sum(b.priority for b in ordering[:count])
        if best is None or mass > best[0]:
            best = (mass, preset.name, {b.id for b in ordering[:count]})
    if best is None or (ordering and not best[2]):
        return None
    return best[1], best[2]


@pytest.mark.parametrize("seed", range(32))
def test_fit_includes_the_maximal_priority_prefix_for_every_target(seed: int) -> None:
    content = synthetic_resume(1 + seed % 6, 1 + seed % 8, seed=seed, words=4 + seed % 10)

    for target in TARGETS:
        expected = reference(content, target)
        if expected is None:
            with pytest.raises(CannotFitError):
                run(content, target)
            continue
        layout = run(content, target)
        assert layout.pages is not None
        assert layout.pages <= target
        assert (layout.preset, set(layout.included_ids)) == expected


@pytest.mark.parametrize("seed", range(12))
def test_fit_with_the_real_compiler_never_exceeds_the_page_target(seed: int) -> None:
    content = synthetic_resume(2 + seed % 5, 2 + seed % 7, seed=seed, words=6 + seed)

    for target in TARGETS:
        layout = run(content, target, meter=measure_pages)
        pdf = compile_pdf(
            build_data(
                content,
                frozenset(layout.included_ids),
                next(p for p in PRESETS if p.name == layout.preset),
                "classic",
            )
        )
        assert count_pages(pdf) == layout.pages
        assert layout.pages is not None
        assert layout.pages <= target


def test_fit_places_every_role_anchor_before_any_second_bullet() -> None:
    content = synthetic_resume(5, 6, seed=3)
    anchors = {max(e.highlights, key=lambda b: b.score).id for e in content.work}

    ordering = [b.id for b in priority_order(fit._eligible(content)[0])]

    assert set(ordering[:5]) == anchors


def test_fit_drops_whole_roles_only_when_the_anchors_cannot_all_fit() -> None:
    content = synthetic_resume(6, 5, seed=4)
    scores = {e.id: max(e.highlights, key=lambda b: b.score) for e in content.work}

    layout = run(content, 1, meter=lambda data: math.ceil(lines(data) / 20))

    included = set(layout.included_ids)
    assert included < {b.id for b in scores.values()}
    assert included
    left_out = [b.score for b in scores.values() if b.id not in included]
    assert min(b.score for b in scores.values() if b.id in included) >= max(left_out)


def test_fit_keeps_pinned_bullets_ahead_of_unpinned_ones() -> None:
    content = synthetic_resume(3, 6, seed=5, pinned={"r2b3"})
    lowest = min((b for e in content.work for b in e.highlights), key=lambda b: b.score)
    content.work[2].highlights[3].score = lowest.score - 0.01

    layout = run(content, 1, meter=lambda data: math.ceil(lines(data) / 14))

    assert "r2b3" in layout.included_ids
    assert any(item.reason == "did_not_fit" for item in layout.not_included)


def test_fit_excludes_bullets_that_need_review_and_reports_them() -> None:
    content = synthetic_resume(2, 3, seed=6, checks={"r0b0": "needs_review", "r1b2": "failed"})

    layout = run(content, 2)

    assert {"r0b0", "r1b2"}.isdisjoint(layout.included_ids)
    flagged = {item.id for item in layout.not_included if item.reason == "needs_review"}
    assert flagged == {"r0b0", "r1b2"}


def test_fit_includes_a_bullet_the_user_approved_anyway() -> None:
    content = synthetic_resume(1, 2, seed=7)
    content.work[0].highlights[0].approved_anyway = True

    assert "r0b0" in run(content, 1).included_ids


def test_fit_carries_over_unwritten_and_overlap_omitted_entries() -> None:
    content = synthetic_resume(1, 2, seed=8)
    generation = Generation(
        pool=[
            PoolEntry(
                achievement_id="00000000-0000-0000-0000-000000000001",
                block_id="role0",
                title="t",
                priority=0.4,
                rank=3,
                written=False,
            )
        ],
        omitted_roles=[
            OmittedRole(
                block_id="old",
                company="Old",
                title="Dev",
                priority=0.2,
                overlaps_with="role0",
                reason="overlap",
                entry=content.work[0],
            )
        ],
    )

    layout = run(content, 2, generation=generation)

    assert {(item.id, item.reason) for item in layout.not_included} == {
        ("00000000-0000-0000-0000-000000000001", "not_written"),
        ("old", "overlap_omitted"),
    }
    assert layout.short_on_evidence is False


def test_fit_reports_short_on_evidence_without_padding() -> None:
    content = synthetic_resume(1, 2, seed=9)

    layout = run(content, 4)

    assert layout.included_ids == ["r0b0", "r0b1"]
    assert layout.pages == 1
    assert layout.short_on_evidence is True


def test_fit_is_not_short_on_evidence_when_a_page_is_full_of_chosen_content() -> None:
    content = synthetic_resume(4, 8, seed=10)

    layout = run(content, 1)

    assert layout.not_included
    assert layout.short_on_evidence is False


def test_fit_raises_when_nothing_fits_even_one_bullet() -> None:
    content = synthetic_resume(2, 2, seed=11)

    with pytest.raises(CannotFitError):
        run(content, 1, meter=lambda _data: 2)


def test_fit_raises_for_a_real_one_page_document_whose_fixed_sections_overflow() -> None:
    content = synthetic_resume(1, 1, seed=12)
    content.skills = [f"Skill number {n}" for n in range(900)]

    with pytest.raises(CannotFitError):
        run(content, 1, meter=measure_pages)


def test_fit_with_no_bullets_returns_an_empty_but_valid_layout() -> None:
    content = synthetic_resume(1, 1, seed=13, checks={"r0b0": "needs_review"})

    layout = run(content, 1)

    assert layout.included_ids == []
    assert layout.pages == 1
    assert layout.short_on_evidence is False


def test_fit_stays_within_the_compile_budget_and_says_when_it_hit_it() -> None:
    content = synthetic_resume(6, 8, seed=14, words=20)
    calls: list[int] = []

    def counting(data: JsonObject) -> int:
        calls.append(1)
        return fake_meter(data)

    layout = run(content, 1, meter=counting, limit=9)

    assert len(calls) == 9
    assert "compile budget reached" in layout.steps


def test_fit_rejects_an_unknown_template() -> None:
    with pytest.raises(InvalidResumeDocumentError):
        fit_layout(synthetic_resume(1, 1), Generation(), 1, "fancy", fake_meter, 30)


def test_fit_prefers_the_roomier_preset_when_a_tighter_one_adds_nothing() -> None:
    content = synthetic_resume(2, 2, seed=15)

    layout = run(content, 1)

    assert layout.preset == "P0"
    assert layout.steps[-1] == "chose P0"
