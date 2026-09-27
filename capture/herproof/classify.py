"""Flag abusive / bullying messages.

Primary path: an LLM (Claude or Gemini, see llm.py) with a JSON-schema output. Fallback path
(`--no-classify` or no credentials): a conservative keyword heuristic so the
pipeline still produces a reviewable JSON.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from .messages import Message

CATEGORIES = ["insult", "threat", "humiliation", "exclusion", "pressure", "control", "other"]

_SCHEMA = {
    "type": "object",
    "properties": {
        "flagged": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "why": {"type": "string"},
                },
                "required": ["index", "category", "confidence", "why"],
                "additionalProperties": False,
            },
        },
        "context": {
            "type": "array",
            "description": "Indexes of the phone owner's own messages that show the impact (e.g. 'I don't feel safe').",
            "items": {"type": "integer"},
        },
    },
    "required": ["flagged", "context"],
    "additionalProperties": False,
}

SYSTEM = """You review a private text-message conversation on behalf of the phone's owner, who is
documenting abuse or bullying directed at them. Messages are given in chronological order with an
index, sender and time. The owner's own messages have sender "me".

Flag every message (never the owner's own) that insults, threatens, humiliates, excludes, pressures,
or tries to control the owner, or encourages others to. Judge each message in the context of the
ones around it: a line that looks neutral on its own can be part of a pattern (for example a
'stay at home Mom for a decade' remark inside a string of insults). Quote nothing; return only
indexes. Work-related links, file names, email addresses and logistics are not abuse. When unsure,
include the message with confidence "low" rather than dropping it.

Also return, as context, the indexes of the owner's own messages that show how the messages landed
(e.g. 'I don't feel safe', 'please stop')."""


@dataclass
class Flag:
    index: int
    category: str
    confidence: str
    why: str


def _transcript(msgs: list[Message]) -> str:
    lines = []
    for i, m in enumerate(msgs):
        tag = f" [{m.kind}]" if m.kind != "text" else ""
        lines.append(f"{i}. [{m.time}] {m.sender}{tag}: {m.text}")
    return "\n".join(lines)


def classify_with_llm(msgs: list[Message], provider: str = "auto", model: str | None = None) -> tuple[list[Flag], list[int], str]:
    from .llm import complete_json, resolve_provider, DEFAULT_MODELS

    provider = resolve_provider(provider)
    model = model or DEFAULT_MODELS[provider]
    data = complete_json(SYSTEM, "Conversation:\n\n" + _transcript(msgs), _SCHEMA, provider=provider, model=model)
    flags = [Flag(**f) for f in data.get("flagged", []) if 0 <= f["index"] < len(msgs) and not msgs[f["index"]].is_me]
    ctx = [i for i in data.get("context", []) if 0 <= i < len(msgs) and msgs[i].is_me]
    return flags, ctx, f"{provider}:{model}"


_KEYWORDS = [
    (r"\buseless\b|\bworthless\b|\bstupid\b|\bidiot\b|\bpathetic\b|\bdisgusting\b|\bugly\b|\bfat\b", "insult"),
    (r"\bmore useful than you\b|\bnobody (likes|wants) you\b|\byou (don'?t|dont) even\b|\blike a (cat|dog|pig)\b", "insult"),
    (r"\b(i'?ll|i will|gonna|going to) (hurt|kill|ruin|destroy|take)\b|\bruin your\b|\byou'?ll regret\b|\bor else\b", "threat"),
    (r"\bstop taking the kids\b|\bthe kids\b.*\b(take|taking|away)\b|\btake .* away\b", "control"),
    (r"\bso dramatic\b|\bcrazy\b|\bhysterical\b|\boverreacting\b|\bshut up\b", "humiliation"),
    (r"\bnobody cares\b|\bno one cares\b|\bkill yourself\b|\bkys\b", "threat"),
]


def classify_heuristic(msgs: list[Message]) -> tuple[list[Flag], list[int]]:
    flags: list[Flag] = []
    for i, m in enumerate(msgs):
        if m.is_me or m.kind != "text":
            continue
        for pat, cat in _KEYWORDS:
            if re.search(pat, m.text, re.I):
                flags.append(Flag(i, cat, "medium", f"keyword match: {pat.split('|')[0].strip(chr(92)+'b')}"))
                break
    ctx = [i for i, m in enumerate(msgs) if m.is_me and re.search(r"feel safe|please stop|stop it|scared|afraid|hurt", m.text, re.I)]
    return flags, ctx


def classify(msgs: list[Message], use_llm: bool = True, provider: str = "auto", model: str | None = None) -> tuple[list[Flag], list[int], str]:
    if use_llm:
        try:
            return classify_with_llm(msgs, provider=provider, model=model)
        except Exception as e:  # noqa: BLE001 - fall back, but say so
            if os.environ.get("HERPROOF_STRICT"):
                raise
            print(f"[classify] LLM unavailable ({type(e).__name__}: {e}); using keyword heuristic")
    f, c = classify_heuristic(msgs)
    return f, c, "heuristic"
