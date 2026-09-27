"""
HerProof — WhatsApp .txt export parser.

Handles both export styles:
  iOS:      [2026-09-24, 9:42:13 PM] Other Person: where are you
  Android:  24/09/2026, 21:42 - Other Person: where are you

Day/month order is ambiguous (24/09 vs 09/24); formats are tried in the
order of DT_FORMATS and the first one that parses wins.

The exporting user's display name maps to "self". Set it with
HERPROOF_SELF_NAME in .env, or `python ingest.py ./samples --self "Name"`.
"""

import os
import re
from datetime import datetime

SELF_NAME = os.environ.get("HERPROOF_SELF_NAME", "")

# invisible direction marks iOS puts before system text and attachments
BIDI = "\u200E\u200F\u202A\u202B\u202C"

IOS_RE = re.compile(r"^\[(?P<dt>[^\]]+)\]\s*(?P<rest>.*)$")
ANDROID_RE = re.compile(r"^(?P<dt>\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\s+-\s+(?P<rest>.*)$")
SENDER_RE = re.compile(r"^(?P<sender>[^:]{1,80}):\s(?P<text>.*)$", re.S)

DT_FORMATS = [
    "%Y-%m-%d, %I:%M:%S %p",
    "%Y-%m-%d, %I:%M %p",
    "%d/%m/%Y, %H:%M:%S",
    "%d/%m/%Y, %H:%M",
    "%d/%m/%y, %H:%M:%S",
    "%d/%m/%y, %H:%M",
    "%m/%d/%y, %I:%M:%S %p",
    "%m/%d/%y, %I:%M %p",
    "%m/%d/%Y, %I:%M %p",
    "%d.%m.%y, %H:%M:%S",
    "%d.%m.%Y, %H:%M",
]

# WhatsApp's own notices, not written by either person
SYSTEM_PATTERNS = [
    "messages and calls are end-to-end encrypted",
    "created group", "added you", "changed the subject", "changed this group",
    "changed their phone number", "security code", "left", "joined using",
    "this message was deleted", "you deleted this message",
]
ATTACHMENT_RE = re.compile(
    r"^(<media omitted>|(image|video|audio|sticker|gif|document) omitted|<attached: .+>)",
    re.I,
)


def _parse_dt(s):
    s = s.strip().replace(" ", " ").replace(" ", " ")
    for fmt in DT_FORMATS:
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            continue
    return None


def _match_line(line):
    """Return (dt_string, rest) if the line starts a new message, else None."""
    for rx in (IOS_RE, ANDROID_RE):
        m = rx.match(line)
        if m and _parse_dt(m.group("dt")):
            return m.group("dt"), m.group("rest")
    return None


def _is_system(text):
    t = text.lower()
    return any(p in t for p in SYSTEM_PATTERNS)


def parse_file(path, self_name=None):
    self_name = self_name if self_name is not None else SELF_NAME
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    messages = []
    for line in raw.splitlines():
        line = line.lstrip(BIDI)
        hit = _match_line(line)
        if not hit:
            # continuation of the previous multi-line message
            if messages and line.strip():
                messages[-1]["text"] += "\n" + line
            continue
        dt, rest = hit
        sm = SENDER_RE.match(rest)
        if sm:
            sender_name = sm.group("sender").strip()
            raw_text = sm.group("text")
            text = raw_text.lstrip(BIDI)
            if raw_text[:1] in BIDI and _is_system(text):
                sender = "system"
            elif self_name and sender_name == self_name:
                sender = "self"
            else:
                sender = "other"
        else:
            # no "Name:" part at all, e.g. "You created group"
            sender_name, text, sender = None, rest.lstrip(BIDI), "system"
        messages.append({
            "sender": sender,
            "sender_name": sender_name,
            "timestamp": _parse_dt(dt),
            "text": text,
            "attachment": bool(ATTACHMENT_RE.match(text)),
            "confidence": 1.0,
            "source_file": os.path.basename(path),
            "source_index": len(messages),
        })
    return raw, messages


if __name__ == "__main__":
    import sys, json
    raw, msgs = parse_file(sys.argv[1])
    print(json.dumps(msgs, indent=2))
