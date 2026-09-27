"""
HerProof — P1: sweep + ingest + OCR/parse per file.

Walks a folder, and for every file:
  - computes a SHA-256 hash (integrity anchor)
  - reads EXIF timestamp (images)
  - screenshots/photos -> Gemini multimodal: OCR + parse into messages[]
  - WhatsApp .txt      -> parsed directly (real timestamps, no OCR)

Outputs a list of Entry dicts (see DATA_SHAPE.md) to entries.json.

Privacy: images are sent to Google's Gemini API (see llm.py).

Usage:  python ingest.py ./samples [--self "WhatsApp display name"]
"""

import sys
import os
import json
import hashlib
from datetime import datetime, timezone

from PIL import Image

import llm
import whatsapp  # local module, WhatsApp .txt parser
from timeutil import norm_ts

try:  # HEIC support is optional: pip install pillow-heif
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_OK = True
except ImportError:
    HEIC_OK = False

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"}

PARSE_PROMPT = """You are parsing a screenshot of a message conversation.
Read all visible text and return ONLY a JSON array of messages, top to bottom. For each message include:
  "sender": "self" or "other" (infer from bubble position, right side = self; "unknown" if unclear)
  "timestamp": ISO 8601 string if a send-time is visible in the image, else null
  "text": the message text, verbatim; if garbled, preserve it as-is
  "confidence": number 0-1, lower it when the text is unclear
If the image is not a conversation, return [].
Do not invent, complete, or paraphrase any text. Return only the JSON array, no prose."""

EXIF_DATETIME_ORIGINAL = 0x9003
EXIF_DATETIME = 0x0132


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def exif_timestamp(img):
    """Return original capture time as ISO string, or None."""
    try:
        exif = img.getexif()
        value = exif.get_ifd(0x8769).get(EXIF_DATETIME_ORIGINAL) or exif.get(EXIF_DATETIME)
        if value:
            # EXIF format: "2026:09:24 21:45:00"
            return datetime.strptime(value.strip("\x00 "), "%Y:%m:%d %H:%M:%S").isoformat()
    except Exception:
        pass
    return None


def _extract_json(text):
    """Strip markdown fences and return the parsed JSON value."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def parse_image(img, name):
    """Send an image to Gemini. Returns (raw_text, messages, error)."""
    raw = llm.generate([PARSE_PROMPT, img])
    try:
        data = _extract_json(raw)
    except json.JSONDecodeError:
        return raw, [], "Model reply was not valid JSON"
    if isinstance(data, dict):  # {"messages": [...]} instead of a bare list
        data = data.get("messages", [])
    if not isinstance(data, list):
        return raw, [], "Model reply was not a list of messages"

    messages = []
    for i, m in enumerate(x for x in data if isinstance(x, dict)):
        conf = m.get("confidence", 0.5)
        messages.append({
            "sender": m.get("sender") if m.get("sender") in ("self", "other") else "unknown",
            "timestamp": norm_ts(m.get("timestamp")),
            "text": str(m.get("text") or ""),
            "confidence": float(conf) if isinstance(conf, (int, float)) else 0.5,
            "source_file": name,
            "source_index": i,  # position within the screenshot, top to bottom
        })
    return raw, messages, None


def make_entry(path):
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    base = {
        "source_file": name,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "file_hash": sha256(path),
        "parse_error": None,
    }

    if ext == ".txt":
        raw, messages = whatsapp.parse_file(path)
        base.update(source_type="whatsapp_export", exif_timestamp=None,
                    raw_text=raw, messages=messages)
    elif ext in IMAGE_EXTS:
        if ext in (".heic", ".heif") and not HEIC_OK:
            base.update(source_type="photo", exif_timestamp=None, raw_text="", messages=[],
                        parse_error="HEIC file skipped: install pillow-heif to read it")
            return base
        try:
            img = Image.open(path)
            img.load()
        except Exception as ex:
            base.update(source_type="photo", exif_timestamp=None, raw_text="", messages=[],
                        parse_error=f"Could not open image: {ex}")
            return base
        try:
            raw, messages, error = parse_image(img, name)
        except Exception as ex:
            raw, messages, error = "", [], f"Gemini request failed: {ex}"
        # only call it a plain photo when the model actually answered and found nothing
        stype = "screenshot" if messages or error else "photo"
        base.update(source_type=stype, exif_timestamp=exif_timestamp(img),
                    raw_text=raw, messages=messages, parse_error=error)
    else:
        return None  # skip unknown file types
    return base


def sweep(folder):
    entries = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path) or name.startswith("."):
            continue
        print(f"  ingesting {name} ...")
        entry = make_entry(path)
        if entry:
            if entry["parse_error"]:
                print(f"    ! {entry['parse_error']}")
            entries.append(entry)
    return entries


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--self" in args:
        i = args.index("--self")
        whatsapp.SELF_NAME = args[i + 1]
        del args[i:i + 2]
    folder = args[0] if args else "./samples"
    print(f"Sweeping {folder}")
    entries = sweep(folder)
    with open("entries.json", "w") as f:
        json.dump(entries, f, indent=2)
    print(f"Wrote {len(entries)} entries -> entries.json")
