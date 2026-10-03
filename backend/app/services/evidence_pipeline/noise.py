import re
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.adapters.job_sources.base import json_array
from app.schemas.evidence import EvidenceItemData, NoiseVerdict

_MERGE_RE = re.compile(r"^Merge (branch|pull request|remote)\b", re.IGNORECASE)
_BUMP_RE = re.compile(r"^(chore\(deps[^)]*\)|(?:bump|update dependency|upgrade)\b)", re.IGNORECASE)
_TRIVIA_RE = re.compile(
    r"^(wip|fix typo|typo|format|lint|cleanup|update readme|initial commit|misc|minor|\.+)(\W|$)",
    re.IGNORECASE,
)
_MIN_FILE_RE = re.compile(r"\.min\.[^/]+$|\.snap$")

LOCKFILES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "uv.lock",
        "Cargo.lock",
        "go.sum",
        "Podfile.lock",
        "Gemfile.lock",
        "composer.lock",
    }
)
GENERATED_DIRS = frozenset({"dist", "build", "vendor"})

BUMP_MAX_CHANGED_LINES = 5
TRIVIA_MAX_WORDS = 2
TRIVIA_MAX_CHANGED_LINES = 3
TRIVIA_REGEX_MAX_WORDS = 5


@dataclass(frozen=True)
class _Facts:
    message: str
    author_login: str | None
    parents: int | None
    changed_lines: int | None
    paths: tuple[str, ...]
    bot_logins: frozenset[str]


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _first_line(item: EvidenceItemData) -> str:
    text = (item.title or item.body).strip()
    return text.splitlines()[0].strip() if text else ""


def _facts(item: EvidenceItemData, bot_logins: Collection[str]) -> _Facts:
    additions = _as_int(item.meta.get("additions"))
    deletions = _as_int(item.meta.get("deletions"))
    changed = (
        None if additions is None and deletions is None else (additions or 0) + (deletions or 0)
    )
    paths = tuple(p for p in json_array(item.meta.get("paths")) or [] if isinstance(p, str))
    login = item.meta.get("author_login")
    return _Facts(
        message=_first_line(item),
        author_login=login if isinstance(login, str) else None,
        parents=_as_int(item.meta.get("parents")),
        changed_lines=changed,
        paths=paths,
        bot_logins=frozenset(name.lower() for name in bot_logins),
    )


def _is_merge(f: _Facts) -> bool:
    return (f.parents is not None and f.parents > 1) or bool(_MERGE_RE.match(f.message))


def _is_bot(f: _Facts) -> bool:
    if f.author_login is None:
        return False
    login = f.author_login.lower()
    return login.endswith("[bot]") or login in f.bot_logins


def _is_dependency_bump(f: _Facts) -> bool:
    small = f.changed_lines is not None and f.changed_lines <= BUMP_MAX_CHANGED_LINES
    return small and bool(_BUMP_RE.match(f.message))


def _is_lockfile_only(f: _Facts) -> bool:
    return bool(f.paths) and all(PurePosixPath(p).name in LOCKFILES for p in f.paths)


def _is_trivial(f: _Facts) -> bool:
    words = len(f.message.split())
    if _TRIVIA_RE.match(f.message) and words <= TRIVIA_REGEX_MAX_WORDS:
        return True
    return (
        f.changed_lines is not None
        and f.changed_lines <= TRIVIA_MAX_CHANGED_LINES
        and 0 < words <= TRIVIA_MAX_WORDS
    )


def _is_generated(f: _Facts) -> bool:
    def generated(path: str) -> bool:
        parts = PurePosixPath(path).parts
        return bool(GENERATED_DIRS.intersection(parts[:-1])) or bool(_MIN_FILE_RE.search(path))

    return bool(f.paths) and all(generated(p) for p in f.paths)


# Order is part of the contract: the first matching rule supplies the reason.
RULES: tuple[tuple[str, Callable[[_Facts], bool]], ...] = (
    ("merge_commit", _is_merge),
    ("bot_author", _is_bot),
    ("dependency_bump", _is_dependency_bump),
    ("lockfile_only", _is_lockfile_only),
    ("trivial_message", _is_trivial),
    ("generated_or_vendored", _is_generated),
)


def classify(item: EvidenceItemData, bot_logins: Collection[str]) -> NoiseVerdict:
    facts = _facts(item, bot_logins)
    for reason, rule in RULES:
        if rule(facts):
            return NoiseVerdict(kept=False, reason=reason)
    return NoiseVerdict(kept=True)
