import re
import unicodedata


def stable_player_id(name: str) -> str:
    """Create a conservative fallback ID when a source exposes no player ID.

    This is not identity resolution. A future collector-provided ATP ID should take
    precedence, and ambiguous aliases must be reviewed rather than fuzzy-matched.
    """
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    identifier = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    if not identifier:
        raise ValueError(f"cannot derive player ID from {name!r}")
    return identifier

