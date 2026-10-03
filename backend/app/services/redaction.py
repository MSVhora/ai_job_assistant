import ipaddress
import re
from dataclasses import dataclass, field

_URL_CREDENTIALS = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@", re.IGNORECASE)
_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL
)
_TOKEN_SHAPES = re.compile(
    r"\b(?:"
    r"github_pat_[A-Za-z0-9_]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|sk-[A-Za-z0-9_-]{20,}"
    r"|AIza[0-9A-Za-z_-]{30,}"
    r"|xox[abp]-[A-Za-z0-9-]{10,}"
    r"|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
    r")\b"
)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<![\w.-])\+?\d[\d\s().-]{7,}\d(?![\w.-])")
_IPV4 = re.compile(
    r"(?<![\w.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\w.])"
)
_IPV6 = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}(?![\w:])")
_SECRET_ASSIGNMENT = re.compile(
    r"(?P<key>\b(?:secret|token|password|passwd|api[_-]?key|auth|credential)s?\w*\s*[=:]\s*)"
    r"(?P<value>[A-Za-z0-9+/_=-]{16,})",
    re.IGNORECASE,
)
_VERSION_PREFIX = re.compile(r"(?:version|ver\.?|v)\s*$", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"<[A-Z_]+_\d+>")
_IPV4_VERSION = 4
_MIN_PHONE_DIGITS = 9
_MAX_PHONE_DIGITS = 15
_DIGITS = re.compile(r"\d")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class RedactionResult:
    text: str
    placeholders: dict[str, str] = field(default_factory=dict[str, str])
    counts: dict[str, int] = field(default_factory=dict[str, int])


class _Redactor:
    def __init__(self) -> None:
        self.placeholders: dict[str, str] = {}
        self.counts: dict[str, int] = {}
        self._by_value: dict[tuple[str, str], str] = {}

    def token(self, label: str, value: str) -> str:
        existing = self._by_value.get((label, value))
        if existing is not None:
            return existing
        self.counts[label] = self.counts.get(label, 0) + 1
        placeholder = f"<{label}_{self.counts[label]}>"
        self.placeholders[placeholder] = value
        self._by_value[(label, value)] = placeholder
        return placeholder

    def sub(self, pattern: re.Pattern[str], label: str, text: str) -> str:
        return pattern.sub(lambda match: self.token(label, match.group(0)), text)


def _phone_sub(redactor: _Redactor, text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        digits = len(_DIGITS.findall(match.group(0)))
        if _DATE.search(match.group(0)):
            return match.group(0)
        if _MIN_PHONE_DIGITS <= digits <= _MAX_PHONE_DIGITS:
            return redactor.token("PHONE", match.group(0))
        return match.group(0)

    return _PHONE.sub(replace, text)


def _ip_sub(redactor: _Redactor, text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group(0)
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            return value
        if address.version == _IPV4_VERSION and _VERSION_PREFIX.search(text[: match.start()]):
            return value
        return redactor.token("IP", value)

    return _IPV6.sub(replace, _IPV4.sub(replace, text))


def redact(text: str) -> RedactionResult:
    """Replace secrets and PII with `<LABEL_n>` placeholders (deterministic, idempotent).

    Rules run in a fixed order. Hex commit SHAs, UUIDs and bare version strings are not
    matched. `restore` reverses it for a caller that needs the originals back.
    """
    redactor = _Redactor()
    out = _URL_CREDENTIALS.sub(
        lambda m: (
            m.group("scheme")
            + redactor.token("URL_CREDENTIALS", m.group(0)[len(m.group("scheme")) : -1])
            + "@"
        ),
        text,
    )
    out = redactor.sub(_PRIVATE_KEY, "PRIVATE_KEY", out)
    out = redactor.sub(_TOKEN_SHAPES, "TOKEN", out)
    out = redactor.sub(_EMAIL, "EMAIL", out)
    out = _SECRET_ASSIGNMENT.sub(
        lambda m: m.group("key") + redactor.token("SECRET", m.group("value")), out
    )
    out = _ip_sub(redactor, out)
    out = _phone_sub(redactor, out)
    return RedactionResult(text=out, placeholders=redactor.placeholders, counts=redactor.counts)


def restore(text: str, placeholders: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda match: placeholders.get(match.group(0), match.group(0)), text)
