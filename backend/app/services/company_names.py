import re
import unicodedata
from collections.abc import Iterable

from app.adapters.job_sources.base import json_array, json_object

LEGAL_SUFFIXES = frozenset(
    {
        "inc",
        "incorporated",
        "llc",
        "ltd",
        "limited",
        "pvt",
        "private",
        "corp",
        "corporation",
        "co",
        "company",
        "gmbh",
        "ag",
        "sa",
        "plc",
        "pte",
        "bv",
        "oy",
        "ab",
    }
)
_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_company(name: str | None) -> str:
    """Comparison key for a company name: case, accents, punctuation and legal suffixes dropped.

    "Reliance Jio Infocom Ltd." and "reliance jio infocom" are one company; "Samsung" and
    "Samsung Research Institute" are not (that is a judgment the user confirms as a merge).
    """
    if not name:
        return ""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold()
    tokens = [token for token in _NON_WORD.split(folded) if token]
    if not tokens:
        return name.casefold().strip()
    while len(tokens) > 1 and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


class Merges:
    """The user's confirmed company merges: differently named companies that are one employer."""

    def __init__(self, groups: Iterable[tuple[str, Iterable[str]]] = ()) -> None:
        self._canonical: dict[str, str] = {}
        self._members: dict[str, tuple[str, ...]] = {}
        self._lookup: dict[str, str] = {}
        for canonical, members in groups:
            key = normalize_company(canonical)
            names = tuple(dict.fromkeys([canonical, *members]))
            self._canonical[key] = canonical
            self._members[key] = names
            for name in names:
                self._lookup[normalize_company(name)] = key

    @classmethod
    def from_stored(cls, raw: object) -> "Merges":
        """Tolerant of a missing or malformed column: anything unusable is simply no merge."""
        parsed: list[tuple[str, list[str]]] = []
        for group in json_array((json_object(raw) or {}).get("groups")) or []:
            fields = json_object(group) or {}
            canonical = fields.get("canonical")
            if isinstance(canonical, str):
                members = json_array(fields.get("members")) or []
                parsed.append((canonical, [m for m in members if isinstance(m, str)]))
        return cls(parsed)

    def to_stored(self) -> dict[str, object]:
        return {
            "groups": [
                {"canonical": self._canonical[key], "members": list(self._members[key])}
                for key in self._canonical
            ]
        }

    def key(self, name: str | None) -> str:
        normalized = normalize_company(name)
        return self._lookup.get(normalized, normalized)

    def canonical(self, key: str) -> str | None:
        return self._canonical.get(key)

    def members(self, key: str) -> tuple[str, ...]:
        return self._members.get(key, ())

    def keys(self) -> list[str]:
        return list(self._canonical)
