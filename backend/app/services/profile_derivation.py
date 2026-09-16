import logging
import re
from datetime import date

from app.core.config import get_settings
from app.schemas.profile import ExperienceItem, Preferences, SeniorityLevel, StructuredProfile

logger = logging.getLogger(__name__)

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_PRESENT = re.compile(r"^(present|current|now|today|ongoing|current role|to date)$", re.I)
_MONTH_NAME = re.compile(r"^(?P<month>[A-Za-z]{3,9})\.?\s*,?\s*(?P<year>\d{4})$")
_YEAR_ONLY = re.compile(r"^\d{4}$")
_ISO_MONTH = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{1,2})$")
_SLASH_MONTH = re.compile(r"^(?P<month>\d{1,2})[/](?P<year>\d{4})$")
_ISO_FULL = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})$")

# Date strings stamped in the future are treated as unparseable (future-proof
# formats / typos); a one-month grace window absorbs clock skew.
_MAX_FUTURE_GRACE_DAYS = 31


def resolve_date(value: str | None) -> date | None:
    """Parse one verbatim resume date string into a date; None when unparseable."""
    text = (value or "").strip().rstrip(".")
    if not text:
        return None
    if _PRESENT.match(text):
        return date.today()
    parsed = _parse_absolute(text)
    if parsed is None:
        return None
    today = date.today()
    if parsed > today and (parsed - today).days > _MAX_FUTURE_GRACE_DAYS:
        return None
    return parsed


def _parse_absolute(text: str) -> date | None:
    text = text.strip()
    month_match = _MONTH_NAME.match(text)
    if month_match:
        month = _MONTHS.get(month_match.group("month")[:3].lower())
        if month:
            return date(int(month_match.group("year")), month, 1)
        return None
    if _YEAR_ONLY.match(text):
        return date(int(text), 1, 1)
    iso_month = _ISO_MONTH.match(text)
    if iso_month:
        return date(int(iso_month.group("year")), int(iso_month.group("month")), 1)
    slash = _SLASH_MONTH.match(text)
    if slash:
        return date(int(slash.group("year")), int(slash.group("month")), 1)
    iso_full = _ISO_FULL.match(text)
    if iso_full:
        return date(
            int(iso_full.group("year")), int(iso_full.group("month")), int(iso_full.group("day"))
        )
    return None


def parse_years_of_experience(experience: list[ExperienceItem]) -> int | None:
    """Career span in whole years: earliest parseable start to latest end.

    Overlapping roles are absorbed by the span (no per-role summation);
    unparseable items are skipped. Returns None when no dates parse at all.
    """
    today = date.today()
    starts: list[date] = []
    ends: list[date] = []
    for item in experience:
        start = resolve_date(item.start_date)
        if start is None:
            continue
        end = resolve_date(item.end_date)
        if item.is_current or end is None:
            end = today
        starts.append(start)
        ends.append(end)
    if not starts:
        return None
    span_days = (max(ends) - min(starts)).days
    if span_days <= 0:
        return None
    return int(span_days // 365.25)


def derive_seniority(years: int) -> SeniorityLevel:
    settings = get_settings()
    if years < settings.seniority_band_mid:
        return "junior"
    if years < settings.seniority_band_senior:
        return "mid"
    if years < settings.seniority_band_staff:
        return "senior"
    if years < settings.seniority_band_principal:
        return "staff"
    return "principal"


def apply_derived_fields(profile: StructuredProfile) -> bool:
    """Set years_of_experience and, as a fallback, seniority from it.

    Seniority is only filled when the user hasn't set it (None, or an earlier
    derived value that must track YOE changes); user-set and legacy values
    (seniority set, source None) are never overwritten. When the derived label
    loses its YOE basis (dates unparseable), a derived seniority is cleared.
    Returns whether anything changed.
    """
    years = parse_years_of_experience(profile.experience)
    changed = profile.years_of_experience != years
    profile.years_of_experience = years
    if years is None:
        if _clear_stale_derived(profile):
            changed = True
        return changed
    derived = derive_seniority(years)
    prefs = profile.preferences
    if prefs is None or prefs.seniority is None:
        if prefs is None:
            prefs = Preferences()
            profile.preferences = prefs
        if prefs.seniority != derived or prefs.seniority_source != "derived":
            prefs.seniority = derived
            prefs.seniority_source = "derived"
            changed = True
    elif prefs.seniority_source == "derived" and prefs.seniority != derived:
        prefs.seniority = derived
        changed = True
    return changed


def _clear_stale_derived(profile: StructuredProfile) -> bool:
    prefs = profile.preferences
    if prefs is not None and prefs.seniority_source == "derived":
        prefs.seniority = None
        prefs.seniority_source = None
        return True
    return False
