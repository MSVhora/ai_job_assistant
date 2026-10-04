import logging
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import EvidenceOwnerNotFoundError, InvalidEmployerError
from app.schemas.evidence import OwnerSummary
from app.services.achievement_review import apply_scope_employer
from app.services.employer_mapping import load_profile_facts, normalize_employer_ref
from app.services.evidence_owners import is_explicit, owner_default, owner_mapping, owner_of
from app.services.evidence_sync import get_or_create_account, stored_scopes
from app.services.resume_service import get_or_create_candidate

logger = logging.getLogger(__name__)


async def list_owners(session: AsyncSession) -> list[OwnerSummary]:
    """Every GitHub owner among the stored repositories, with the employer it maps to."""
    candidate = await get_or_create_candidate(session)
    account = await get_or_create_account(session, candidate.id)
    mapping = owner_mapping(account)
    by_owner: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    for scope in (await stored_scopes(session, account.id)).values():
        by_owner[owner_of(scope.ref)].append((scope.enabled, is_explicit(scope.employer_ref)))
    login = (account.account_login or "").casefold()
    return [
        OwnerSummary(
            owner=owner,
            repos=len(rows),
            selected=sum(1 for enabled, _ in rows if enabled),
            explicit=sum(1 for _, explicit in rows if explicit),
            employer=mapping.get(owner),
            personal_account=owner == login,
        )
        for owner, rows in sorted(by_owner.items())
    ]


async def set_owner_employer(
    session: AsyncSession, owner: str, employer_ref: dict[str, object] | None
) -> list[OwnerSummary]:
    """Map an organization to an employer (or clear it). Every repository of the owner that was
    not mapped on its own follows, selected or not; repository choices stay."""
    key = owner.casefold()
    candidate = await get_or_create_candidate(session)
    account = await get_or_create_account(session, candidate.id)
    scopes = [
        scope
        for scope in (await stored_scopes(session, account.id)).values()
        if owner_of(scope.ref) == key
    ]
    if not scopes:
        raise EvidenceOwnerNotFoundError
    groups = (await load_profile_facts(session, candidate.id)).groups
    try:
        normalized = normalize_employer_ref(employer_ref, groups)
    except ValueError as exc:
        raise InvalidEmployerError from exc
    mapping = owner_mapping(account)
    if normalized is None:
        mapping.pop(key, None)
    else:
        mapping[key] = {k: v for k, v in normalized.items() if k != "source"}
    account.owner_employers = {"owners": mapping} if mapping else None
    inherited = owner_default(account, key + "/")
    for scope in scopes:
        if is_explicit(scope.employer_ref):
            continue
        scope.employer_ref = inherited
        await apply_scope_employer(session, candidate.id, scope.ref, inherited)
    await session.flush()
    logger.info("evidence.owner mapped repos=%d cleared=%s", len(scopes), normalized is None)
    return await list_owners(session)
