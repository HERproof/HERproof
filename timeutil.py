"""
HerProof — timestamp normalization.

Sources disagree on time zones: WhatsApp exports and EXIF are naive local
wall-clock times, while Gemini sometimes appends an offset or "Z" to a time
it read off a screenshot. Every time a person saw on their phone was local
wall-clock time, so we drop any offset (without converting) and compare
everything as naive local datetimes.
"""

from datetime import datetime


def parse_ts(s):
    """ISO-ish string -> naive datetime, or None."""
    if not s:
        return None
    s = str(s).strip()
    if s.endswith("Z"):
        s = s[:-1]
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt.replace(tzinfo=None)


def norm_ts(s):
    """Normalize a timestamp string to naive ISO format, or None."""
    dt = parse_ts(s)
    return dt.isoformat() if dt else None
