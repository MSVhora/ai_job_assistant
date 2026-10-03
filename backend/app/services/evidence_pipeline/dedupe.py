import hashlib

CHUNKER_VERSION = "chunker_v1"
SQUASH_REASON = "squash_of_pull_request"
_UNIT_SEPARATOR = "\x1f"


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def digest(*parts: str) -> str:
    """SHA-256 over whitespace-normalized parts; identical content gives an identical id."""
    joined = _UNIT_SEPARATOR.join(normalize_text(part) for part in parts)
    return hashlib.sha256(joined.encode()).hexdigest()


def chunk_hash(chunker_version: str, text: str) -> str:
    return digest(chunker_version, text)
