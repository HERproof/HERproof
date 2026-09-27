"""Phone tools exposed to a driving model (Claude or Gemini).

One tool table, one executor. Providers only translate between this table
and their own function-calling format. Every tool returns a dict; screenshot
tools also return PNG bytes, which the provider attaches as an image.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Any

from .messages import parse_screen
from .phone import Phone, PhoneError, Screen

TOOLS: list[dict[str, Any]] = [
    {"name": "phone_status", "description": "Check the phone is drivable (unlocked, WebDriverAgent up). Call first.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "read_screen",
     "description": "Read the current screen as text: the foreground app, the navigation title, and a numbered list of visible elements (kind, label, position). In Messages, bubbles appear as 'sender, text, time'. Prefer this over screenshots; it is cheaper and exact.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "screenshot",
     "description": "Save a screenshot to the evidence folder and return it as an image. Use to confirm what you see or when pixels matter. `name` is a short label for the file.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "screenshot_with_times",
     "description": "In an open Messages conversation: drag the transcript left so every bubble shows its time, and save that frame. Use once per screen while walking a chat.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "tap_element",
     "description": "Tap an element by its index from the most recent read_screen.",
     "input_schema": {"type": "object", "properties": {"index": {"type": "integer"}}, "required": ["index"]}},
    {"name": "tap", "description": "Tap at a normalized position (0..1 from top-left). Only when tap_element cannot target it.",
     "input_schema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]}},
    {"name": "scroll",
     "description": "Scroll the screen. dy=-70 reveals content above (older messages); dy=70 reveals content below.",
     "input_schema": {"type": "object", "properties": {"dy": {"type": "number"}}, "required": ["dy"]}},
    {"name": "home", "description": "Go to the iOS home screen.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "launch_app", "description": "Open an app by bundle id, e.g. com.apple.MobileSMS for Messages, com.burbn.instagram for Instagram.",
     "input_schema": {"type": "object", "properties": {"bundle": {"type": "string"}}, "required": ["bundle"]}},
    {"name": "back", "description": "Tap the navigation Back button if there is one.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "flag_message",
     "description": "Record one abusive or bullying message you have seen on screen. Quote the text exactly. `screenshot` is the file name returned by screenshot/screenshot_with_times that shows it.",
     "input_schema": {"type": "object", "properties": {
         "sender": {"type": "string"}, "text": {"type": "string"}, "time": {"type": "string"},
         "category": {"type": "string", "enum": ["insult", "threat", "humiliation", "exclusion", "pressure", "control", "other"]},
         "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
         "why": {"type": "string"}, "screenshot": {"type": "string"}},
         "required": ["sender", "text", "time", "category", "confidence", "why", "screenshot"]}},
    {"name": "finish",
     "description": "End the task. Give a one-paragraph summary of what was reviewed and the stop reason. Call this exactly once, at the end.",
     "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}, "messages_reviewed": {"type": "integer"}},
                      "required": ["summary", "messages_reviewed"]}},
]

TOOL_NAMES = {t["name"] for t in TOOLS}


@dataclass
class ToolResult:
    data: dict[str, Any]
    image_png: bytes | None = None

    def text(self) -> str:
        return json.dumps(self.data, ensure_ascii=False)


@dataclass
class Executor:
    phone: Phone
    out_dir: str
    date: str = field(default_factory=lambda: dt.date.today().isoformat())
    last_screen: Screen | None = None
    shots: list[str] = field(default_factory=list)
    flagged: list[dict[str, Any]] = field(default_factory=list)
    finished: dict[str, Any] | None = None
    n: int = 0

    def __post_init__(self) -> None:
        os.makedirs(os.path.join(self.out_dir, "screens"), exist_ok=True)
        os.makedirs(os.path.join(self.out_dir, "flagged"), exist_ok=True)

    def _path(self, name: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:40]
        p = os.path.join(self.out_dir, "screens", f"{self.date}_{self.n:02d}_{safe}.png")
        self.n += 1
        return p

    def run(self, name: str, args: dict[str, Any]) -> ToolResult:
        if name not in TOOL_NAMES:
            return ToolResult({"error": f"unknown tool {name}"})
        try:
            return getattr(self, "t_" + name)(**args)
        except PhoneError as e:
            return ToolResult({"error": str(e)})
        except TypeError as e:
            return ToolResult({"error": f"bad arguments for {name}: {e}"})

    # ---- tools ----
    def t_phone_status(self) -> ToolResult:
        st = self.phone.status()
        return ToolResult({k: st.get(k) for k in ("drivable", "device_state", "wda", "hint", "setup_blocked_on", "owner")})

    def t_read_screen(self) -> ToolResult:
        scr = self.phone.elements()
        self.last_screen = scr
        app = next((e.label for e in scr.elements if e.kind == "Application"), "")
        title = next((e.label for e in scr.elements if e.identifier == "ConversationTitle"), "")
        rows = []
        for i, e in enumerate(scr.elements):
            if not e.visible or e.kind in ("Application", "Image") or e.label.startswith("Vertical scroll bar") or e.label.startswith("Horizontal scroll bar"):
                continue
            if e.identifier in ("AdditionalDimmingOverlay", "Sticker", "CKBalloonTextView"):
                continue
            if not e.label.strip():
                continue
            x, y, w, h = e.rect
            rows.append(f"[{i}] {e.kind} y={int(y + h / 2)} {e.label[:160]!r}")
        read = parse_screen(scr, 0)
        return ToolResult({
            "app": app, "conversation_title": title, "scroll_percent": read.scroll_pct,
            "date_separators": read.date_separators, "at_top_of_conversation": read.at_top,
            "screen_size": [scr.width, scr.height], "elements": rows,
        })

    def t_screenshot(self, name: str) -> ToolResult:
        p = self.phone.screenshot(self._path(name))
        self.shots.append(p)
        return ToolResult({"saved": os.path.basename(p)}, open(p, "rb").read())

    def t_screenshot_with_times(self, name: str) -> ToolResult:
        p = self.phone.capture_times(self._path(name))
        if not p:
            self.n -= 1
            return ToolResult({"error": "could not capture times (ffmpeg/PIL missing or nothing revealed); use screenshot instead"})
        self.shots.append(p)
        return ToolResult({"saved": os.path.basename(p)}, open(p, "rb").read())

    def t_tap_element(self, index: int) -> ToolResult:
        if self.last_screen is None:
            return ToolResult({"error": "call read_screen first"})
        try:
            e = self.last_screen.elements[index]
        except IndexError:
            return ToolResult({"error": f"no element {index}"})
        x, y, w, h = e.rect
        self.phone.tap_point(x + w / 2, y + h / 2, self.last_screen)
        time.sleep(1.5)
        return ToolResult({"tapped": e.label[:80]})

    def t_tap(self, x: float, y: float) -> ToolResult:
        self.phone.tap(x, y)
        time.sleep(1.2)
        return ToolResult({"tapped": [x, y]})

    def t_scroll(self, dy: float) -> ToolResult:
        self.phone.scroll(dy)
        time.sleep(0.9)
        return ToolResult({"scrolled": dy})

    def t_home(self) -> ToolResult:
        self.phone.home()
        time.sleep(0.8)
        return ToolResult({"ok": True})

    def t_launch_app(self, bundle: str) -> ToolResult:
        self.phone.launch_app(bundle)
        time.sleep(1.5)
        return ToolResult({"launched": bundle})

    def t_back(self) -> ToolResult:
        scr = self.phone.elements()
        b = next((e for e in scr.elements if e.identifier == "BackButton"), None)
        if b is None:
            return ToolResult({"error": "no Back button on this screen"})
        x, y, w, h = b.rect
        self.phone.tap_point(x + w / 2, y + h / 2, scr)
        time.sleep(1.2)
        return ToolResult({"ok": True})

    def t_flag_message(self, **rec: Any) -> ToolResult:
        shot = rec.get("screenshot", "")
        src = next((p for p in self.shots if os.path.basename(p) == shot), None)
        copy = None
        if src:
            t = rec.get("time", "").replace(":", "-").replace(" ", "")
            snd = "".join(c if c.isalnum() else "_" for c in rec.get("sender", ""))[:20]
            txt = "".join(c if c.isalnum() else "_" for c in rec.get("text", ""))[:30]
            copy = os.path.join(self.out_dir, "flagged", f"{self.date}_{t}_{snd}_{txt}.png")
            if not os.path.exists(copy):
                shutil.copyfile(src, copy)
        rec = dict(rec)
        rec["screenshot"] = src
        rec["flagged_copy"] = copy
        self.flagged.append(rec)
        return ToolResult({"recorded": len(self.flagged), "flagged_copy": copy and os.path.basename(copy)})

    def t_finish(self, summary: str, messages_reviewed: int) -> ToolResult:
        self.finished = {"summary": summary, "messages_reviewed": messages_reviewed}
        return ToolResult({"ok": True})


def png_b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("ascii")
