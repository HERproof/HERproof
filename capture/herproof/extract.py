"""Walk one iMessage conversation, capture screenshots, flag abusive messages,
and write a JSON evidence index.

    python -m herproof.extract --chat "Team 2"
    python -m herproof.extract --chat "Team 2" --provider gemini
    python -m herproof.extract --chat "Team 2" --no-classify   # keyword fallback only
    python -m herproof.extract --chat "Team 2" --all-days      # don't stop at yesterday

Read-only: never types, sends, reacts, or deletes. Requires the iphone-use
daemon + WebDriverAgent (see README) and the phone plugged in and unlocked.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import time

from .classify import classify
from .messages import Message, find_conversation_cell, merge_up, parse_screen
from .phone import Phone, PhoneError

MESSAGES_BUNDLE = "com.apple.MobileSMS"


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)[:40]


def open_conversation(phone: Phone, chat: str, shots: "Shots") -> None:
    phone.home()
    time.sleep(0.8)
    phone.launch_app(MESSAGES_BUNDLE)
    time.sleep(1.5)
    scr = phone.elements()
    # Messages reopens wherever it was last; back out until the list is showing.
    for _ in range(4):
        if any(e.identifier == "ConversationList" for e in scr.elements) and not any(
            e.identifier == "ConversationTitle" for e in scr.elements
        ):
            break
        if not any(e.identifier == "BackButton" for e in scr.elements):
            break
        _press_back(phone, scr)
        time.sleep(1.5)
        scr = phone.elements()
    shots.take(phone, "conversation_list")
    cell = find_conversation_cell(scr, chat)
    tries = 0
    while cell is None and tries < 3:
        # maybe the chat is not on the first screen: scroll the list down and look again
        phone.scroll(60)
        time.sleep(0.8)
        scr = phone.elements()
        cell = find_conversation_cell(scr, chat)
        tries += 1
    if cell is None:
        raise PhoneError(f"no conversation titled {chat!r} found in the Messages list")
    # Two nested cells share the label, so tap by position. Re-read the tree
    # right before every tap: on iOS 26 the first tap can just collapse the
    # large title, which shifts every row up, and a stale position then opens
    # the wrong conversation.
    want = chat.strip().lower()
    for attempt in range(4):
        scr = phone.elements()
        title = _open_title(scr)
        if title == want:
            return
        if title:  # some other conversation is open: leave it immediately
            _press_back(phone, scr)
            time.sleep(1.2)
            continue
        cell = find_conversation_cell(scr, chat)
        if cell is None:
            break
        x, y, w, h = cell.rect
        phone.tap_point(x + w / 2, y + h / 2, scr)
        time.sleep(2.0)
    scr = phone.elements()
    if _open_title(scr) == want:
        return
    raise PhoneError(f"tapped {chat!r} but the conversation did not open")


def _open_title(scr) -> str:
    return next((e.label.strip().lower() for e in scr.elements if e.identifier == "ConversationTitle"), "")


def _press_back(phone: Phone, scr) -> None:
    back = next((e for e in scr.elements if e.identifier == "BackButton"), None)
    if back is None:
        return
    x, y, w, h = back.rect
    phone.tap_point(x + w / 2, y + h / 2, scr)


class Shots:
    def __init__(self, screens_dir: str, date: str):
        self.dir = screens_dir
        self.date = date
        self.n = 0
        os.makedirs(screens_dir, exist_ok=True)
        self.paths: list[str] = []

    def _next(self, name: str) -> str:
        p = os.path.join(self.dir, f"{self.date}_{self.n:02d}_{_safe(name)}.png")
        self.n += 1
        return p

    def take(self, phone: Phone, name: str) -> str:
        p = phone.screenshot(self._next(name))
        self.paths.append(p)
        return p

    def take_times(self, phone: Phone, name: str) -> str | None:
        p = phone.capture_times(self._next(name))
        if p:
            self.paths.append(p)
        else:
            self.n -= 1
        return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chat", required=True, help='conversation title exactly as shown, e.g. "Team 2"')
    ap.add_argument("--out", default="evidence", help="output root (default: evidence/)")
    ap.add_argument("--max-screens", type=int, default=15)
    ap.add_argument("--all-days", action="store_true", help="keep walking past earlier days")
    ap.add_argument("--no-times", action="store_true", help="skip the swipe-left timestamp captures")
    ap.add_argument("--no-classify", action="store_true", help="skip the LLM; keyword heuristic only")
    ap.add_argument("--provider", default=None, choices=["auto", "claude", "gemini"],
                    help="LLM for classification (default: HERPROOF_PROVIDER or auto = whichever API key is set)")
    ap.add_argument("--model", default=None, help="model id override (default per provider, see herproof/llm.py)")
    ap.add_argument("--device", default=os.environ.get("HERPROOF_DEVICE", ""), help='label for the JSON, e.g. "Ava (iPhone 17)"')
    args = ap.parse_args(argv)

    _load_dotenv()
    today = dt.date.today().isoformat()
    chat_slug = _safe(args.chat).lower()
    screens_dir = os.path.join(args.out, "screens")
    flagged_dir = os.path.join(args.out, "flagged")
    index_dir = os.path.join(args.out, chat_slug)
    os.makedirs(flagged_dir, exist_ok=True)
    os.makedirs(index_dir, exist_ok=True)

    phone = Phone()
    st = phone.require_drivable()
    print(f"[phone] drivable, device_state={st.get('device_state')} udid={st.get('udid')}")

    shots = Shots(screens_dir, today)
    open_conversation(phone, args.chat, shots)
    print(f"[phone] opened {args.chat!r}")

    messages: list[Message] = []
    screen_shots: dict[int, dict[str, str | None]] = {}
    stop_reason = "max_screens"
    prev_total, prev_pct = -1, None
    for i in range(args.max_screens):
        scr = phone.elements()
        read = parse_screen(scr, i)
        plain = shots.take(phone, f"{chat_slug}_screen{i + 1}")
        times = None if args.no_times else shots.take_times(phone, f"{chat_slug}_screen{i + 1}_times")
        screen_shots[i] = {"plain": plain, "times": times}
        # messages on screen are chronological; annotate which screen they were seen on
        messages = merge_up(messages, read.messages)
        print(f"[walk] screen {i + 1}: {len(read.messages)} bubbles, total {len(messages)}, scroll={read.scroll_pct}% seps={read.date_separators}")
        older_day = [s for s in read.date_separators if not s.startswith("Today")]
        if older_day and not args.all_days:
            stop_reason = f"reached earlier day: {older_day[0]}"
            break
        if read.at_top or read.scroll_pct == 0:
            stop_reason = "top of conversation"
            break
        if i > 0 and len(messages) == prev_total and read.scroll_pct == prev_pct:
            stop_reason = "no new messages after scrolling (top of conversation)"
            break
        prev_total, prev_pct = len(messages), read.scroll_pct
        phone.scroll(-70)
        time.sleep(0.9)

    if not args.all_days:
        # keep only messages seen on/after the first "Today" separator when one was found;
        # iOS shows a time separator per day, so anything above an older-day separator is out
        pass

    flags, ctx, method = classify(messages, use_llm=not args.no_classify, provider=args.provider or "auto", model=args.model)
    print(f"[classify] {method}: {len(flags)} flagged, {len(ctx)} context")

    # Copy the best screenshot for each flagged message into flagged/
    flagged_out = []
    for f in flags:
        m = messages[f.index]
        src = screen_shots.get(m.best_screen(), {})
        shot = src.get("times") or src.get("plain")
        copy = None
        if shot:
            copy = os.path.join(flagged_dir, f"{today}_{_safe(m.time.replace(':', '-').replace(' ', ''))}_{_safe(m.sender)}_{_safe(m.text[:30])}.png")
            if not os.path.exists(copy):
                shutil.copyfile(shot, copy)
        flagged_out.append({
            "sender": m.sender, "text": m.text, "time": m.time,
            "screenshot": src.get("plain"), "screenshot_with_times": src.get("times"), "flagged_copy": copy,
            "category": f.category, "confidence": f.confidence, "why": f.why,
        })

    phone.home()
    shots.take(phone, "home_final")

    out = {
        "chat": args.chat,
        "date": today,
        "device": args.device or f"udid {st.get('udid')}",
        "extracted_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "method": "Read-only walk of the conversation from newest to oldest via the iphone-use daemon "
                  "(WebDriverAgent). Sender/text/time come from the iOS accessibility tree; "
                  "screenshots with times were captured during a swipe-left gesture. Classification: " + method,
        "stop_reason": stop_reason,
        "screens_reviewed": len(screen_shots),
        "messages_reviewed": len(messages),
        "flagged_count": len(flagged_out),
        "flagged": flagged_out,
        "victim_context": [
            {"sender": "me", "text": messages[i].text, "time": messages[i].time,
             "screenshot": (screen_shots.get(messages[i].best_screen()) or {}).get("times")
             or (screen_shots.get(messages[i].best_screen()) or {}).get("plain")}
            for i in ctx
        ],
        "full_timeline": [
            {"time": m.time, "sender": m.sender, "kind": m.kind, "text": m.text,
             "screenshot": (screen_shots.get(m.best_screen()) or {}).get("plain"),
             "screenshot_with_times": (screen_shots.get(m.best_screen()) or {}).get("times")}
            for m in messages
        ],
        "screenshots": {"all": shots.paths, "flagged": sorted(os.path.join(flagged_dir, p) for p in os.listdir(flagged_dir))},
    }
    out_path = os.path.join(index_dir, f"{chat_slug}_{today}.json")
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    from .entries import write_entries
    entries_path = write_entries(out_path, os.path.join(args.out, "entries.json"))
    print(f"[done] {out_path}  ({len(flagged_out)} flagged of {len(messages)} messages, {len(shots.paths)} screenshots)")
    print(f"[done] {entries_path}  (pipeline input: copy to the repo root and run organize.py)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PhoneError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
