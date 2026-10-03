import re
import uuid
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import PurePosixPath

from app.adapters.job_sources.base import json_array
from app.adapters.llm import estimate_tokens
from app.models.evidence import EvidenceKind
from app.services.evidence_pipeline.dedupe import CHUNKER_VERSION, chunk_hash, normalize_text
from app.services.redaction import redact

CAPS = {
    "pr": 3000,
    "commit_cluster": 2000,
    "repo_summary": 2000,
    "issue": 1500,
    "review": 1500,
    "note": 1500,
    "resume_entry": 800,
}
MAX_PR_COMMITS = 20
MAX_CLUSTER_COMMITS = 30
BURST_GAP = timedelta(days=7)
README_CHARS = 4000
MESSAGE_CHARS = 600
OVERLAP_FRACTION = 0.10
CHARS_PER_TOKEN = 4
TOP_DIRS = 4
_EPOCH = datetime.min.replace(tzinfo=UTC)
_NOTE_SPLIT = re.compile(r"\n\s*\n|\n(?=#{1,6}\s)")


@dataclass(frozen=True)
class ItemView:
    """The fields of an evidence item the chunker reads (keeps this module ORM-free)."""

    id: uuid.UUID
    kind: EvidenceKind
    external_id: str
    project_key: str | None
    title: str | None
    body: str
    occurred_at: datetime | None
    is_private: bool
    meta: dict[str, object] = field(default_factory=dict[str, object])


@dataclass(frozen=True)
class ChunkDraft:
    kind: str
    project_key: str | None
    title: str | None
    text: str
    item_ids: tuple[uuid.UUID, ...]
    time_start: datetime | None
    time_end: datetime | None
    contains_private: bool
    token_count: int
    content_hash: str


@dataclass(frozen=True)
class BuildResult:
    drafts: list[ChunkDraft]
    redactions: dict[str, int]


@lru_cache(maxsize=8192)
def count_tokens(text: str) -> int:
    return estimate_tokens([{"role": "user", "content": text}])


def _hard_split(paragraph: str, cap_tokens: int) -> list[str]:
    size = max(1, cap_tokens * CHARS_PER_TOKEN)
    return [paragraph[start : start + size] for start in range(0, len(paragraph), size)]


def _overlap_tail(parts: list[str], cap_tokens: int, fraction: float) -> list[str]:
    budget = int(cap_tokens * fraction)
    tail: list[str] = []
    used = 0
    for part in reversed(parts):
        tokens = count_tokens(part)
        if used + tokens > budget:
            break
        tail.insert(0, part)
        used += tokens
    return tail


def split_to_cap(
    paragraphs: Sequence[str],
    cap_tokens: int,
    *,
    overlap_fraction: float = 0.0,
    joiner: str = "\n\n",
) -> list[str]:
    """Pack paragraphs into pieces of at most ~`cap_tokens`, repeating a short tail as overlap."""
    fitted: list[str] = []
    for paragraph in paragraphs:
        text = paragraph.strip()
        if not text:
            continue
        fitted.extend(_hard_split(text, cap_tokens) if count_tokens(text) > cap_tokens else [text])
    pieces: list[str] = []
    current: list[str] = []
    used = 0
    for paragraph in fitted:
        tokens = count_tokens(paragraph)
        if current and used + tokens > cap_tokens:
            pieces.append(joiner.join(current))
            current = _overlap_tail(current, cap_tokens, overlap_fraction)
            used = sum(count_tokens(part) for part in current)
            if used + tokens > cap_tokens:
                current, used = [], 0
        current.append(paragraph)
        used += tokens
    if current:
        pieces.append(joiner.join(current))
    return pieces


class _Maker:
    def __init__(self, *, redaction_enabled: bool) -> None:
        self.redaction_enabled = redaction_enabled
        self.counts: Counter[str] = Counter()

    def _clean(self, text: str, *, count: bool = True) -> str:
        if not self.redaction_enabled:
            return text.strip()
        result = redact(text)
        if count:
            self.counts.update(result.counts)
        return result.text.strip()

    def __call__(
        self,
        kind: str,
        project_key: str | None,
        title: str | None,
        text: str,
        members: Sequence[ItemView],
    ) -> ChunkDraft:
        clean = self._clean(text)
        times = [member.occurred_at for member in members if member.occurred_at is not None]
        return ChunkDraft(
            kind=kind,
            project_key=project_key,
            title=self._clean(title, count=False) if title else None,
            text=clean,
            item_ids=tuple(dict.fromkeys(member.id for member in members)),
            time_start=min(times, default=None),
            time_end=max(times, default=None),
            contains_private=any(member.is_private for member in members),
            token_count=count_tokens(clean),
            content_hash=chunk_hash(CHUNKER_VERSION, clean),
        )


Make = Callable[[str, str | None, str | None, str, Sequence[ItemView]], ChunkDraft]


def _sorted(items: Sequence[ItemView]) -> list[ItemView]:
    return sorted(items, key=lambda item: (item.occurred_at or _EPOCH, item.external_id))


def _flat(text: str, limit: int = MESSAGE_CHARS) -> str:
    return normalize_text(text)[:limit]


def _path_summary(item: ItemView) -> str | None:
    paths = [path for path in json_array(item.meta.get("paths")) or [] if isinstance(path, str)]
    if not paths:
        return None
    tops = Counter(
        f"{PurePosixPath(path).parts[0]}/" if len(PurePosixPath(path).parts) > 1 else "(root)"
        for path in paths
    )
    dirs = ", ".join(f"{name} x{count}" for name, count in tops.most_common(TOP_DIRS))
    return f"Files changed: {len(paths)} ({dirs})"


def _pr_chunks(pr: ItemView, commits: list[ItemView], make: Make) -> list[ChunkDraft]:
    seen = {normalize_text(pr.body)}
    messages: list[str] = []
    for commit in _sorted(commits):
        message = _flat(commit.body)
        if message and normalize_text(message) not in seen:
            seen.add(normalize_text(message))
            messages.append(message)
    paragraphs = [pr.body]
    summary = _path_summary(pr)
    if summary:
        paragraphs.append(summary)
    if messages:
        paragraphs.append("Commits:\n" + "\n".join(f"- {m}" for m in messages[:MAX_PR_COMMITS]))
    return [
        make("pr", pr.project_key, pr.title, piece, [pr, *commits])
        for piece in split_to_cap(paragraphs, CAPS["pr"])
    ]


def _bursts(commits: list[ItemView]) -> list[list[ItemView]]:
    groups: list[list[ItemView]] = []
    previous: datetime | None = None
    for commit in _sorted(commits):
        stamp = commit.occurred_at
        starts_new = (
            not groups
            or len(groups[-1]) >= MAX_CLUSTER_COMMITS
            or (previous is not None and stamp is not None and stamp - previous >= BURST_GAP)
        )
        if starts_new:
            groups.append([])
        groups[-1].append(commit)
        previous = stamp or previous
    return groups


def _cluster_chunks(
    project_key: str | None, commits: list[ItemView], make: Make
) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    for group in _bursts(commits):
        lines = [
            f"{(commit.occurred_at or _EPOCH):%Y-%m-%d} {_flat(commit.body)}" for commit in group
        ]
        first = group[0].occurred_at
        last = group[-1].occurred_at
        span = f"{first:%Y-%m-%d}" if first else "undated"
        if last and first and last.date() != first.date():
            span += f" to {last:%Y-%m-%d}"
        title = f"{project_key or 'commits'}: {len(group)} commits, {span}"
        chunks.extend(
            make("commit_cluster", project_key, title, piece, group)
            for piece in split_to_cap(lines, CAPS["commit_cluster"], joiner="\n")
        )
    return chunks


def _contribution_line(commits: list[ItemView], pull_requests: int) -> str:
    stamps = [commit.occurred_at for commit in commits if commit.occurred_at is not None]
    span = f", {min(stamps):%Y-%m-%d} to {max(stamps):%Y-%m-%d}" if stamps else ""
    return f"Your contributions: {len(commits)} commits{span}, {pull_requests} pull requests"


def _summary_chunks(
    item: ItemView, commits: list[ItemView], pull_requests: int, make: Make
) -> list[ChunkDraft]:
    body = item.body[:README_CHARS]
    paragraphs = [body, _contribution_line(commits, pull_requests)]
    return [
        make("repo_summary", item.project_key, item.title, piece, [item])
        for piece in split_to_cap(paragraphs, CAPS["repo_summary"])
    ]


def _single_chunks(kind: str, item: ItemView, make: Make) -> list[ChunkDraft]:
    return [
        make(kind, item.project_key, item.title, piece, [item])
        for piece in split_to_cap([item.body], CAPS[kind])
    ]


def _note_chunks(item: ItemView, make: Make) -> list[ChunkDraft]:
    paragraphs = [part for part in _NOTE_SPLIT.split(item.body) if part.strip()]
    return [
        make("note", item.project_key, item.title, piece, [item])
        for piece in split_to_cap(paragraphs, CAPS["note"], overlap_fraction=OVERLAP_FRACTION)
    ]


def _resume_chunks(project_key: str | None, lines: list[ItemView], make: Make) -> list[ChunkDraft]:
    ordered = sorted(lines, key=lambda line: line.external_id)
    header = ordered[0].title or project_key or "Resume entry"
    budget = max(1, CAPS["resume_entry"] - count_tokens(header))
    bullets = [f"- {line.body}" for line in ordered]
    return [
        make("resume_entry", project_key, header, f"{header}\n{piece}", ordered)
        for piece in split_to_cap(bullets, budget, joiner="\n")
    ]


def build_chunks(items: Sequence[ItemView], *, redaction_enabled: bool) -> BuildResult:
    """Deterministic chunk drafts for kept evidence (plus squash commits attached to a PR)."""
    make = _Maker(redaction_enabled=redaction_enabled)
    ordered = _sorted(items)
    drafts: list[ChunkDraft] = []
    attached: dict[tuple[str | None, int], list[ItemView]] = {}
    standalone: dict[str | None, list[ItemView]] = {}
    commits_by_project: dict[str | None, list[ItemView]] = {}
    prs_by_project: Counter[str | None] = Counter()
    resume: dict[str | None, list[ItemView]] = {}
    for item in ordered:
        if item.kind is EvidenceKind.commit:
            commits_by_project.setdefault(item.project_key, []).append(item)
            number = item.meta.get("pr_number")
            if isinstance(number, int):
                attached.setdefault((item.project_key, number), []).append(item)
            else:
                standalone.setdefault(item.project_key, []).append(item)
        elif item.kind is EvidenceKind.pull_request:
            prs_by_project[item.project_key] += 1
        elif item.kind is EvidenceKind.resume_line:
            resume.setdefault(item.project_key, []).append(item)
    for item in ordered:
        drafts.extend(_item_chunks(item, attached, commits_by_project, prs_by_project, make))
    for project_key, commits in standalone.items():
        drafts.extend(_cluster_chunks(project_key, commits, make))
    for project_key, lines in resume.items():
        drafts.extend(_resume_chunks(project_key, lines, make))
    # Stable sort: pieces of one item keep their document order.
    drafts.sort(key=lambda d: (d.kind, d.project_key or "", d.time_start or _EPOCH))
    return BuildResult(drafts=drafts, redactions=dict(make.counts))


def _item_chunks(
    item: ItemView,
    attached: dict[tuple[str | None, int], list[ItemView]],
    commits_by_project: dict[str | None, list[ItemView]],
    prs_by_project: Counter[str | None],
    make: Make,
) -> list[ChunkDraft]:
    kind = item.kind
    if kind is EvidenceKind.pull_request:
        number = item.meta.get("number")
        commits = attached.get((item.project_key, number), []) if isinstance(number, int) else []
        return _pr_chunks(item, commits, make)
    if kind is EvidenceKind.repo_summary:
        return _summary_chunks(
            item,
            commits_by_project.get(item.project_key, []),
            prs_by_project[item.project_key],
            make,
        )
    if kind is EvidenceKind.issue:
        return _single_chunks("issue", item, make)
    if kind is EvidenceKind.review_comment:
        return _single_chunks("review", item, make)
    if kind is EvidenceKind.note or (
        kind is EvidenceKind.link and item.meta.get("url_only") is False
    ):
        return _note_chunks(item, make)
    return []
