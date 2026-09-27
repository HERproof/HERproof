"""
HerProof — P3: merge + organize into a timeline.

Reads entries.json, merges all messages, removes the overlap between
consecutive screenshots, sorts by time, tags each message against the CDC
categories (matchers.py), groups into incidents on time gaps, asks Gemini
for a neutral summary per incident, and builds a flags list.

When a screenshot shows no send-times, its messages get an
`approx_timestamp` from the screenshot's EXIF capture time. That is when the
screenshot was taken, so the messages were sent at or before it.

Outputs timeline.json (see DATA_SHAPE.md).

Usage:  python organize.py
"""

import json
from datetime import timedelta

import llm
import matchers
from timeutil import parse_ts, norm_ts

GAP_HOURS = 6           # split incidents when messages are >6h apart
LOW_CONFIDENCE = 0.6    # flag messages below this

SUMMARY_PROMPT = """You are given messages from one incident, as JSON.
Write a neutral, factual 2-3 sentence summary: dates, participants (self/other),
and what was communicated. No adjectives, no interpretation, no advice.
Return only the summary text."""


def load_entries():
    with open("entries.json") as f:
        return json.load(f)


def _key(m):
    return (m.get("sender"), " ".join((m.get("text") or "").split()).lower())


def remove_overlap(prev, cur):
    """Consecutive screenshots of one thread usually overlap: the bottom of
    one repeats at the top of the next. Drop only that repeated run, so two
    genuinely separate "ok" messages are both kept."""
    for k in range(min(len(prev), len(cur)), 0, -1):
        if [_key(m) for m in prev[-k:]] == [_key(m) for m in cur[:k]]:
            return cur[k:], k
    return cur, 0


def load_messages(entries):
    msgs, overlap_dropped = [], 0
    prev_shot = []
    for order, e in enumerate(entries):
        cur = [dict(m) for m in e.get("messages", [])]
        for i, m in enumerate(cur):
            m.setdefault("source_index", i)
            m["entry_order"] = order
            m["timestamp"] = norm_ts(m.get("timestamp"))
            if not m["timestamp"] and e.get("exif_timestamp"):
                m["approx_timestamp"] = norm_ts(e["exif_timestamp"])
        if e.get("source_type") == "screenshot":
            cur, dropped = remove_overlap(prev_shot, cur)
            overlap_dropped += dropped
            prev_shot = [m for m in e.get("messages", [])]
        else:
            prev_shot = []
        msgs.extend(cur)

    # the same export imported twice: identical sender + exact time + text
    seen, out = set(), []
    for m in msgs:
        if m["timestamp"]:
            k = (_key(m), m["timestamp"])
            if k in seen:
                overlap_dropped += 1
                continue
            seen.add(k)
        out.append(m)
    return out, overlap_dropped


def effective_dt(m):
    return parse_ts(m.get("timestamp") or m.get("approx_timestamp"))


def sort_key(m):
    dt = effective_dt(m)
    # messages with no time at all go last, in file order
    return (dt is None, dt or 0, m["entry_order"], m["source_index"])


def group_incidents(msgs):
    """Split the timeline where there's a gap > GAP_HOURS between timed msgs."""
    incidents, current = [], []
    last_dt = None
    for m in msgs:
        dt = effective_dt(m)
        if dt and last_dt and (dt - last_dt) > timedelta(hours=GAP_HOURS):
            incidents.append(current)
            current = []
        current.append(m)
        if dt:
            last_dt = dt
    if current:
        incidents.append(current)
    return incidents


def summarize(incident_msgs):
    visible = [
        {k: m.get(k) for k in ("sender", "timestamp", "approx_timestamp", "text")}
        for m in incident_msgs if m.get("sender") != "system"
    ]
    try:
        return llm.generate([SUMMARY_PROMPT, json.dumps(visible, indent=2)]).strip()
    except Exception as ex:
        return f"(summary unavailable: {ex})"


def incident_bounds(inc):
    times = [(effective_dt(m), m) for m in inc if effective_dt(m)]
    if not times:
        return None, None, False
    approx = any(not m.get("timestamp") for _, m in times)
    return times[0][0].isoformat(), times[-1][0].isoformat(), approx


def build_flags(entries, msgs, incidents, overlap_dropped):
    """Flags are dicts: {"kind", "text"} plus kind-specific fields."""
    flags = []
    for e in entries:
        if e.get("parse_error"):
            flags.append({"kind": "parse_error", "source_file": e["source_file"],
                          "text": f"{e['source_file']}: {e['parse_error']}. "
                                  "Check the original file by hand."})
    for m in msgs:
        if m.get("confidence", 1.0) < LOW_CONFIDENCE:
            snippet = (m.get("text") or "")[:40]
            flags.append({"kind": "low_confidence", "source_file": m.get("source_file"),
                          "text": f"Low OCR confidence ({m['confidence']:.2f}) on "
                                  f"{m.get('source_file')}: \"{snippet}\". Review the original."})
    untimed = [m for m in msgs if not effective_dt(m)]
    if untimed:
        files = sorted({m.get("source_file") for m in untimed})
        flags.append({"kind": "no_time", "count": len(untimed),
                      "text": f"{len(untimed)} messages have no time at all "
                              f"({', '.join(files)}). They are listed last, in file order."})
    approx = [m for m in msgs if not m.get("timestamp") and m.get("approx_timestamp")]
    if approx:
        flags.append({"kind": "approx_time", "count": len(approx),
                      "text": f"{len(approx)} messages show no send-time; they are dated by "
                              "when the screenshot was taken, so they were sent at or before it."})
    if overlap_dropped:
        flags.append({"kind": "overlap", "count": overlap_dropped,
                      "text": f"{overlap_dropped} repeated messages from overlapping "
                              "screenshots were counted once."})
    for a, b in zip(incidents, incidents[1:]):
        end = incident_bounds(a)[1]
        start = incident_bounds(b)[0]
        if end and start:
            days = (parse_ts(start) - parse_ts(end)).days
            flags.append({"kind": "gap", "start": end, "end": start, "days": days,
                          "text": f"No records between {end} and {start}"
                                  f"{f' ({days} days)' if days else ''}. "
                                  "Possible missing messages, not necessarily a calm period."})
    return flags


def main():
    entries = load_entries()
    msgs, overlap_dropped = load_messages(entries)
    msgs.sort(key=sort_key)
    matchers.enrich(msgs)

    incidents_raw = group_incidents(msgs)
    incidents = []
    for inc in incidents_raw:
        start, end, approx = incident_bounds(inc)
        incidents.append({
            "start": start,
            "end": end,
            "approximate": approx,
            "summary": summarize(inc),
            "message_count": len(inc),
        })

    out = {
        "timeline": msgs,
        "incidents": incidents,
        "patterns": matchers.summary(msgs),
        "prevalence_source": matchers.PREVALENCE_SOURCE,
        "flags": build_flags(entries, msgs, incidents_raw, overlap_dropped),
    }
    with open("timeline.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote timeline.json — {len(msgs)} messages, {len(incidents)} incidents, "
          f"{sum(p['count'] for p in out['patterns'])} pattern hits, {len(out['flags'])} flags")


if __name__ == "__main__":
    main()
