from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import EmployerMergeNotFoundError, InvalidEmployerMergeError
from app.schemas.evidence import EmployerMergeRequest, EmployerOption
from app.services.company_names import Merges
from app.services.employer_mapping import group_for_company, load_profile_facts
from app.services.evidence_sync import employer_options
from app.services.resume_service import get_or_create_candidate

MIN_MERGED_EMPLOYERS = 2


async def merge_employers(
    session: AsyncSession, payload: EmployerMergeRequest
) -> list[EmployerOption]:
    """Record that several company names are one employer; stored refs are never rewritten."""
    candidate = await get_or_create_candidate(session)
    facts = await load_profile_facts(session, candidate.id)
    names = list(dict.fromkeys([payload.canonical, *payload.members]))
    groups = facts.groups
    found = [group_for_company(groups, name) for name in names]
    if (
        any(group is None for group in found)
        or len({g.key for g in found if g}) < MIN_MERGED_EMPLOYERS
    ):
        raise InvalidEmployerMergeError
    stored = facts.merges
    touched = {stored.key(name) for name in names} & set(stored.group_keys())
    members = list(names)
    for key in touched:
        members.extend(stored.members(key))
    kept = [
        (canonical, stored.members(key))
        for key in stored.group_keys()
        if key not in touched and (canonical := stored.canonical(key)) is not None
    ]
    candidate.employer_merges = Merges([*kept, (payload.canonical, members)]).to_stored()
    await session.flush()
    return await employer_options(session)


async def unmerge_employer(session: AsyncSession, key: str) -> list[EmployerOption]:
    candidate = await get_or_create_candidate(session)
    stored = (await load_profile_facts(session, candidate.id)).merges
    if key not in stored.group_keys():
        raise EmployerMergeNotFoundError
    candidate.employer_merges = Merges(
        [
            (canonical, stored.members(other))
            for other in stored.group_keys()
            if other != key and (canonical := stored.canonical(other)) is not None
        ]
    ).to_stored()
    await session.flush()
    return await employer_options(session)
