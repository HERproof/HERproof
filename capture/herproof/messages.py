"""Parsing the iOS Messages accessibility tree into message records."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .phone import Element, Screen

# "Husband, You are so dramatic, 11:27 AM"  /  "Your iMessage, Okay, 11:27 AM"
_CELL_RE = re.compile(r"^(?P<sender>.+?), (?P<text>.*), (?P<time>\d{1,2}:\d{2} [AP]M)$", re.S)
_TIME_ONLY_RE = re.compile(r"^\d{1,2}:\d{2} [AP]M$")
_DATE_SEP_RE = re.compile(r"^(Today|Yesterday|[A-Z][a-z]+day|[A-Z][a-z]{2} \d{1,2}, \d{4}|\d{1,2}/\d{1,2}/\d{2,4})\b")
_CHAT_NAME_TAIL = re.compile(r"\.$")


@dataclass
class Message:
    sender: str
    text: str
    time: str
    screen_index: int
    is_me: bool = False
    kind: str = "text"  # text | link | attachment
    # every (screen_index, vertical position 0..1) this bubble was seen at
    sightings: list[tuple[int, float]] = field(default_factory=list)

    def key(self) -> tuple[str, str, str]:
        return (self.sender, self.text, self.time)

    def best_screen(self) -> int:
        """Screen where the bubble sits closest to the middle (fully visible)."""
        if not self.sightings:
            return self.screen_index
        return min(self.sightings, key=lambda s: abs(s[1] - 0.5))[0]


@dataclass
class ScreenRead:
    messages: list[Message]            # chronological (top to bottom)
    date_separators: list[str] = field(default_factory=list)
    at_top: bool = False               # "iMessage Encrypted" banner / 0% scroll
    scroll_pct: int | None = None
    title: str = ""


def _norm(s: str) -> str:
    # iOS uses narrow no-break spaces before AM/PM and in some banners
    return s.replace("\u202f", " ").replace("\u00a0", " ").replace("\u2009", " ")


def parse_screen(screen: Screen, screen_index: int) -> ScreenRead:
    msgs: list[Message] = []
    seps: list[str] = []
    at_top = False
    scroll_pct = None
    title = ""
    for e in screen.elements:
        e = Element(kind=e.kind, label=_norm(e.label), rect=e.rect, depth=e.depth, identifier=e.identifier,
                    value=e.value, accessible=e.accessible, visible=e.visible)
        if e.identifier == "ConversationTitle":
            title = e.label
        if e.kind == "Other" and e.label.startswith("Vertical scroll bar") and e.rect[2] >= 25:
            v = e.value.rstrip("%")
            if v.isdigit():
                scroll_pct = int(v)
        if e.kind == "StaticText" and e.label.replace(" ", " ").strip().lower().startswith("imessage") and "encrypted" in e.label.lower():
            at_top = True
        if e.kind == "StaticText" and _DATE_SEP_RE.match(e.label) and e.rect[0] <= 20 and e.rect[2] >= 300:
            seps.append(e.label)
        # Message cells: the outer Cell at depth ~15 carries "sender, text, time".
        if e.kind == "Cell" and e.identifier != "Sticker" and e.rect[2] >= 300:
            m = _CELL_RE.match(e.label)
            if not m:
                continue
            sender, text, t = m.group("sender"), m.group("text"), m.group("time")
            is_me = sender == "Your iMessage"
            kind = "text"
            if ", drive.google.com" in text or text.endswith("github.com") or "http" in text and "\n" not in text and len(text.split()) == 1:
                kind = "link"
            if re.search(r"\b\d+ KB\b|\b\d+ MB\b|Attachment:|\d+ image\b", text):
                kind = "attachment"
            y_frac = (e.rect[1] + e.rect[3] / 2) / (screen.height or 1)
            msgs.append(Message(sender="me" if is_me else sender, text=text, time=t,
                                screen_index=screen_index, is_me=is_me, kind=kind,
                                sightings=[(screen_index, y_frac)]))
    return ScreenRead(messages=msgs, date_separators=seps, at_top=at_top, scroll_pct=scroll_pct, title=title)


def merge_up(accumulated: list[Message], newer_screen_above: list[Message]) -> list[Message]:
    """We walk from the bottom (newest) upward. `accumulated` is chronological
    and starts at the newest message; each new screen shows older messages
    that overlap with the top of what we already have. Find the longest
    suffix of the new screen equal to the prefix of accumulated and prepend
    the rest."""
    if not accumulated:
        return list(newer_screen_above)
    new_keys = [m.key() for m in newer_screen_above]
    acc_keys = [m.key() for m in accumulated]
    best = 0
    for k in range(min(len(new_keys), len(acc_keys)), 0, -1):
        if new_keys[-k:] == acc_keys[:k]:
            best = k
            break
    if best == 0:
        # no overlap: assume the whole screen is older and prepend it all
        return list(newer_screen_above) + accumulated
    for j in range(best):  # remember where the overlapping bubbles were seen again
        accumulated[j].sightings.extend(newer_screen_above[len(new_keys) - best + j].sightings)
    return list(newer_screen_above[:-best]) + accumulated


def find_conversation_cell(screen: Screen, chat_title: str) -> Element | None:
    """Return the outermost list Cell for a conversation titled `chat_title`."""
    want = chat_title.strip().lower()
    for e in screen.elements:
        if e.kind != "Cell" or not e.label:
            continue
        head = e.label.split(",")[0].strip().lower()
        if head == want and e.visible:
            return e
    return None
