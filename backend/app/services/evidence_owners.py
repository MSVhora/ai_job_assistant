from app.adapters.job_sources.base import json_object
from app.models import EvidenceSourceAccount

ORG_SOURCE = "org"
USER_SOURCE = "user"


def owner_of(ref: str) -> str:
    return ref.partition("/")[0].casefold()


def owner_mapping(account: EvidenceSourceAccount) -> dict[str, dict[str, object]]:
    stored = json_object(account.owner_employers) or {}
    owners = json_object(stored.get("owners")) or {}
    mapping: dict[str, dict[str, object]] = {}
    for owner, ref in owners.items():
        employer = json_object(ref)
        if employer:
            mapping[owner] = employer
    return mapping


def owner_default(account: EvidenceSourceAccount, ref: str) -> dict[str, object] | None:
    """The employer a repository inherits from its organization, marked as not chosen on its own."""
    mapped = owner_mapping(account).get(owner_of(ref))
    return {**mapped, "source": ORG_SOURCE} if mapped else None


def is_explicit(employer_ref: dict[str, object] | None) -> bool:
    return employer_ref is not None and employer_ref.get("source") != ORG_SOURCE
