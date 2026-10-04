import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.core.errors import CannotFitError, InvalidResumeDocumentError
from app.schemas.resume_document import (
    Generation,
    Layout,
    NotIncluded,
    ResumeContent,
)
from app.services.resume_blocks import blocks
from app.services.resume_render.typst_data import PRESETS, TEMPLATES, JsonObject, Preset, build_data

logger = logging.getLogger(__name__)

Meter = Callable[[JsonObject], int]


@dataclass(frozen=True)
class FitBullet:
    id: str
    block_id: str
    priority: float
    pinned: bool
    position: int


@dataclass
class _Search:
    """Compile accounting shared by all presets of one fit run."""

    meter: Meter
    limit: int
    used: int = 0
    exhausted: bool = False

    def pages(self, data: JsonObject) -> int | None:
        if self.used >= self.limit:
            self.exhausted = True
            return None
        self.used += 1
        return self.meter(data)


@dataclass
class _Outcome:
    preset: Preset
    count: int
    pages: int
    mass: float


@dataclass
class _Measured:
    content: ResumeContent
    template: str
    ordering: list[FitBullet]
    search: _Search
    steps: list[str]

    def pages_for(self, count: int, preset: Preset) -> int | None:
        included = frozenset(bullet.id for bullet in self.ordering[:count])
        return self.search.pages(build_data(self.content, included, preset, self.template))


def _eligible(content: ResumeContent) -> tuple[list[FitBullet], list[NotIncluded]]:
    """Bullets that may be placed, and those that may not (flagged for review)."""
    usable: list[FitBullet] = []
    flagged: list[NotIncluded] = []
    for entry in blocks(content):
        for bullet in entry.highlights:
            if bullet.check == "passed":
                usable.append(
                    FitBullet(bullet.id, entry.id, bullet.score, bullet.pinned, len(usable))
                )
            else:
                flagged.append(
                    NotIncluded(id=bullet.id, priority=bullet.score, reason="needs_review")
                )
    return usable, flagged


def priority_order(bullets: list[FitBullet]) -> list[FitBullet]:
    """Pinned first, then each block's best bullet (its anchor), then the rest by priority."""
    anchors: dict[str, FitBullet] = {}
    for bullet in bullets:
        best = anchors.get(bullet.block_id)
        if best is None or (bullet.priority, -bullet.position) > (best.priority, -best.position):
            anchors[bullet.block_id] = bullet
    anchor_ids = {bullet.id for bullet in anchors.values()}

    def rank(bullet: FitBullet) -> tuple[int, float, int]:
        group = 0 if bullet.pinned else 1 if bullet.id in anchor_ids else 2
        return (group, -bullet.priority, bullet.position)

    return sorted(bullets, key=rank)


def _largest_prefix(measured: _Measured, preset: Preset, target: int) -> tuple[int, int] | None:
    """(bullet count, pages) of the longest priority prefix that fits `target` pages, if any."""
    total = len(measured.ordering)
    known: dict[int, int] = {}

    def fits(count: int) -> bool:
        pages = measured.pages_for(count, preset)
        if pages is None:
            return False
        known[count] = pages
        return pages <= target

    if fits(total):
        return total, known[total]
    if not fits(0):
        return None
    low, high = 0, total
    while high - low > 1:
        middle = (low + high) // 2
        if fits(middle):
            low = middle
        else:
            high = middle
    return low, known[low]


def _mass(ordering: list[FitBullet], count: int) -> float:
    return sum(bullet.priority for bullet in ordering[:count])


def _search_presets(measured: _Measured, target: int) -> _Outcome | None:
    best: _Outcome | None = None
    for preset in PRESETS:
        found = _largest_prefix(measured, preset, target)
        if found is None:
            measured.steps.append(f"{preset.name}: even the fixed sections exceed {target} page(s)")
        else:
            count, pages = found
            mass = _mass(measured.ordering, count)
            measured.steps.append(
                f"{preset.name}: {count} of {len(measured.ordering)} bullets, {pages} page(s)"
            )
            if best is None or mass > best.mass:
                best = _Outcome(preset, count, pages, mass)
            if count == len(measured.ordering):
                break
        if measured.search.exhausted:
            measured.steps.append("compile budget reached")
            break
    return best


def _exclusions(
    generation: Generation,
    left_out: list[FitBullet],
    flagged: list[NotIncluded],
) -> list[NotIncluded]:
    skipped = [
        NotIncluded(id=b.id, priority=b.priority, reason="did_not_fit")
        for b in sorted(left_out, key=lambda b: (-b.priority, b.position))
    ]
    skipped += flagged
    skipped += [
        NotIncluded(id=str(item.achievement_id), priority=item.priority, reason="not_written")
        for item in generation.pool
        if not item.written
    ]
    skipped += [
        NotIncluded(id=item.block_id, priority=item.priority, reason="overlap_omitted")
        for item in generation.omitted_roles
    ]
    return skipped


def fit_layout(
    content: ResumeContent,
    generation: Generation,
    page_target: int,
    template: str,
    meter: Meter,
    max_compiles: int,
) -> Layout:
    """Largest priority-ordered set of written, passing bullets that fits `page_target` pages."""
    if template not in TEMPLATES:
        msg = f"unknown resume template: {template}"
        raise InvalidResumeDocumentError(msg)
    usable, flagged = _eligible(content)
    ordering = priority_order(usable)
    measured = _Measured(content, template, ordering, _Search(meter, max_compiles), [])
    best = _search_presets(measured, page_target)
    if best is None or (ordering and best.count == 0):
        logger.warning(
            "resume.fit cannot_fit target=%s bullets=%s compiles=%s",
            page_target,
            len(ordering),
            measured.search.used,
        )
        raise CannotFitError
    chosen = {bullet.id for bullet in ordering[: best.count]}
    left_out = [bullet for bullet in usable if bullet.id not in chosen]
    measured.steps.append(f"chose {best.preset.name}")
    skipped = _exclusions(generation, left_out, flagged)
    nothing_left = not any(
        item.reason in {"did_not_fit", "needs_review", "not_written"} for item in skipped
    )
    logger.info(
        "resume.fit pages=%s preset=%s included=%s compiles=%s",
        best.pages,
        best.preset.name,
        best.count,
        measured.search.used,
    )
    return Layout(
        pages=best.pages,
        preset=best.preset.name,
        font_pt=best.preset.font_pt,
        margin_in=best.preset.margin_in,
        included_ids=[bullet.id for bullet in usable if bullet.id in chosen],
        not_included=skipped,
        steps=measured.steps,
        short_on_evidence=nothing_left and best.pages < page_target,
    )


def unfitted_layout(content: ResumeContent, generation: Generation, reason: str) -> Layout:
    """Stored when generation succeeded but nothing fits: nothing is placed, nothing is lost."""
    usable, flagged = _eligible(content)
    return Layout(
        included_ids=[],
        not_included=_exclusions(generation, usable, flagged),
        steps=[reason],
    )
