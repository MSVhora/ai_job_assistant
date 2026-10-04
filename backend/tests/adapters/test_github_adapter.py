import json
import logging
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.adapters.evidence_sources.base import (
    EvidenceSourceConfigError,
    EvidenceSourceError,
    EvidenceSourcePausedError,
)
from app.adapters.evidence_sources.github import GitHubSource
from app.core.config import Settings, get_settings
from app.models import EvidenceKind
from app.schemas.evidence import ScopeState, SyncPage

GOLDEN = Path(__file__).resolve().parents[1] / "eval" / "golden" / "github"
TOKEN = "ghp_" + "t0ken" * 8
REF = "ada/engine"


def golden(name: str) -> Any:
    return json.loads((GOLDEN / name).read_text())


class FakeGitHub:
    """Routes MockTransport requests to golden payloads and records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.graphql_bodies: list[dict[str, Any]] = []
        self.commit_pages = ["graphql_commits_page1.json", "graphql_commits_page2.json"]
        self.repo_etag = '"etag-1"'
        self.headers: dict[str, str] = {
            "x-ratelimit-remaining": "4900",
            "x-ratelimit-limit": "5000",
        }
        self.override: Any = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.override is not None and (response := self.override(request)) is not None:
            return response
        path = request.url.path
        if request.method == "POST" and path == "/graphql":
            return self._graphql(request)
        routes: dict[str, tuple[Any, dict[str, str]]] = {
            "/user": (golden("user.json"), {"x-oauth-scopes": "repo, read:user"}),
            "/user/repos": (golden("repos.json"), {}),
            f"/repos/{REF}": (golden("repo_engine.json"), {"etag": self.repo_etag}),
            f"/repos/{REF}/languages": (golden("languages_engine.json"), {}),
        }
        if path == f"/repos/{REF}/readme":
            return httpx.Response(200, text=(GOLDEN / "readme_engine.md").read_text())
        if path in routes:
            if path == f"/repos/{REF}" and request.headers.get("if-none-match") == self.repo_etag:
                return httpx.Response(304, headers=self.headers)
            body, extra = routes[path]
            return httpx.Response(200, json=body, headers={**self.headers, **extra})
        return httpx.Response(404, json={"message": "Not Found"})

    def _graphql(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.graphql_bodies.append(body)
        query: str = body["query"]
        if "contributionYears" in query:
            return httpx.Response(
                200, json=golden("graphql_contribution_years.json"), headers=self.headers
            )
        if "commitContributionsByRepository" in query:
            year = body["variables"]["from"][:4]
            return httpx.Response(
                200, json=golden(f"graphql_contributions_{year}.json"), headers=self.headers
            )
        if "history(" in query:
            index = 0 if body["variables"]["after"] is None else 1
            return httpx.Response(200, json=golden(self.commit_pages[index]), headers=self.headers)
        if "reviews(first" in query:
            payload = golden("graphql_reviews.json")
        elif "... on Issue" in query:
            payload = golden("graphql_issues.json")
        else:
            payload = golden("graphql_prs.json")
        return httpx.Response(200, json=payload, headers=self.headers)


@pytest.fixture(autouse=True)
def _fast_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "github_token", TOKEN)
    monkeypatch.setattr(settings, "llm_retry_attempts", 2)
    monkeypatch.setattr(settings, "llm_retry_base_delay_s", 0.0)


def source_for(fake: FakeGitHub, **overrides: object) -> GitHubSource:
    settings = Settings(_env_file=None, github_token=TOKEN, **overrides)  # type: ignore[arg-type]
    return GitHubSource(settings=settings, transport=httpx.MockTransport(fake))


async def collect(source: GitHubSource, state: ScopeState | None = None) -> list[SyncPage]:
    return [page async for page in source.sync_scope(state or ScopeState(ref=REF))]


def items_of(pages: list[SyncPage], kind: EvidenceKind) -> list[Any]:
    return [item for page in pages for item in page.items if item.kind is kind]


async def test_identify_returns_login_node_id_and_token_scopes() -> None:
    fake = FakeGitHub()

    identity = await source_for(fake).identify()

    assert (identity.login, identity.node_id) == ("ada", "U_kgDOADA")
    assert identity.permissions == ["repo", "read:user"]
    assert fake.requests[0].headers["authorization"] == f"Bearer {TOKEN}"


async def test_identify_carries_the_public_name_location_and_email() -> None:
    identity = await source_for(FakeGitHub()).identify()

    assert (identity.name, identity.location) == ("Augusta Byron", "London, England")
    assert identity.emails == ["ada@example.com"]


async def test_identify_leaves_name_and_location_empty_when_the_profile_hides_them() -> None:
    fake = FakeGitHub()
    fake.override = lambda request: (
        httpx.Response(200, json={"login": "ada", "name": None})
        if request.url.path == "/user"
        else None
    )

    identity = await source_for(fake).identify()

    assert (identity.name, identity.location, identity.emails) == (None, None, [])


async def test_identify_is_cached_for_the_run() -> None:
    fake = FakeGitHub()
    source = source_for(fake)

    await source.identify()
    await source.identify()

    assert len(fake.requests) == 1


async def test_list_scopes_flags_private_fork_and_marks_old_repos_outside_the_lookback() -> None:
    scopes = await source_for(FakeGitHub()).list_scopes()

    by_ref = {scope.ref: scope for scope in scopes}
    assert list(by_ref) == [
        "ada/engine",
        "ada/secret-notes",
        "babbage/difference",
        "ada/ancient",
        "booth/private-app",
        "outsider/lib",
    ]
    assert by_ref["ada/secret-notes"].is_private is True
    assert by_ref["babbage/difference"].is_fork is True
    assert by_ref["ada/engine"].description == "Analytical engine emulator"


async def test_list_scopes_marks_contributed_repos_and_adds_ones_the_token_does_not_list() -> None:
    scopes = {scope.ref: scope for scope in await source_for(FakeGitHub()).list_scopes()}

    assert {ref for ref, scope in scopes.items() if scope.contributed} == {
        "ada/engine",
        "ada/ancient",
        "booth/private-app",
        "outsider/lib",
    }
    assert scopes["booth/private-app"].is_private is True
    assert scopes["outsider/lib"].is_private is False
    assert scopes["outsider/lib"].pushed_at is None


async def test_a_contributed_repo_is_never_outside_the_lookback_but_others_are() -> None:
    scopes = {scope.ref: scope for scope in await source_for(FakeGitHub()).list_scopes()}

    assert scopes["ada/ancient"].contributed is True
    assert scopes["ada/ancient"].outside_lookback is False
    assert scopes["ada/engine"].outside_lookback is False


async def test_an_old_repo_without_contributions_is_flagged_outside_the_lookback() -> None:
    fake = FakeGitHub()
    fake.override = lambda request: (
        httpx.Response(200, json=golden("graphql_contribution_years.json") | {"data": {}})
        if request.method == "POST" and b"contributionYears" in request.content
        else None
    )

    scopes = {scope.ref: scope for scope in await source_for(fake).list_scopes()}

    assert scopes["ada/ancient"].outside_lookback is True
    assert not any(scope.contributed for scope in scopes.values())


async def test_a_failing_contribution_query_degrades_to_the_plain_repository_list() -> None:
    fake = FakeGitHub()
    fake.override = lambda request: (
        httpx.Response(200, json={"errors": [{"type": "RATE_LIMITED", "message": "slow down"}]})
        if request.method == "POST" and request.url.path == "/graphql"
        else None
    )

    scopes = await source_for(fake).list_scopes()

    assert [scope.ref for scope in scopes][:3] == [
        "ada/engine",
        "ada/secret-notes",
        "babbage/difference",
    ]
    assert not any(scope.contributed for scope in scopes)


async def test_partial_contribution_results_are_kept_when_an_organization_blocks_access() -> None:
    fake = FakeGitHub()

    def partial(request: httpx.Request) -> httpx.Response | None:
        if request.method == "POST" and b"commitContributionsByRepository" in request.content:
            payload = golden("graphql_contributions_2026.json")
            payload["errors"] = [{"type": "FORBIDDEN", "message": "SAML enforcement"}]
            return httpx.Response(200, json=payload)
        return None

    fake.override = partial

    scopes = {scope.ref: scope for scope in await source_for(fake).list_scopes()}

    assert scopes["booth/private-app"].contributed is True


async def test_sync_scope_yields_every_evidence_kind_with_normalized_fields() -> None:
    pages = await collect(source_for(FakeGitHub()))

    kinds = {item.kind for page in pages for item in page.items}
    assert kinds == {
        EvidenceKind.repo_summary,
        EvidenceKind.commit,
        EvidenceKind.pull_request,
        EvidenceKind.review_comment,
        EvidenceKind.issue,
    }
    summary = items_of(pages, EvidenceKind.repo_summary)[0]
    assert summary.external_id == REF
    assert "Python 80%" in summary.body
    assert "punch-card loader" in summary.body
    assert summary.meta["stars"] == 42
    commits = items_of(pages, EvidenceKind.commit)
    assert [c.external_id for c in commits] == ["a1" * 20, "b2" * 20, "c3" * 20]
    assert commits[0].title == "Implement punch-card loader"
    assert commits[0].meta == {"additions": 10, "deletions": 2, "changed_files": 3, "parents": 1}
    assert commits[2].meta["parents"] == 2
    prs = {pr.external_id: pr for pr in items_of(pages, EvidenceKind.pull_request)}
    assert prs[f"{REF}#7"].meta["merge_commit_oid"] == "a1" * 20
    assert prs[f"{REF}#7"].meta["paths"] == ["src/loader.py", "tests/test_loader.py"]
    assert prs[f"{REF}#8"].meta["paths"] == ["uv.lock"]
    issue = items_of(pages, EvidenceKind.issue)[0]
    assert issue.meta["labels"] == ["bug"]


async def test_pull_request_with_truncated_file_list_omits_paths() -> None:
    pages = await collect(source_for(FakeGitHub()))

    big = next(pr for pr in items_of(pages, EvidenceKind.pull_request) if pr.meta["number"] == 9)

    assert "paths" not in big.meta
    assert big.meta["paths_truncated"] is True


async def test_review_comments_join_review_text_and_skip_empty_reviews() -> None:
    pages = await collect(source_for(FakeGitHub()))

    reviews = items_of(pages, EvidenceKind.review_comment)

    assert len(reviews) == 1
    assert reviews[0].external_id == f"{REF}#21:review"
    assert "Needs a test for the empty case." in reviews[0].body
    assert "src/cache.py: Off by one here." in reviews[0].body
    assert reviews[0].meta == {"pr_number": 21, "reviews": 1, "comments": 1}


async def test_cursor_advances_per_page_and_ends_done_with_a_watermark() -> None:
    pages = await collect(source_for(FakeGitHub()))

    cursors = [page.next_cursor for page in pages if page.next_cursor is not None]
    assert [cursor["stage"] for cursor in cursors] == [
        "commits",
        "commits",
        "prs",
        "reviews",
        "issues",
        "done",
        "done",
    ]
    assert cursors[1]["commits_after"] == "cursor-1"
    assert cursors[2]["commits_after"] is None
    assert cursors[-1]["watermark"] is not None


async def test_own_work_is_filtered_by_the_server_queries() -> None:
    fake = FakeGitHub()

    await collect(source_for(fake))

    commit_vars = next(b["variables"] for b in fake.graphql_bodies if "history(" in b["query"])
    assert commit_vars["author"] == "U_kgDOADA"
    searches = [b["variables"]["q"] for b in fake.graphql_bodies if "search(" in b["query"]]
    assert any("author:ada is:pr" in q for q in searches)
    assert any("reviewed-by:ada -author:ada is:pr" in q for q in searches)
    assert any("author:ada is:issue" in q for q in searches)
    assert all(q.startswith(f"repo:{REF} ") for q in searches)


async def test_resuming_mid_pass_skips_finished_stages() -> None:
    fake = FakeGitHub()
    cursor = {
        "stage": "prs",
        "since": "2026-01-01T00:00:00+00:00",
        "started_at": "2026-10-03T00:00:00+00:00",
    }

    pages = await collect(source_for(fake), ScopeState(ref=REF, cursor=cursor))

    assert not any("history(" in b["query"] for b in fake.graphql_bodies)
    assert not any(r.url.path.endswith("/languages") for r in fake.requests)
    assert {item.kind for page in pages for item in page.items} == {
        EvidenceKind.pull_request,
        EvidenceKind.review_comment,
        EvidenceKind.issue,
    }


async def test_incremental_pass_starts_from_the_watermark_with_a_one_day_overlap() -> None:
    fake = FakeGitHub()
    cursor = {"stage": "done", "watermark": "2026-09-10T00:00:00+00:00"}

    await collect(source_for(fake), ScopeState(ref=REF, cursor=cursor))

    commit_vars = next(b["variables"] for b in fake.graphql_bodies if "history(" in b["query"])
    assert commit_vars["since"] == "2026-09-09T00:00:00+00:00"
    searches = [b["variables"]["q"] for b in fake.graphql_bodies if "search(" in b["query"]]
    assert all("updated:>=2026-09-09" in q for q in searches)


async def test_unchanged_repo_summary_is_a_304_that_costs_no_budget() -> None:
    fake = FakeGitHub()
    cursor = {
        "stage": "done",
        "summary_etag": fake.repo_etag,
        "watermark": "2026-09-10T00:00:00+00:00",
    }
    source = source_for(fake)

    pages = await collect(source, ScopeState(ref=REF, cursor=cursor))

    assert items_of(pages, EvidenceKind.repo_summary) == []
    summary_requests = [r for r in fake.requests if r.url.path == f"/repos/{REF}"]
    assert summary_requests[0].headers["if-none-match"] == fake.repo_etag
    assert not any(r.url.path.endswith("/languages") for r in fake.requests)
    assert source.requests_used == len(fake.requests) - 1


async def test_no_request_ever_reads_file_contents_or_patches() -> None:
    fake = FakeGitHub()

    await collect(source_for(fake))
    await source_for(fake).list_scopes()

    allowed = {
        "/user",
        "/user/repos",
        "/graphql",
        f"/repos/{REF}",
        f"/repos/{REF}/languages",
        f"/repos/{REF}/readme",
    }
    assert {r.url.path for r in fake.requests} <= allowed
    assert not any("/contents" in str(r.url) or "/commits/" in str(r.url) for r in fake.requests)
    assert not any(r.url.path.endswith((".diff", ".patch")) for r in fake.requests)
    for body in fake.graphql_bodies:
        assert "patch" not in body["query"].lower()
        assert "Blob" not in body["query"]


async def test_request_budget_pauses_before_exceeding() -> None:
    fake = FakeGitHub()
    source = source_for(fake, github_max_requests_per_run=3)

    with pytest.raises(EvidenceSourcePausedError) as caught:
        await collect(source)

    assert len(fake.requests) == 3
    assert caught.value.resume_at is not None
    assert "budget" in caught.value.reason


async def test_low_remaining_rate_limit_pauses_the_run() -> None:
    fake = FakeGitHub()
    fake.headers = {
        "x-ratelimit-remaining": "100",
        "x-ratelimit-limit": "5000",
        "x-ratelimit-reset": "1893456000",
    }
    source = source_for(fake, github_min_remaining_pct=10)

    await source.identify()
    with pytest.raises(EvidenceSourcePausedError) as caught:
        await source.list_scopes()

    assert caught.value.resume_at is not None
    assert caught.value.resume_at.year == 2030


async def test_long_retry_after_pauses_instead_of_sleeping() -> None:
    fake = FakeGitHub()
    fake.override = lambda request: httpx.Response(
        403, headers={"retry-after": "3600"}, json={"message": "secondary rate limit"}
    )

    with pytest.raises(EvidenceSourcePausedError) as caught:
        await source_for(fake).identify()

    assert caught.value.resume_at is not None
    assert len(fake.requests) == 1


async def test_short_retry_after_is_retried() -> None:
    fake = FakeGitHub()
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response | None:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return None

    fake.override = flaky

    identity = await source_for(fake).identify()

    assert identity.login == "ada"
    assert calls["n"] == 2


async def test_server_errors_are_retried_then_reported_without_internals() -> None:
    fake = FakeGitHub()
    fake.override = lambda request: httpx.Response(503, text=f"upstream said {TOKEN}")

    with pytest.raises(EvidenceSourceError) as caught:
        await source_for(fake).identify()

    assert len(fake.requests) == 2
    assert TOKEN not in str(caught.value)


async def test_rejected_token_raises_a_config_error_that_hides_the_token() -> None:
    fake = FakeGitHub()
    fake.override = lambda request: httpx.Response(401, json={"message": "Bad credentials"})

    with pytest.raises(EvidenceSourceConfigError) as caught:
        await source_for(fake).identify()

    assert "401" in str(caught.value)
    assert TOKEN not in str(caught.value)


async def test_inaccessible_repository_is_a_scope_level_error() -> None:
    with pytest.raises(EvidenceSourceError, match="not accessible"):
        await collect(source_for(FakeGitHub()), ScopeState(ref="ghost/missing"))


async def test_invalid_repository_reference_is_rejected_before_any_request() -> None:
    fake = FakeGitHub()

    with pytest.raises(EvidenceSourceError, match="invalid repository"):
        await collect(source_for(fake), ScopeState(ref="../../etc/passwd"))

    assert fake.requests == []


async def test_graphql_errors_become_source_errors_and_rate_limits_pause() -> None:
    fake = FakeGitHub()
    fake.override = lambda r: (
        httpx.Response(200, json={"errors": [{"type": "NOT_FOUND", "message": "x"}]})
        if r.url.path == "/graphql"
        else None
    )
    with pytest.raises(EvidenceSourceError, match="GraphQL"):
        await collect(source_for(fake), ScopeState(ref=REF, cursor={"stage": "commits"}))

    limited = FakeGitHub()
    limited.override = lambda r: (
        httpx.Response(200, json={"errors": [{"type": "RATE_LIMITED", "message": "x"}]})
        if r.url.path == "/graphql"
        else None
    )
    with pytest.raises(EvidenceSourcePausedError):
        await collect(source_for(limited), ScopeState(ref=REF, cursor={"stage": "commits"}))


async def test_missing_token_is_reported_unconfigured_and_never_calls_github(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeGitHub()
    source = GitHubSource(
        settings=Settings(_env_file=None, github_token=None), transport=httpx.MockTransport(fake)
    )

    assert source.is_configured() is False
    with pytest.raises(EvidenceSourceConfigError):
        await source.identify()
    assert fake.requests == []


async def test_normalize_rejects_unknown_kinds() -> None:
    with pytest.raises(EvidenceSourceError, match="cannot normalize"):
        source_for(FakeGitHub()).normalize({"kind": "tweet", "repo": REF, "node": {}})


async def test_token_never_reaches_the_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    fake = FakeGitHub()
    fake.override = lambda request: httpx.Response(503, text=TOKEN)

    with pytest.raises(EvidenceSourceError):
        await source_for(fake).identify()

    assert TOKEN not in "\n".join(record.getMessage() for record in caplog.records)
