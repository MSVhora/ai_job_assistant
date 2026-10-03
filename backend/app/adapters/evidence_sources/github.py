import logging
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

from app.adapters.evidence_sources.base import (
    EvidenceSourceConfigError,
    EvidenceSourceError,
    EvidenceSourcePausedError,
    RawEvidence,
)
from app.adapters.job_sources.base import json_array, json_object, parse_datetime
from app.adapters.retry import TransientError, retry_after_header, with_retry
from app.core.config import Settings, get_settings
from app.schemas.evidence import (
    EvidenceItemData,
    EvidenceKind,
    RateLimitInfo,
    ScopeCandidate,
    ScopeState,
    SourceIdentity,
    SyncPage,
)

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 30.0
MAX_INLINE_WAIT_S = 30.0
REPOS_PER_PAGE = 100
MAX_REPO_PAGES = 10
COMMITS_PAGE_SIZE = 50
SEARCH_PAGE_SIZE = 25
README_MAX_CHARS = 8000
PASS_OVERLAP = timedelta(days=1)
FALLBACK_RESUME = timedelta(hours=1)
DAYS_PER_YEAR = 365
RETRYABLE_STATUS = frozenset({500, 502, 503, 504})
HTTP_NOT_FOUND = 404
HTTP_NOT_MODIFIED = 304
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429
HTTP_CLIENT_ERROR = 400
JSON_ACCEPT = "application/vnd.github+json"
RAW_ACCEPT = "application/vnd.github.raw+json"
REF_RE = re.compile(r"^[\w.-]+/[\w.-]+$")

COMMITS_QUERY = """
query($owner: String!, $name: String!, $author: ID!, $since: GitTimestamp, $after: String) {
  rateLimit { limit remaining resetAt }
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: __PAGE__, after: $after, since: $since, author: {id: $author}) {
            pageInfo { hasNextPage endCursor }
            nodes {
              oid messageHeadline messageBody committedDate url additions deletions
              changedFilesIfAvailable parents { totalCount }
            }
          }
        }
      }
    }
  }
}
""".replace("__PAGE__", str(COMMITS_PAGE_SIZE))

_SEARCH_WRAPPER = """
query($q: String!, $after: String__VARS__) {
  rateLimit { limit remaining resetAt }
  search(query: $q, type: ISSUE, first: __PAGE__, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes { __NODES__ }
  }
}
"""


def _search_query_text(variables: str, nodes: str) -> str:
    return (
        _SEARCH_WRAPPER.replace("__VARS__", variables)
        .replace("__PAGE__", str(SEARCH_PAGE_SIZE))
        .replace("__NODES__", nodes)
    )


PULL_REQUESTS_QUERY = _search_query_text(
    "",
    """... on PullRequest {
      number title body url createdAt mergedAt state additions deletions changedFiles
      mergeCommit { oid } author { login } files(first: 100) { nodes { path } }
    }""",
)

REVIEWS_QUERY = _search_query_text(
    ", $login: String!",
    """... on PullRequest {
      number title url createdAt mergedAt author { login }
      reviews(first: 20, author: $login) {
        nodes { id body submittedAt url comments(first: 20) { nodes { body path } } }
      }
    }""",
)

ISSUES_QUERY = _search_query_text(
    "",
    """... on Issue {
      number title body url createdAt state author { login }
      labels(first: 10) { nodes { name } }
    }""",
)

Stage = Literal["summary", "commits", "prs", "reviews", "issues", "done"]
SearchField = Literal["prs_after", "reviews_after", "issues_after"]


@dataclass(frozen=True)
class _SearchSpec:
    query: str
    terms: str
    kind: EvidenceKind
    cursor_field: SearchField
    next_stage: Stage
    variables: dict[str, object] = field(default_factory=dict[str, object])


_STAGES: tuple[Stage, ...] = ("summary", "commits", "prs", "reviews", "issues")


class GitHubCursor(BaseModel):
    """Resume point for one scope: which stage and page a pass reached, plus the watermark."""

    stage: Stage | None = None
    since: str | None = None
    started_at: str | None = None
    watermark: str | None = None
    summary_etag: str | None = None
    commits_after: str | None = None
    prs_after: str | None = None
    reviews_after: str | None = None
    issues_after: str | None = None

    def begin_pass(self, now: datetime, floor: datetime) -> "GitHubCursor":
        watermark = parse_datetime(self.watermark)
        since = watermark - PASS_OVERLAP if watermark is not None else floor
        return GitHubCursor(
            stage="summary",
            since=since.isoformat(),
            started_at=now.isoformat(),
            watermark=self.watermark,
            summary_etag=self.summary_etag,
        )

    def finished(self) -> "GitHubCursor":
        return GitHubCursor(stage="done", watermark=self.started_at, summary_etag=self.summary_etag)


def _load_cursor(raw: dict[str, object]) -> GitHubCursor:
    try:
        return GitHubCursor.model_validate(raw)
    except ValidationError:
        return GitHubCursor()


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _obj(value: object) -> dict[str, object]:
    return json_object(value) or {}


def _arr(value: object) -> list[object]:
    return json_array(value) or []


def _login(node: dict[str, object]) -> str | None:
    return _str(_obj(node.get("author")).get("login"))


def _header_int(headers: httpx.Headers, name: str) -> int | None:
    raw = headers.get(name)
    return int(raw) if raw is not None and raw.isdigit() else None


class _RateTracker:
    def __init__(self, api: str) -> None:
        self.api = api
        self.remaining: int | None = None
        self.limit: int | None = None
        self.reset_at: datetime | None = None

    def update_headers(self, headers: httpx.Headers) -> None:
        remaining = _header_int(headers, "x-ratelimit-remaining")
        limit = _header_int(headers, "x-ratelimit-limit")
        reset = _header_int(headers, "x-ratelimit-reset")
        if remaining is not None:
            self.remaining = remaining
        if limit is not None:
            self.limit = limit
        if reset is not None:
            self.reset_at = datetime.fromtimestamp(reset, tz=UTC)

    def update_body(self, rate_limit: dict[str, object]) -> None:
        if "remaining" in rate_limit:
            self.remaining = _int(rate_limit["remaining"])
        if "limit" in rate_limit:
            self.limit = _int(rate_limit["limit"])
        reset = parse_datetime(rate_limit.get("resetAt"))
        if reset is not None:
            self.reset_at = reset

    def info(self) -> RateLimitInfo:
        return RateLimitInfo(
            api=self.api, remaining=self.remaining, limit=self.limit, reset_at=self.reset_at
        )


@dataclass(frozen=True)
class _Options:
    json_body: dict[str, object] | None = None
    params: dict[str, str | int] | None = None
    accept: str = JSON_ACCEPT
    etag: str | None = None
    allow_not_found: bool = False


def _split_ref(ref: str) -> tuple[str, str]:
    if not REF_RE.fullmatch(ref):
        msg = "invalid repository reference"
        raise EvidenceSourceError(msg)
    owner, _, name = ref.partition("/")
    return owner, name


class GitHubSource:
    """Own-work evidence from GitHub: REST for identity/repos/summaries, GraphQL for the rest.

    One instance per sync run: it owns the request budget and the rate trackers. Only commit
    messages, PR/issue/review text, README text, language stats and PR file *paths* are read —
    never file contents or patches.
    """

    name = "github"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport
        self._used = 0
        self._reported = 0
        self._rest_rate = _RateTracker("rest")
        self._graphql_rate = _RateTracker("graphql")
        self._identity: SourceIdentity | None = None

    def is_configured(self) -> bool:
        return self._settings.github_token is not None

    @property
    def requests_used(self) -> int:
        return self._used

    def _floor(self) -> datetime:
        years = self._settings.evidence_lookback_years
        return datetime.now(UTC) - timedelta(days=DAYS_PER_YEAR * years)

    def _headers(self, accept: str, etag: str | None) -> dict[str, str]:
        token = self._settings.github_token
        if token is None:
            msg = "GITHUB_TOKEN is not configured"
            raise EvidenceSourceConfigError(msg)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-job-assistant",
        }
        if etag is not None:
            headers["If-None-Match"] = etag
        return headers

    def _guard(self, tracker: _RateTracker) -> None:
        settings = self._settings
        if self._used >= settings.github_max_requests_per_run:
            reason = "the request budget for this run is used up"
            raise EvidenceSourcePausedError(
                reason, tracker.reset_at or datetime.now(UTC) + FALLBACK_RESUME
            )
        if (
            tracker.remaining is not None
            and tracker.limit
            and tracker.remaining * 100 < settings.github_min_remaining_pct * tracker.limit
        ):
            reason = "GitHub rate limit is nearly exhausted"
            raise EvidenceSourcePausedError(
                reason, tracker.reset_at or datetime.now(UTC) + FALLBACK_RESUME
            )

    def _classify(
        self, response: httpx.Response, tracker: _RateTracker, *, allow_not_found: bool
    ) -> httpx.Response:
        status = response.status_code
        if status == HTTP_UNAUTHORIZED:
            msg = "GitHub rejected the token (401)"
            raise EvidenceSourceConfigError(msg)
        if _is_rate_limited(response):
            wait = retry_after_header(response.headers.get("retry-after"))
            if wait is None and tracker.reset_at is not None:
                wait = max(0.0, (tracker.reset_at - datetime.now(UTC)).total_seconds())
            if wait is None or wait > MAX_INLINE_WAIT_S:
                reason = "rate limited by GitHub"
                resume = datetime.now(UTC) + timedelta(seconds=wait if wait is not None else 3600)
                raise EvidenceSourcePausedError(reason, resume)
            msg = "github rate limited"
            raise TransientError(msg, retry_after_s=wait)
        if status in RETRYABLE_STATUS:
            msg = f"github status {status}"
            raise TransientError(msg)
        if status == HTTP_NOT_FOUND and allow_not_found:
            return response
        if status >= HTTP_CLIENT_ERROR and status != HTTP_NOT_MODIFIED:
            msg = f"GitHub returned {status} (repository missing or not accessible to the token)"
            raise EvidenceSourceError(msg)
        return response

    async def _send(
        self, method: str, url: str, tracker: _RateTracker, options: _Options
    ) -> httpx.Response:
        self._guard(tracker)
        headers = self._headers(options.accept, options.etag)

        async def _call() -> httpx.Response:
            try:
                async with httpx.AsyncClient(
                    base_url=self._settings.github_api_url,
                    timeout=REQUEST_TIMEOUT_S,
                    transport=self._transport,
                ) as client:
                    response = await client.request(
                        method,
                        url,
                        json=options.json_body,
                        params=options.params,
                        headers=headers,
                    )
            except httpx.TransportError as exc:
                msg = "github transport error"
                raise TransientError(msg) from exc
            tracker.update_headers(response.headers)
            if response.status_code != HTTP_NOT_MODIFIED:
                self._used += 1
            return self._classify(response, tracker, allow_not_found=options.allow_not_found)

        try:
            return await with_retry("github.request", _call, is_retryable=_never_retryable)
        except TransientError as exc:
            msg = "GitHub is temporarily unavailable"
            raise EvidenceSourceError(msg) from exc

    async def _rest(
        self,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        accept: str = JSON_ACCEPT,
        etag: str | None = None,
        allow_not_found: bool = False,
    ) -> httpx.Response:
        options = _Options(params=params, accept=accept, etag=etag, allow_not_found=allow_not_found)
        return await self._send("GET", path, self._rest_rate, options)

    async def _graphql(self, query: str, variables: dict[str, object]) -> dict[str, object]:
        options = _Options(json_body={"query": query, "variables": variables})
        response = await self._send("POST", "/graphql", self._graphql_rate, options)
        body = _json_object(response)
        rate = _obj(_obj(body.get("data")).get("rateLimit"))
        if rate:
            self._graphql_rate.update_body(rate)
        errors = [_obj(error) for error in _arr(body.get("errors"))]
        if any(_str(error.get("type")) == "RATE_LIMITED" for error in errors):
            reason = "GraphQL rate limit reached"
            raise EvidenceSourcePausedError(
                reason, self._graphql_rate.reset_at or datetime.now(UTC) + FALLBACK_RESUME
            )
        if errors:
            msg = "GitHub GraphQL query failed (repository missing or not accessible)"
            raise EvidenceSourceError(msg)
        return _obj(body.get("data"))

    async def identify(self) -> SourceIdentity:
        if self._identity is None:
            response = await self._rest("/user")
            body = _json_object(response)
            login = _str(body.get("login"))
            if login is None:
                msg = "GitHub returned no login for this token"
                raise EvidenceSourceError(msg)
            email = _str(body.get("email"))
            scopes = response.headers.get("x-oauth-scopes", "")
            self._identity = SourceIdentity(
                login=login,
                node_id=_str(body.get("node_id")),
                emails=[email] if email else [],
                permissions=[scope.strip() for scope in scopes.split(",") if scope.strip()],
            )
        return self._identity

    async def list_scopes(self) -> list[ScopeCandidate]:
        floor = self._floor()
        candidates: list[ScopeCandidate] = []
        for page in range(1, MAX_REPO_PAGES + 1):
            response = await self._rest(
                "/user/repos",
                params={
                    "per_page": REPOS_PER_PAGE,
                    "page": page,
                    "sort": "pushed",
                    "direction": "desc",
                    "affiliation": "owner,collaborator,organization_member",
                },
            )
            rows = _arr(_json_value(response))
            reached_floor = False
            for row in rows:
                repo = _obj(row)
                pushed = parse_datetime(repo.get("pushed_at"))
                full_name = _str(repo.get("full_name"))
                if pushed is not None and pushed < floor:
                    reached_floor = True
                    break
                if full_name is not None and REF_RE.fullmatch(full_name):
                    candidates.append(
                        ScopeCandidate(
                            ref=full_name,
                            is_private=repo.get("private") is True,
                            is_fork=repo.get("fork") is True,
                            description=_str(repo.get("description")),
                            pushed_at=pushed,
                        )
                    )
            if reached_floor or len(rows) < REPOS_PER_PAGE:
                break
        return candidates

    def _page(self, items: list[EvidenceItemData], cursor: GitHubCursor) -> SyncPage:
        used = self._used - self._reported
        self._reported = self._used
        limits = [
            tracker.info()
            for tracker in (self._rest_rate, self._graphql_rate)
            if tracker.remaining is not None
        ]
        return SyncPage(
            items=items,
            next_cursor=cursor.model_dump(mode="json"),
            requests_used=used,
            rate_limits=limits,
        )

    async def sync_scope(self, scope: ScopeState) -> AsyncIterator[SyncPage]:
        _split_ref(scope.ref)
        identity = await self.identify()
        cursor = _load_cursor(scope.cursor)
        if cursor.stage in (None, "done"):
            cursor = cursor.begin_pass(datetime.now(UTC), self._floor())
        runners: dict[str, StageRunner] = {
            "summary": self._summary,
            "commits": self._commits,
            "prs": self._pull_requests,
            "reviews": self._reviews,
            "issues": self._issues,
        }
        current = cursor.stage if cursor.stage in _STAGES else "summary"
        for stage in _STAGES[_STAGES.index(current) :]:
            async for items, advanced in runners[stage](scope, cursor, identity):
                cursor = advanced
                yield self._page(items, cursor)
        yield self._page([], cursor.finished())

    async def _summary(
        self, scope: ScopeState, cursor: GitHubCursor, _: SourceIdentity
    ) -> AsyncIterator[tuple[list[EvidenceItemData], GitHubCursor]]:
        advanced = cursor.model_copy(update={"stage": "commits"})
        repo_response = await self._rest(f"/repos/{scope.ref}", etag=cursor.summary_etag)
        if repo_response.status_code == HTTP_NOT_MODIFIED:
            yield [], advanced
            return
        languages = _obj(_json_value(await self._rest(f"/repos/{scope.ref}/languages")))
        readme = await self._rest(
            f"/repos/{scope.ref}/readme", accept=RAW_ACCEPT, allow_not_found=True
        )
        readme_text = readme.text if readme.status_code != HTTP_NOT_FOUND else ""
        node: dict[str, object] = {
            **_json_object(repo_response),
            "languages": languages,
            "readme": readme_text[:README_MAX_CHARS],
            "readme_truncated": len(readme_text) > README_MAX_CHARS,
        }
        item = self.normalize({"kind": "repo_summary", "repo": scope.ref, "node": node})
        etag = repo_response.headers.get("etag")
        yield [item], advanced.model_copy(update={"summary_etag": etag})

    async def _commits(
        self, scope: ScopeState, cursor: GitHubCursor, identity: SourceIdentity
    ) -> AsyncIterator[tuple[list[EvidenceItemData], GitHubCursor]]:
        if identity.node_id is None:
            msg = "GitHub returned no node id for this token"
            raise EvidenceSourceError(msg)
        owner, name = _split_ref(scope.ref)
        after = cursor.commits_after
        while True:
            data = await self._graphql(
                COMMITS_QUERY,
                {
                    "owner": owner,
                    "name": name,
                    "author": identity.node_id,
                    "since": cursor.since,
                    "after": after,
                },
            )
            history = _obj(
                _obj(_obj(_obj(data.get("repository")).get("defaultBranchRef")).get("target")).get(
                    "history"
                )
            )
            items = [
                self.normalize({"kind": "commit", "repo": scope.ref, "node": _obj(node)})
                for node in _arr(history.get("nodes"))
            ]
            end = _next_page(history)
            if end is None:
                yield items, cursor.model_copy(update={"stage": "prs", "commits_after": None})
                return
            after = end
            yield items, cursor.model_copy(update={"commits_after": end})

    def _search_query(self, scope: ScopeState, cursor: GitHubCursor, terms: str) -> str:
        since = (parse_datetime(cursor.since) or self._floor()).date().isoformat()
        return f"repo:{scope.ref} {terms} updated:>={since}"

    async def _search_stage(
        self, scope: ScopeState, cursor: GitHubCursor, spec: _SearchSpec
    ) -> AsyncIterator[tuple[list[EvidenceItemData], GitHubCursor]]:
        after: str | None = getattr(cursor, spec.cursor_field)
        while True:
            data = await self._graphql(
                spec.query,
                {
                    "q": self._search_query(scope, cursor, spec.terms),
                    "after": after,
                    **spec.variables,
                },
            )
            search = _obj(data.get("search"))
            items: list[EvidenceItemData] = []
            for node in _arr(search.get("nodes")):
                item = self._maybe_normalize(spec.kind, scope.ref, _obj(node))
                if item is not None:
                    items.append(item)
            end = _next_page(search)
            if end is None:
                done = {"stage": spec.next_stage, spec.cursor_field: None}
                yield items, cursor.model_copy(update=done)
                return
            after = end
            yield items, cursor.model_copy(update={spec.cursor_field: end})

    def _maybe_normalize(
        self, kind: EvidenceKind, repo: str, node: dict[str, object]
    ) -> EvidenceItemData | None:
        if not node or not _int(node.get("number")):
            return None
        try:
            return self.normalize({"kind": kind.value, "repo": repo, "node": node})
        except EvidenceSourceError:
            return None

    def _pull_requests(
        self, scope: ScopeState, cursor: GitHubCursor, identity: SourceIdentity
    ) -> AsyncIterator[tuple[list[EvidenceItemData], GitHubCursor]]:
        spec = _SearchSpec(
            query=PULL_REQUESTS_QUERY,
            terms=f"author:{identity.login} is:pr",
            kind=EvidenceKind.pull_request,
            cursor_field="prs_after",
            next_stage="reviews",
        )
        return self._search_stage(scope, cursor, spec)

    def _reviews(
        self, scope: ScopeState, cursor: GitHubCursor, identity: SourceIdentity
    ) -> AsyncIterator[tuple[list[EvidenceItemData], GitHubCursor]]:
        spec = _SearchSpec(
            query=REVIEWS_QUERY,
            terms=f"reviewed-by:{identity.login} -author:{identity.login} is:pr",
            kind=EvidenceKind.review_comment,
            cursor_field="reviews_after",
            next_stage="issues",
            variables={"login": identity.login},
        )
        return self._search_stage(scope, cursor, spec)

    def _issues(
        self, scope: ScopeState, cursor: GitHubCursor, identity: SourceIdentity
    ) -> AsyncIterator[tuple[list[EvidenceItemData], GitHubCursor]]:
        spec = _SearchSpec(
            query=ISSUES_QUERY,
            terms=f"author:{identity.login} is:issue",
            kind=EvidenceKind.issue,
            cursor_field="issues_after",
            next_stage="done",
        )
        return self._search_stage(scope, cursor, spec)

    def normalize(self, raw: RawEvidence) -> EvidenceItemData:
        kind = _str(raw.get("kind"))
        repo = _str(raw.get("repo"))
        mapper = _MAPPERS.get(kind or "")
        if mapper is None or repo is None:
            msg = f"cannot normalize evidence of kind {kind!r}"
            raise EvidenceSourceError(msg)
        return mapper(repo, _obj(raw.get("node")))


StageRunner = Callable[
    [ScopeState, GitHubCursor, SourceIdentity],
    AsyncIterator[tuple[list[EvidenceItemData], GitHubCursor]],
]


def _never_retryable(_: Exception) -> bool:
    return False


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.status_code == HTTP_TOO_MANY_REQUESTS:
        return True
    if response.status_code != HTTP_FORBIDDEN:
        return False
    if "retry-after" in response.headers or response.headers.get("x-ratelimit-remaining") == "0":
        return True
    return "rate limit" in response.text[:500].lower()


def _json_value(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError as exc:
        msg = "GitHub returned a response that is not JSON"
        raise EvidenceSourceError(msg) from exc


def _json_object(response: httpx.Response) -> dict[str, object]:
    return _obj(_json_value(response))


def _next_page(connection: dict[str, object]) -> str | None:
    info = _obj(connection.get("pageInfo"))
    end = _str(info.get("endCursor"))
    return end if info.get("hasNextPage") is True else None


def _joined(*parts: str | None) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _map_repo_summary(repo: str, node: dict[str, object]) -> EvidenceItemData:
    languages = {key: _int(value) for key, value in _obj(node.get("languages")).items()}
    total = sum(languages.values()) or 1
    shares = ", ".join(
        f"{name} {round(100 * size / total)}%"
        for name, size in sorted(languages.items(), key=lambda pair: -pair[1])[:6]
    )
    topics = [topic for topic in _arr(node.get("topics")) if isinstance(topic, str)]
    body = _joined(
        _str(node.get("description")),
        f"Languages: {shares}" if shares else None,
        f"Topics: {', '.join(topics)}" if topics else None,
        _str(node.get("readme")),
    )
    return EvidenceItemData(
        kind=EvidenceKind.repo_summary,
        external_id=repo,
        project_key=repo,
        title=repo,
        body=body or repo,
        url=_str(node.get("html_url")),
        occurred_at=parse_datetime(node.get("pushed_at")),
        meta={
            "stars": _int(node.get("stargazers_count")),
            "forks": _int(node.get("forks_count")),
            "languages": languages,
            "topics": topics,
            "is_fork": node.get("fork") is True,
            "readme_truncated": node.get("readme_truncated") is True,
        },
    )


def _map_commit(repo: str, node: dict[str, object]) -> EvidenceItemData:
    oid = _str(node.get("oid"))
    if oid is None:
        msg = "commit without an oid"
        raise EvidenceSourceError(msg)
    headline = _str(node.get("messageHeadline"))
    return EvidenceItemData(
        kind=EvidenceKind.commit,
        external_id=oid,
        project_key=repo,
        title=headline,
        body=_joined(headline, _str(node.get("messageBody"))) or oid,
        url=_str(node.get("url")),
        occurred_at=parse_datetime(node.get("committedDate")),
        meta={
            "additions": _int(node.get("additions")),
            "deletions": _int(node.get("deletions")),
            "changed_files": _int(node.get("changedFilesIfAvailable")),
            "parents": _int(_obj(node.get("parents")).get("totalCount")),
        },
    )


def _map_pull_request(repo: str, node: dict[str, object]) -> EvidenceItemData:
    number = _int(node.get("number"))
    title = _str(node.get("title"))
    paths = [
        path
        for file in _arr(_obj(node.get("files")).get("nodes"))
        if (path := _str(_obj(file).get("path"))) is not None
    ]
    changed = _int(node.get("changedFiles"))
    meta: dict[str, object] = {
        "number": number,
        "state": _str(node.get("state")),
        "merged": node.get("mergedAt") is not None,
        "additions": _int(node.get("additions")),
        "deletions": _int(node.get("deletions")),
        "changed_files": changed,
        "merge_commit_oid": _str(_obj(node.get("mergeCommit")).get("oid")),
        "author_login": _login(node),
    }
    if changed <= len(paths):
        meta["paths"] = paths
    else:
        meta["paths_truncated"] = True
    return EvidenceItemData(
        kind=EvidenceKind.pull_request,
        external_id=f"{repo}#{number}",
        project_key=repo,
        title=title,
        body=_joined(title, _str(node.get("body"))) or f"{repo}#{number}",
        url=_str(node.get("url")),
        occurred_at=parse_datetime(node.get("mergedAt")) or parse_datetime(node.get("createdAt")),
        meta=meta,
    )


def _map_issue(repo: str, node: dict[str, object]) -> EvidenceItemData:
    number = _int(node.get("number"))
    title = _str(node.get("title"))
    labels = [
        name
        for label in _arr(_obj(node.get("labels")).get("nodes"))
        if (name := _str(_obj(label).get("name"))) is not None
    ]
    return EvidenceItemData(
        kind=EvidenceKind.issue,
        external_id=f"{repo}#{number}",
        project_key=repo,
        title=title,
        body=_joined(title, _str(node.get("body"))) or f"{repo}#{number}",
        url=_str(node.get("url")),
        occurred_at=parse_datetime(node.get("createdAt")),
        meta={"number": number, "state": _str(node.get("state")), "labels": labels},
    )


def _map_review(repo: str, node: dict[str, object]) -> EvidenceItemData:
    number = _int(node.get("number"))
    title = _str(node.get("title"))
    reviews = [_obj(review) for review in _arr(_obj(node.get("reviews")).get("nodes"))]
    parts: list[str] = []
    comments = 0
    for review in reviews:
        parts.append(_str(review.get("body")) or "")
        for comment in _arr(_obj(review.get("comments")).get("nodes")):
            comment_node = _obj(comment)
            text = _str(comment_node.get("body"))
            if text:
                comments += 1
                path = _str(comment_node.get("path"))
                parts.append(f"{path}: {text}" if path else text)
    body = _joined(*parts)
    if not body:
        msg = "review without text"
        raise EvidenceSourceError(msg)
    first = reviews[0] if reviews else {}
    return EvidenceItemData(
        kind=EvidenceKind.review_comment,
        external_id=f"{repo}#{number}:review",
        project_key=repo,
        title=f"Review of {repo}#{number}: {title}" if title else f"Review of {repo}#{number}",
        body=body,
        url=_str(first.get("url")) or _str(node.get("url")),
        occurred_at=parse_datetime(first.get("submittedAt")),
        meta={"pr_number": number, "reviews": len(reviews), "comments": comments},
    )


_MAPPERS: dict[str, Callable[[str, dict[str, object]], EvidenceItemData]] = {
    EvidenceKind.repo_summary.value: _map_repo_summary,
    EvidenceKind.commit.value: _map_commit,
    EvidenceKind.pull_request.value: _map_pull_request,
    EvidenceKind.issue.value: _map_issue,
    EvidenceKind.review_comment.value: _map_review,
}
