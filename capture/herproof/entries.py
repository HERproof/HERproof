"""Bridge into the HerProof pipeline: turn a capture index into `entries.json`
records, the same shape `ingest.py` produces from screenshots, so
`organize.py` and `export_packet.py` run on captured chats unchanged.

Differences from an OCR'd screenshot entry:
  source_type   "iphone_capture"  (text came from the iOS accessibility tree, not OCR)
  timestamp     always set, from the per-message time iOS shows, on the capture date
  confidence    1.0
  overlap       already removed at capture time; each message belongs to exactly one screenshot

    python -m herproof.entries evidence/alex/alex/alex_2026-09-25.json   # writes evidence/alex/entries.json
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from typing import Any


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _iso(date: str, clock: str) -> str | None:
    """'2026-09-25' + '1:10 PM' -> '2026-09-25T13:10:00' (naive local, like the pipeline)."""
    try:
        t = dt.datetime.strptime(clock.replace(" ", " ").strip(), "%I:%M %p").time()
        return dt.datetime.combine(dt.date.fromisoformat(date), t).isoformat()
    except ValueError:
        return None


def build_entries(index: dict[str, Any], base_dir: str = ".") -> list[dict[str, Any]]:
    date = index.get("date") or dt.date.today().isoformat()
    timeline = index.get("full_timeline", [])
    flagged = {(f["sender"], f["text"], f["time"]): f for f in index.get("flagged", [])}
    by_shot: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for m in timeline:
        shot = m.get("screenshot") or "(no screenshot)"
        if shot not in by_shot:
            by_shot[shot] = []
            order.append(shot)
        by_shot[shot].append(m)

    # Chronological entry order: the walk numbers screens newest-first, so the
    # screenshot that holds the oldest message comes first here.
    entries = []
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for shot in order:
        msgs = by_shot[shot]
        path = os.path.join(base_dir, shot) if not os.path.isabs(shot) else shot
        exists = os.path.isfile(path)
        out_msgs = []
        for i, m in enumerate(msgs):
            f = flagged.get((m.get("sender"), m.get("text"), m.get("time")))
            out_msgs.append({
                # the capture's own judgment, kept on the message so it survives organize.py
                "capture_flag": {"category": f["category"], "confidence": f["confidence"], "why": f["why"]} if f else None,
                "sender": "self" if m.get("sender") == "me" else "other",
                "sender_name": m.get("sender"),
                "timestamp": _iso(date, m.get("time", "")),
                "text": m.get("text", ""),
                "kind": m.get("kind", "text"),
                "confidence": 1.0,
                "source_file": os.path.basename(shot),
                "source_index": i,
            })
        capture_flags = [
            {"text": f["text"], "time": f["time"], "category": f["category"], "confidence": f["confidence"], "why": f["why"]}
            for f in (flagged.get((m.get("sender"), m.get("text"), m.get("time"))) for m in msgs) if f
        ]
        entries.append({
            "source_file": os.path.basename(shot),
            "source_path": shot,
            "imported_at": now,
            "file_hash": _sha256(path) if exists else None,
            "source_type": "iphone_capture",
            "exif_timestamp": None,
            "capture": {
                "chat": index.get("chat"), "device": index.get("device"), "date": date,
                "screenshot_with_times": next((m.get("screenshot_with_times") for m in msgs if m.get("screenshot_with_times")), None),
                "method": index.get("method"),
            },
            "raw_text": json.dumps([{k: m.get(k) for k in ("time", "sender", "text")} for m in msgs], ensure_ascii=False),
            "messages": out_msgs,
            "capture_flags": capture_flags,
            "parse_error": None if exists else f"screenshot not found: {shot}",
        })
    return entries


# capture categories -> the Pattern Map UI's category ids (web/pattern-map/index.html CATS)
UI_CATEGORY = {"insult": "degradation", "humiliation": "degradation", "other": "degradation",
               "threat": "threats", "control": "threats", "exclusion": "isolation", "pressure": "monitoring"}


def build_import_text(index: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """The Pattern Map UI's import format, one message per line:
        [DD/MM/YYYY, HH:MM:SS] Name: text
    plus the capture's flags keyed by line number, ready to merge into the UI's TAGS."""
    date = index.get("date") or dt.date.today().isoformat()
    d = dt.date.fromisoformat(date)
    flagged = {(f["sender"], f["text"], f["time"]): f for f in index.get("flagged", [])}
    lines, tags = [], []
    for m in index.get("full_timeline", []):
        iso = _iso(date, m.get("time", ""))
        clock = iso[11:19] if iso else "00:00:00"
        name = "Me" if m.get("sender") == "me" else (m.get("sender") or "Them")
        text = " ".join((m.get("text") or "").split())
        if m.get("kind") in ("link", "attachment"):
            text = f"({m['kind']}) {text}"
        lines.append(f"[{d.day:02d}/{d.month:02d}/{d.year}, {clock}] {name}: {text}")
        f = flagged.get((m.get("sender"), m.get("text"), m.get("time")))
        if f:
            tags.append({"line": len(lines), "category": UI_CATEGORY.get(f["category"], "degradation"),
                         "capture_category": f["category"], "confidence": f["confidence"],
                         "reasons": [f"flagged at capture ({f['category']}, {f['confidence']}): {f['why']}"],
                         "text": text, "screenshot": f.get("screenshot_with_times") or f.get("screenshot")})
    return "\n".join(lines) + "\n", tags


def write_entries(index_path: str, out_path: str | None = None, base_dir: str = ".") -> str:
    index = json.load(open(index_path))
    entries = build_entries(index, base_dir=base_dir)
    if out_path is None:
        # evidence/<run>/<chat>/<chat>_<date>.json -> evidence/<run>/entries.json
        out_path = os.path.join(os.path.dirname(os.path.dirname(index_path)), "entries.json")
    with open(out_path, "w") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    # UI import text + tags, beside entries.json
    run_dir = os.path.dirname(out_path)
    text, tags = build_import_text(index)
    with open(os.path.join(run_dir, "messages.txt"), "w") as f:
        f.write(text)
    with open(os.path.join(run_dir, "capture-tags.json"), "w") as f:
        json.dump({"chat": index.get("chat"), "date": index.get("date"), "device": index.get("device"), "tags": tags}, f, indent=2, ensure_ascii=False)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    p = write_entries(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    n = sum(len(e["messages"]) for e in json.load(open(p)))
    print(f"wrote {p}: {n} messages")
