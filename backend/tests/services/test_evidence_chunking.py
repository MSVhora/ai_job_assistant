import uuid
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest

from app.models import EvidenceKind
from app.services.evidence_pipeline.chunking import (
    CAPS,
    ItemView,
    build_chunks,
    count_tokens,
    split_to_cap,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
REPO = "ada/engine"


def view(
    kind: str,
    external_id: str,
    body: str,
    *,
    when: datetime | None = T0,
    project: str | None = REPO,
    title: str | None = None,
    private: bool = False,
    **meta: object,
) -> ItemView:
    return ItemView(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"{kind}:{external_id}"),
        kind=EvidenceKind(kind),
        external_id=external_id,
        project_key=project,
        title=title or body.splitlines()[0][:60],
        body=body,
        occurred_at=when,
        is_private=private,
        meta=dict(meta),
    )


def chunks_of(items: list[ItemView], kind: str, *, redact: bool = True):
    return [d for d in build_chunks(items, redaction_enabled=redact).drafts if d.kind == kind]


def test_pr_chunk_collects_squash_commits_dedupes_messages_and_caps_at_twenty() -> None:
    pr = view(
        "pull_request",
        "ada/engine#7",
        "Add loader\n\nStreams cards.",
        number=7,
        paths=["src/loader.py", "src/cards.py", "tests/test_loader.py"],
    )
    commits = [
        view(
            "commit",
            f"sha{i}",
            f"Step {i % 22}: tune buffer",
            when=T0 + timedelta(hours=i),
            pr_number=7,
        )
        for i in range(25)
    ]

    chunk = chunks_of([pr, *commits], "pr")[0]

    assert chunk.text.count("\n- ") == 20
    assert "Files changed: 3 (src/ x2, tests/ x1)" in chunk.text
    assert set(chunk.item_ids) == {pr.id, *(c.id for c in commits)}
    assert chunks_of([pr, *commits], "commit_cluster") == []


def test_commits_split_into_bursts_by_a_seven_day_gap_and_thirty_commit_cap() -> None:
    early = [
        view("commit", f"e{i}", f"Early work {i}", when=T0 + timedelta(days=i % 3))
        for i in range(4)
    ]
    late = [
        view("commit", f"l{i}", f"Late work {i}", when=T0 + timedelta(days=12 + i))
        for i in range(3)
    ]

    clusters = chunks_of([*early, *late], "commit_cluster")

    assert [len(c.item_ids) for c in clusters] == [4, 3]
    assert clusters[0].time_end is not None
    assert clusters[0].time_end < clusters[1].time_start  # type: ignore[operator]

    many = [
        view("commit", f"m{i}", f"Burst {i}", when=T0 + timedelta(minutes=i)) for i in range(65)
    ]
    assert [len(c.item_ids) for c in chunks_of(many, "commit_cluster")] == [30, 30, 5]


def test_a_nine_day_gap_starts_a_new_cluster() -> None:
    commits = [
        view("commit", "a", "First change", when=T0),
        view("commit", "b", "Second change", when=T0 + timedelta(days=9)),
    ]

    assert len(chunks_of(commits, "commit_cluster")) == 2


def test_repo_summary_truncates_readme_and_reports_contributions() -> None:
    summary = view("repo_summary", REPO, "Engine emulator\n\n" + "readme " * 2000, title=REPO)
    items = [
        summary,
        view("commit", "c1", "Ship loader", when=T0),
        view("commit", "c2", "Fix reader", when=T0 + timedelta(days=30)),
        view("pull_request", "ada/engine#1", "PR one", number=1),
    ]

    chunk = chunks_of(items, "repo_summary")[0]

    assert len(chunk.text) < 4300
    assert "Your contributions: 2 commits, 2026-01-01 to 2026-01-31, 1 pull requests" in chunk.text
    assert chunk.item_ids == (summary.id,)


def test_issue_and_review_items_become_their_own_chunks() -> None:
    items = [
        view("issue", "ada/engine#3", "Loader drops the last card", title="Loader bug"),
        view("review_comment", "ada/engine#21:review", "Needs a test for the empty case."),
    ]

    drafts = build_chunks(items, redaction_enabled=True).drafts

    assert sorted(d.kind for d in drafts) == ["issue", "review"]


def test_note_paragraphs_split_with_ten_percent_overlap() -> None:
    paragraphs = [f"Paragraph {i}: " + "decision rationale " * 25 for i in range(40)]
    note = view("note", "n1", "\n\n".join(paragraphs), project="note:design", title="Design")

    chunks = chunks_of([note], "note")

    assert len(chunks) > 1
    assert all(c.token_count <= CAPS["note"] for c in chunks)
    for first, second in pairwise(chunks):
        tail = first.text.split("\n\n")[-1]
        assert tail in second.text


def test_link_chunks_only_when_text_was_pasted() -> None:
    bare = view("link", "l1", "https://example.com", project="link:example.com", url_only=True)
    pasted = view(
        "link", "l2", "Talk notes about the loader", project="link:example.com", url_only=False
    )

    kinds = [
        (d.kind, d.item_ids) for d in build_chunks([bare, pasted], redaction_enabled=True).drafts
    ]

    assert kinds == [("note", (pasted.id,))]


def test_resume_lines_group_into_one_entry_per_project_key() -> None:
    lines = [
        view(
            "resume_line",
            f"r{i}",
            f"Reduced latency by {i}0 percent",
            project="resume:Analytical Ltd",
            title="Engineer at Analytical Ltd",
            when=None,
        )
        for i in range(3)
    ]
    other = view("resume_line", "x", "Built a game", project="resume:Pong", title="Pong", when=None)

    drafts = [
        d
        for d in build_chunks([*lines, other], redaction_enabled=True).drafts
        if d.kind == "resume_entry"
    ]

    assert [d.project_key for d in drafts] == ["resume:Analytical Ltd", "resume:Pong"]
    assert drafts[0].text.startswith("Engineer at Analytical Ltd\n- ")
    assert len(drafts[0].item_ids) == 3


def test_caps_are_enforced_with_the_token_counter() -> None:
    giant = view("issue", "ada/engine#9", "Long report. " + "token budget stress " * 3000)

    chunks = chunks_of([giant], "issue")

    assert len(chunks) > 1
    assert all(c.token_count <= CAPS["issue"] + 5 for c in chunks)
    assert all(c.token_count == count_tokens(c.text) for c in chunks)


def test_split_to_cap_hard_splits_a_single_oversized_paragraph() -> None:
    pieces = split_to_cap(["x" * 20_000], 100)

    assert len(pieces) > 1
    assert all(count_tokens(piece) <= 100 for piece in pieces)


def test_output_is_deterministic_and_independent_of_input_order() -> None:
    items = [
        view("commit", f"c{i}", f"Change {i}", when=T0 + timedelta(days=i)) for i in range(6)
    ] + [view("issue", "ada/engine#1", "An issue")]

    forward = build_chunks(items, redaction_enabled=True).drafts
    backward = build_chunks(list(reversed(items)), redaction_enabled=True).drafts

    assert [d.content_hash for d in forward] == [d.content_hash for d in backward]
    assert [d.kind for d in forward] == sorted(d.kind for d in forward)


def test_contains_private_is_true_when_any_member_is_private() -> None:
    items = [
        view("commit", "a", "Public change", when=T0),
        view("commit", "b", "Private change", when=T0 + timedelta(days=1), private=True),
    ]

    assert chunks_of(items, "commit_cluster")[0].contains_private is True
    assert chunks_of(items[:1], "commit_cluster")[0].contains_private is False


def test_chunk_text_is_redacted_and_the_item_is_untouched() -> None:
    token = "ghp_" + "z" * 36
    item = view("issue", "ada/engine#4", f"Call ada@example.com about {token}")

    result = build_chunks([item], redaction_enabled=True)

    chunk = result.drafts[0]
    assert "ada@example.com" not in chunk.text
    assert token not in chunk.text
    assert "<EMAIL_1>" in chunk.text
    assert result.redactions == {"EMAIL": 1, "TOKEN": 1}
    assert "ada@example.com" in item.body


def test_redaction_can_be_turned_off() -> None:
    item = view("issue", "ada/engine#4", "Call ada@example.com")

    chunk = build_chunks([item], redaction_enabled=False).drafts[0]

    assert "ada@example.com" in chunk.text


@pytest.mark.parametrize("kind", ["repo_summary", "pull_request"])
def test_items_without_content_still_produce_stable_hashes(kind: str) -> None:
    item = view(kind, "x", "Something", number=1)

    first = build_chunks([item], redaction_enabled=True).drafts
    second = build_chunks([item], redaction_enabled=True).drafts

    assert [d.content_hash for d in first] == [d.content_hash for d in second]
