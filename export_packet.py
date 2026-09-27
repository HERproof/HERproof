"""
HerProof — P5: attorney packet export.

Reads entries.json + timeline.json and writes packet.html in the attorney
packet design (web/pattern-map/packet.html). Open it in a browser
and press "Download as PDF".

Only what the record supports is filled. Names, addresses, and the orders
to request are left blank on purpose: a guess on a form the police act on
is worse than an empty line.

Pages: cover and at-a-glance, DV-100 items 1 to 9, CLETS-001, flagged
forms, the item 5c attachment (every flagged message in date order),
exhibit list with re-verified SHA-256 fingerprints, the original images
embedded, review flags and incident summaries, and the method.

Usage:  python export_packet.py ./samples
"""

import sys
import os
import io
import re
import json
import html
import base64
import hashlib
import textwrap
from datetime import datetime

from PIL import Image

from timeutil import parse_ts

try:  # lets HEIC exhibits be embedded (browsers can't show HEIC)
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

ROWS_PER_PAGE = 22
APP_LINK = "web/pattern-map/app.html"

# matchers.py category -> (at-a-glance wording, short kind label)
PLAIN = {
    "Monitoring": ("Checking where the petitioner is, location and phone", "Checking"),
    "Financial control": ("Money and access to accounts", "Money"),
    "Isolation": ("Keeping the petitioner from other people", "Isolation"),
    "Threats of harm": ("Threats", "Threat"),
    "Threatened self-harm": ("Threats of self-harm", "Self-harm"),
    "Decisions taken": ("Decisions made for the petitioner", "Control"),
    "Property destroyed": ("Property destroyed", "Property"),
    "Degradation": ("Put-downs", "Put-down"),
    "Reality denial": ("Denying what happened", "Denial"),
}

WEAPON_RE = re.compile(r"\b(gun|guns|firearm|pistol|rifle|shotgun|handgun|knife|weapon|ammo)\b", re.I)

RESOURCES = [
    ("National Domestic Violence Hotline", "1-800-799-7233", "https://www.thehotline.org"),
    ("RAINN (Sexual Assault Hotline)", "1-800-656-4673", "https://www.rainn.org"),
    ("Local legal aid / victim advocate", "find via your county", "https://www.womenslaw.org"),
]

CSS = """
:root{--ink:#3A3434;--muted:#625B5B;--line:#FCD1D1;--blush:#FEF0F0;--btn:#CC5157;--deep:#A8403F;--ok:#2F6B52}
*{box-sizing:border-box}
body{margin:0;background:#EFECE9;color:#222;font-family:"Plus Jakarta Sans",system-ui,-apple-system,sans-serif;line-height:1.55}
.bar{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:12px;padding:13px 22px;background:#fff;border-bottom:1px solid var(--line)}
.bar b{font-size:15px;color:var(--ink);margin-right:auto}
.btn{border:none;border-radius:999px;background:var(--btn);color:#fff;font-size:14px;font-weight:700;padding:11px 20px;cursor:pointer;font-family:inherit;text-decoration:none}
.btn.ghost{background:#fff;color:var(--ink);border:1px solid #F3C2C2}
.hint{font-size:12px;color:var(--muted);padding:10px 22px 0;text-align:center}
.page{width:8.5in;min-height:11in;margin:22px auto;background:#fff;padding:0.7in 0.75in;box-shadow:0 4px 18px rgba(0,0,0,.12);font-family:"Times New Roman",Times,serif;font-size:12pt;color:#111;position:relative}
.formhead{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #111;padding-bottom:6px;margin-bottom:12px}
.formhead .code{font-weight:700;font-size:13pt;letter-spacing:.5px}
.formhead .ttl{font-size:11pt;text-transform:uppercase;letter-spacing:.3px;text-align:right;max-width:3.4in}
.cap{font-family:"Plus Jakarta Sans",sans-serif;font-size:8.5pt;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:#8A8078;margin-bottom:6px}
h1{font-size:19pt;margin:0 0 8px;letter-spacing:-.3px}
h2{font-size:12.5pt;margin:20px 0 8px;border-bottom:1px solid #C9C2BC;padding-bottom:3px}
p{margin:0 0 9px}
.item{display:flex;gap:9px;margin-bottom:12px}
.num{font-weight:700;font-size:11pt;border:1.2px solid #444;width:20px;height:20px;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px}
.itemtitle{font-weight:700;font-size:11.5pt;margin-bottom:5px}
.q{font-size:11pt;margin-bottom:6px;display:flex;align-items:baseline;gap:6px;flex-wrap:wrap}
.fl{flex:1;min-width:90px;border-bottom:1px solid #6E6862;height:14px}
.fl.short{flex:none;width:1.6in}
.ink{border-bottom:1px solid #A89F98;color:#1A3A6B;font-family:"Segoe Script","Bradley Hand",cursive;height:auto;padding:0 3px 1px}
.written{color:#1A3A6B;font-size:11pt;line-height:22px;border-bottom:1px solid #D7D0CA;margin:0}
.chk{display:flex;gap:7px;align-items:flex-start;font-size:10pt;margin-top:9px}
.box{width:12px;height:12px;border:1.2px solid #444;flex-shrink:0;margin-top:3px}
.box.on{background:#1A3A6B;border-color:#1A3A6B;position:relative}
.box.on:after{content:"\\2713";color:#fff;font-size:10px;position:absolute;top:-4px;left:1px}
.src{font-family:"Plus Jakarta Sans",sans-serif;font-size:8.5pt;color:#8A8078;font-weight:700;margin-top:5px}
table{border-collapse:collapse;width:100%;font-size:9.5pt;font-family:"Plus Jakarta Sans",sans-serif}
th,td{border:1px solid #CFC8C2;padding:5px 7px;text-align:left;vertical-align:top}
th{background:#F4F1ED;font-size:8pt;text-transform:uppercase;letter-spacing:.4px;color:#6E6862}
td.d{white-space:nowrap;font-weight:700;color:#333;width:1.15in}
td.k{white-space:nowrap;color:#6E6862;width:1.05in}
td.s{white-space:nowrap;color:#8A8078;width:.95in;font-size:8.5pt}
.gap{background:#FBF4E8}
.blanknote{font-size:10.5pt;color:#444;background:#F7F4F1;border-left:3px solid #C9C2BC;padding:9px 11px;margin-top:10px}
.flag{font-size:10.5pt;color:#7A3F3F;background:#FCF0F0;border-left:3px solid #E2A9A9;padding:9px 11px;margin-top:10px}
.foot{position:absolute;left:.75in;right:.75in;bottom:.45in;display:flex;justify-content:space-between;font-family:"Plus Jakarta Sans",sans-serif;font-size:8pt;color:#8A8078;border-top:1px solid #DDD6D0;padding-top:5px}
.mono{font-family:"SFMono-Regular",Menlo,Consolas,monospace;font-size:8.5pt;color:#444}
.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0 14px;font-family:"Plus Jakarta Sans",sans-serif}
.summary div{background:#F7F4F1;border-radius:8px;padding:9px 11px}
.summary b{display:block;font-size:17pt;line-height:1.2}
.summary span{font-size:8.5pt;color:#6E6862;font-weight:700}
.ok{color:var(--ok);font-weight:700}
.bad{color:#B00020;font-weight:700}
.shot{text-align:center;margin-top:10px}
.shot img{max-width:100%;max-height:7.4in;border:1px solid #CFC8C2}
.shot .mono{margin-top:6px}
@media print{
  body{background:#fff}
  .bar,.hint{display:none}
  .page{width:auto;min-height:0;margin:0;padding:0;box-shadow:none;page-break-after:always}
  .page:last-child{page-break-after:auto}
  .foot{position:fixed;bottom:.3in}
  @page{size:letter;margin:.6in}
}
"""


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt_dt(dt, with_time=True):
    if not dt:
        return "Undated"
    day = f"{dt.day} {dt:%b %Y}"
    if not with_time:
        return day
    return f"{day}, {dt:%I:%M %p}".replace(", 0", ", ")


def msg_when(m):
    """(datetime, display string) for a message, marking approximate times."""
    if m.get("timestamp"):
        dt = parse_ts(m["timestamp"])
        return dt, fmt_dt(dt)
    if m.get("approx_timestamp"):
        dt = parse_ts(m["approx_timestamp"])
        return dt, f"On or before {fmt_dt(dt)}"
    return None, "Undated"


def msg_source(m, letters):
    letter = letters.get(m.get("source_file"))
    where = f"Exhibit {letter}" if letter else esc(m.get("source_file"))
    return f"{where}, msg {m.get('source_index', 0) + 1}"


def written_lines(text, width=80):
    return "".join(f'<p class="written">{esc(line)}</p>' for line in textwrap.wrap(text, width))


def quote(text, limit=220):
    text = " ".join((text or "").split())
    return f"“{text[:limit]}{'…' if len(text) > limit else ''}”"


def image_data_uri(path):
    """Downscaled JPEG data URI, so the packet is one self-contained file."""
    try:
        img = Image.open(path)
        img.thumbnail((1400, 1400))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def page(code, title, body, foot_left):
    head = (f'<div class="formhead"><span class="code">{esc(code)}</span>'
            f'<span class="ttl">{esc(title)}</span></div>') if code else ""
    return {"html": head + body, "foot": foot_left}


def main(samples_dir="./samples"):
    with open("entries.json") as f:
        entries = json.load(f)
    with open("timeline.json") as f:
        tl = json.load(f)

    msgs = [m for m in tl["timeline"] if m.get("sender") != "system"]
    # CDC pattern hits, plus messages the iPhone capture flagged at import (capture/)
    flagged = [m for m in msgs if m.get("flags") or m.get("capture_flag")]
    patterns = tl.get("patterns", [])
    flags = tl.get("flags", [])
    gaps = [f for f in flags if isinstance(f, dict) and f.get("kind") == "gap"]
    letters = {e["source_file"]: chr(ord("A") + i) if i < 26 else f"A{i - 25}"
               for i, e in enumerate(entries)}

    # re-verify every file against the hash recorded at import
    verified = {}
    for e in entries:
        path = os.path.join(samples_dir, e["source_file"])
        if not os.path.exists(path):
            verified[e["source_file"]] = "missing"
        else:
            verified[e["source_file"]] = "match" if sha256(path) == e["file_hash"] else "changed"
    packet_fp = hashlib.sha256("".join(e["file_hash"] for e in entries).encode()).hexdigest()

    times = sorted(dt for dt in (msg_when(m)[0] for m in msgs) if dt)
    span = (f"{fmt_dt(times[0], False)} to {fmt_dt(times[-1], False)}" if times else "Undated")
    months = 0
    if times:
        months = (times[-1].year - times[0].year) * 12 + times[-1].month - times[0].month + 1
    def kinds(m):
        k = [PLAIN.get(f["category"], (None, f["category"]))[1] for f in m.get("flags", [])]
        cf = m.get("capture_flag")
        if cf:
            k.append(f"Flagged at capture: {cf['category']} ({cf['confidence']})")
        return ", ".join(k)
    flagged_by_time = sorted(flagged, key=lambda m: (msg_when(m)[0] is None, msg_when(m)[0] or datetime.min))
    most_recent = [m for m in flagged_by_time if msg_when(m)[0]][::-1]

    pages = []

    # ---------- DV-100 items 1 to 4 ----------
    body = """
  <div class="item"><span class="num">1</span><div style="flex:1">
    <div class="itemtitle">Person asking for protection</div>
    <div class="q">Name: <span class="fl"></span></div>
    <div class="q">Age: <span class="fl short"></span> Address: <span class="fl"></span></div>
    <div class="q">Email: <span class="fl"></span></div>
    <p class="src">Left for the petitioner. No name or address was taken from any file.</p>
  </div></div>
  <div class="item"><span class="num">2</span><div style="flex:1">
    <div class="itemtitle">Person you want protection from</div>
    <div class="q">Name: <span class="fl"></span></div>
    <div class="q">Date of birth: <span class="fl short"></span> Address: <span class="fl"></span></div>
    <p class="src">Not filled. The record identifies this person only as the other side of the conversation.</p>
  </div></div>
  <div class="item"><span class="num">3</span><div style="flex:1">
    <div class="itemtitle">Your relationship to the person in &#9313;</div>
    <div class="chk"><span class="box"></span><span>We live together or used to live together.</span></div>
    <div class="chk"><span class="box"></span><span>We are married or were in a relationship.</span></div>
    <p class="src">Unchecked. The relationship is for the petitioner to state, not to be inferred from messages.</p>
  </div></div>
  <div class="item"><span class="num">4</span><div style="flex:1">
    <div class="itemtitle">Other court cases</div>
    <div class="chk"><span class="box"></span><span>There are other court cases between us.</span></div>
    <p class="written">Nothing in the record can show whether a court case exists, so this box</p>
    <p class="written">is left for the petitioner and the attorney.</p>
  </div></div>"""
    pages.append(page("DV-100", "Request for Domestic Violence Restraining Order", body,
                      "Judicial Council of California, DV-100"))

    # ---------- DV-100 items 5 and 6 ----------
    if most_recent:
        m0 = most_recent[0]
        dt0, when0 = msg_when(m0)
        story = f"{when0}, the other person wrote {quote(m0['text'])}."
        for m in most_recent[1:3]:
            story += f" {msg_when(m)[1]}: {quote(m['text'])}."
        if len(flagged) > 3:
            story += (f" {len(flagged)} flagged messages in total are set out in date order "
                      "in the attachment to this item.")
        item5 = f"""
    <div class="q">a. Date of most recent abuse: <span class="fl short ink">{esc(fmt_dt(dt0, False))}</span></div>
    <div class="q">b. Who was there? <span class="fl"></span></div>
    <p style="font-size:11pt;margin:10px 0 6px">c. What did the person in &#9313; do or say that made you afraid?</p>
    {written_lines(story)}
    <div class="chk"><span class="box on"></span><span>More space is needed. A sheet titled &ldquo;DV-100, Item 5c&rdquo; is attached.</span></div>
    <p class="src">Quoted word for word. Sources: {'; '.join(msg_source(m, letters) for m in most_recent[:3])}</p>"""
        other = most_recent[3:7]
        item6 = (written_lines(" ".join(f"{msg_when(m)[1]}: {quote(m['text'])}." for m in other))
                 + f'<p class="src">Sources: {"; ".join(msg_source(m, letters) for m in other)}</p>'
                 if other else '<div class="blanknote">No other dated, flagged messages.</div>')
    else:
        item5 = ('<div class="blanknote">No message in the record matched a pattern and had a date, '
                 "so this item is left for the petitioner to write.</div>")
        item6 = ""
    body = f"""
  <div class="item"><span class="num">5</span><div style="flex:1">
    <div class="itemtitle">Describe the Most Recent Abuse</div>{item5}
  </div></div>
  <div class="item"><span class="num">6</span><div style="flex:1">
    <div class="itemtitle">Describe Any Other Recent Abuse</div>{item6}
  </div></div>"""
    pages.append(page("DV-100", "Item 5, Describe the Most Recent Abuse", body,
                      "Judicial Council of California, DV-100"))

    # ---------- DV-100 items 7 to 9 ----------
    weapon_hits = [m for m in msgs if WEAPON_RE.search(m.get("text") or "")]
    if weapon_hits:
        weapon_note = (f"Flagged, not answered. {len(weapon_hits)} message(s) mention a weapon: "
                       + "; ".join(f"{msg_source(m, letters)} {esc(quote(m['text'], 80))}" for m in weapon_hits[:3])
                       + ". Raise this first: the surrender deadline runs separately from the hearing.")
    else:
        weapon_note = (f"Flagged, not answered. A word search of {len(msgs)} messages found no mention "
                       "of a weapon, which does not mean there is none. If the petitioner knows of one, "
                       "this is the box to raise first.")
    body = f"""
  <div class="item"><span class="num">7</span><div style="flex:1">
    <div class="itemtitle">Personal conduct orders</div>
    <div class="chk"><span class="box"></span><span>Not to harass, contact, follow, or disturb the peace of the person in &#9312;.</span></div>
    <div class="chk"><span class="box"></span><span>Not to take any action to get the petitioner's address or location.</span></div>
    <div class="flag">Left unchecked. What to ask the judge for is a legal decision, and the record cannot make it.</div>
  </div></div>
  <div class="item"><span class="num">8</span><div style="flex:1">
    <div class="itemtitle">Stay-away order</div>
    <div class="q">Stay at least <span class="fl short"></span> yards away from: <span class="fl"></span></div>
    <div class="blanknote">Distances and addresses are not in the record, and a guess on an order the police enforce is worse than a blank.</div>
  </div></div>
  <div class="item"><span class="num">9</span><div style="flex:1">
    <div class="itemtitle">Guns and other firearms</div>
    <div class="chk"><span class="box"></span><span>The person in &#9313; owns or possesses guns or firearms.</span></div>
    <div class="flag">{weapon_note}</div>
  </div></div>"""
    pages.append(page("DV-100", "Items 7 to 9, Orders Requested", body,
                      "Judicial Council of California, DV-100"))

    # ---------- CLETS-001 ----------
    body = """
  <p style="font-size:11pt">The restrained person's details, entered into the statewide law enforcement system. The other side never sees this sheet.</p>
  <div class="q">Name: <span class="fl"></span></div>
  <div class="q">Date of birth: <span class="fl short"></span> Height: <span class="fl short"></span> Weight: <span class="fl short"></span></div>
  <div class="q">Driver's license number and state: <span class="fl"></span></div>
  <div class="q">Vehicle make, model, year and plate: <span class="fl"></span></div>
  <div class="q">Employer and work address: <span class="fl"></span></div>
  <div class="blanknote">Blank on purpose. None of this is in the files, and a wrong date of birth or plate on a sheet the police act on is worse than an empty line. The petitioner or the attorney fills this by hand.</div>"""
    pages.append(page("CLETS-001", "Confidential CLETS Information", body,
                      "Judicial Council of California, CLETS-001"))

    # ---------- flagged forms ----------
    body = """
  <p style="font-size:11pt">These are in the California packet and none is filled here.</p>
  <h2>DV-109, Notice of Court Hearing</h2>
  <p>The hearing date, department and time come from the clerk when the packet is filed.</p>
  <h2>DV-110, Temporary Restraining Order</h2>
  <p>Nothing filled. What this order should say is a legal decision about risk, not a summary of the messages.</p>
  <h2>DV-105 and DV-140, children</h2>
  <p>Not started. Custody is outside what a message record can establish.</p>
  <div class="flag">Flagged rather than filled, on purpose. The record can tell an attorney what happened and when. It cannot decide what to ask a judge for.</div>"""
    pages.append(page("DV-109 / DV-110", "Notice of Hearing and Temporary Restraining Order",
                      body, "Flagged for counsel"))

    # ---------- attachment: flagged messages in date order, with gaps ----------
    rows = []
    gap_iter = sorted(gaps, key=lambda g: g["start"])
    for m in flagged_by_time:
        dt, when = msg_when(m)
        while gap_iter and dt and parse_ts(gap_iter[0]["end"]) <= dt:
            g = gap_iter.pop(0)
            for_days = f" for {g['days']} days" if g.get("days") else ""
            rows.append(
                f'<tr class="gap"><td class="d">{esc(fmt_dt(parse_ts(g["start"]), False))} to '
                f'{esc(fmt_dt(parse_ts(g["end"]), False))}</td><td class="k">Gap</td>'
                f"<td>No records of any kind{for_days}. Recorded as missing, not as calm.</td>"
                '<td class="s">&mdash;</td></tr>')
        rows.append(f'<tr><td class="d">{esc(when)}</td><td class="k">{esc(kinds(m))}</td>'
                    f'<td>{esc(quote(m["text"]))}</td><td class="s">{msg_source(m, letters)}</td></tr>')
    if not rows:
        rows = ['<tr><td colspan="4">No message matched a pattern.</td></tr>']
    head = "<tr><th>Date and time</th><th>Kind</th><th>What the record shows</th><th>Source</th></tr>"
    chunks = [rows[i:i + ROWS_PER_PAGE] for i in range(0, len(rows), ROWS_PER_PAGE)]
    attach_first = len(pages)
    for i, chunk in enumerate(chunks):
        intro = ('<p style="font-size:10.5pt">Every row is a message from the other person that matched '
                 "one of the patterns measured by the CDC, or was flagged when it was captured from the phone, "
                 "quoted word for word. Times come from the file; "
                 "&ldquo;on or before&rdquo; means the only date is when the screenshot was taken.</p>") if i == 0 else ""
        tail = (f'<p style="font-size:9.5pt;color:#6E6862;margin-top:10px;font-family:\'Plus Jakarta Sans\',sans-serif">'
                f"{len(flagged)} flagged messages. {len(msgs) - len(flagged)} other messages were read and "
                "left out of this list; all of them appear in the exhibits.</p>") if i == len(chunks) - 1 else ""
        pages.append(page("Attachment", "DV-100, Item 5c: incidents in date order" + (", continued" if i else ""),
                          f"{intro}<table>{head}{''.join(chunk)}</table>{tail}", "DV-100, Item 5c"))
    attach_last = len(pages) - 1

    # ---------- exhibit list ----------
    ex_rows = []
    for e in entries:
        fname = e["source_file"]
        emsgs = [m for m in msgs if m.get("source_file") == fname]
        what = {"screenshot": f"Screenshot, {len(emsgs)} messages",
                "iphone_capture": f"iPhone capture (read from the phone over USB), {len(emsgs)} messages",
                "whatsapp_export": f"WhatsApp export, {len(emsgs)} messages",
                "photo": "Photograph"}.get(e["source_type"], e["source_type"])
        if e.get("parse_error"):
            what += " (could not be read automatically, check by hand)"
        if e.get("exif_timestamp"):
            dated = f"Taken {fmt_dt(parse_ts(e['exif_timestamp']))}"
        else:
            ts = sorted(dt for dt in (parse_ts(m.get("timestamp")) for m in emsgs) if dt)
            dated = (f"{fmt_dt(ts[0], False)} to {fmt_dt(ts[-1], False)}" if len(ts) > 1
                     else fmt_dt(ts[0]) if ts else "No date in the file")
        status = verified[fname]
        badge = {"match": '<span class="ok">unchanged</span>',
                 "changed": '<span class="bad">CHANGED since import</span>',
                 "missing": '<span class="bad">file not found</span>'}[status]
        ex_rows.append(f'<tr><td class="d">{letters[fname]}</td><td>{esc(what)}<br>'
                       f'<span class="mono">{esc(fname)}</span></td><td>{esc(dated)}</td>'
                       f'<td class="mono">{esc(e["file_hash"][:16])}&hellip;<br>{badge}</td></tr>')
    changed = [f for f, s in verified.items() if s != "match"]
    check_note = (f'<div class="flag">{len(changed)} file(s) no longer match the fingerprint taken at import: '
                  f'{esc(", ".join(changed))}. Do not rely on them until the difference is explained.</div>'
                  if changed else
                  '<div class="blanknote">Every file was fingerprinted when it was imported and checked again '
                  "when this packet was built. All match.</div>")
    body = (f'<p style="font-size:10.5pt">Each file was fingerprinted (SHA-256) when it came off the phone. '
            f"A changed file produces a different fingerprint.</p><table><tr><th>Ex.</th><th>What it is</th>"
            f"<th>Taken or dated</th><th>sha256</th></tr>{''.join(ex_rows)}</table>{check_note}")
    exhibit_list = len(pages)
    pages.append(page("Exhibits", f"Exhibit list A to {letters[entries[-1]['source_file']] if entries else 'A'} with file fingerprints",
                      body, "Exhibit list"))

    # ---------- exhibits: the original images ----------
    exhibit_first = len(pages)
    for e in entries:
        if e["source_type"] not in ("screenshot", "photo", "iphone_capture"):
            continue
        fname = e["source_file"]
        uri = image_data_uri(os.path.join(samples_dir, fname))
        img = (f'<img src="{uri}" alt="Exhibit {letters[fname]}">' if uri
               else '<div class="flag">The original file could not be opened for this page.</div>')
        body = (f'<div class="shot">{img}<div class="mono">{esc(fname)} &middot; sha256 {esc(e["file_hash"])}</div></div>')
        pages.append(page(f"Exhibit {letters[fname]}", "Original file, the evidence itself", body,
                          f"Exhibit {letters[fname]}"))
    exhibit_last = len(pages) - 1

    # ---------- review flags and incident summaries ----------
    flag_items = "".join(f"<li>{esc(f['text'] if isinstance(f, dict) else f)}</li>" for f in flags)
    inc_items = []
    for i, inc in enumerate(tl.get("incidents", []), 1):
        if inc.get("start"):
            s, e_ = parse_ts(inc["start"]), parse_ts(inc["end"])
            when = f"{fmt_dt(s)} to {fmt_dt(e_)}" + (", approximate" if inc.get("approximate") else "")
        else:
            when = "undated"
        inc_items.append(f'<tr><td class="d">{i}</td><td>{esc(when)}<br><span class="src">'
                         f'{inc["message_count"]} messages</span></td><td>{esc(inc["summary"])}</td></tr>')
    flag_block = (f'<ul style="font-size:10.5pt">{flag_items}</ul>' if flag_items
                  else "<p>No review flags.</p>")
    body = (f"<h2>Check before relying on this packet</h2>{flag_block}"
            f"<h2>Incident summaries</h2><p style=\"font-size:10.5pt\">Written by Gemini from the messages in each "
            f"incident, told to be neutral and add nothing. The quotes in the attachment are the record; these are an index.</p>"
            f"<table><tr><th>#</th><th>When</th><th>Summary</th></tr>{''.join(inc_items)}</table>")
    review = len(pages)
    pages.append(page("Review", "Flags and incident summaries", body, "For counsel"))

    # ---------- method ----------
    res = "".join(f"<tr><td>{esc(n)}</td><td>{esc(p)}</td><td>{esc(u)}</td></tr>" for n, p, u in RESOURCES)
    body = f"""
  <h2>Where it ran</h2>
  <p>The scripts ran on the petitioner's own computer. To read the text in screenshots, each image was sent to Google's Gemini API. WhatsApp exports were read locally and not sent anywhere.</p>
  <h2>What Gemini did</h2>
  <p>Two jobs. It read the words and times off each screenshot, with a confidence score for each message, and it wrote the neutral incident summaries on the review page.</p>
  <h2>What did not use AI</h2>
  <p>The patterns. Each message from the other person was checked against fixed word patterns for the kinds of behavior measured in {esc(tl.get("prevalence_source") or "the CDC's National Intimate Partner and Sexual Violence Survey")}. A match shows the message and the words that matched. It is not a judgment about what the message means.</p>
  <h2>What it did not do</h2>
  <p>It did not write a sentence anyone did not say, score risk, or reach a conclusion. It did not fill in names, addresses or the orders to request. It did not treat a gap in the record as a calm period.</p>
  <h2>What a person still has to do</h2>
  <p>Read it, correct anything that is not how the petitioner would say it, decide what to ask the judge for, and sign it.</p>
  <h2>Help</h2>
  <table><tr><th>Who</th><th>Phone</th><th>Web</th></tr>{res}</table>
  <div class="blanknote">HerProof is not a law firm and does not give legal advice. Nothing in this packet has been filed or sent.</div>"""
    pages.append(page("Method", "How this record was built", body, f"Packet fingerprint sha256 {packet_fp[:8]}…"))
    method = len(pages) - 1

    # ---------- cover (built last, needs page numbers) ----------
    def pg(a, b=None):
        a, b = a + 2, (b if b is not None else a) + 2  # +1 for 1-based, +1 for the cover
        return str(a) if a == b else f"{a} to {b}"

    contents = [
        (pg(0, 2), "DV-100, Request for Domestic Violence Restraining Order", "Item 5 filled from the record"),
        (pg(3), "CLETS-001, Confidential CLETS Information", "Left blank on purpose"),
        (pg(4), "DV-109, DV-110, DV-105", "Flagged for the attorney"),
        (pg(attach_first, attach_last), "Attachment to DV-100, item 5c: flagged messages in date order", "Complete"),
        (pg(exhibit_list), "Exhibit list with file fingerprints", "Checked again today" if not changed else "Mismatch, see page"),
    ]
    if exhibit_last >= exhibit_first:
        contents.append((pg(exhibit_first, exhibit_last), "The original screenshots and photos", "Embedded"))
    contents += [(pg(review), "Review flags and incident summaries", f"{len(flags)} flags"),
                 (pg(method), "How the record was built", "Complete")]
    toc = "".join(f'<tr><td class="d">{p}</td><td>{esc(d)}</td><td>{esc(s)}</td></tr>' for p, d, s in contents)

    glance = []
    for p in patterns:
        label = PLAIN.get(p["category"], (p["category"], ""))[0]
        prev = esc(p["prevalence"]) if p.get("measured") else "Not measured"
        first = fmt_dt(parse_ts(p["first"]), False) if p.get("first") else "Undated"
        last = fmt_dt(parse_ts(p["last"]), False) if p.get("last") else "Undated"
        glance.append(f"<tr><td>{esc(label)}</td><td>{p['count']}</td><td>{esc(first)}</td>"
                      f"<td>{esc(last)}</td><td>{prev}</td></tr>")
    for g in gaps:
        n_days = f", {g['days']} days" if g.get("days") else ""
        glance.append(f'<tr class="gap"><td colspan="5">No records at all between '
                      f'{esc(fmt_dt(parse_ts(g["start"]), False))} and {esc(fmt_dt(parse_ts(g["end"]), False))}'
                      f"{n_days}. Shown as missing, not as calm.</td></tr>")
    if not glance:
        glance = ['<tr><td colspan="5">No message matched a pattern.</td></tr>']
    caveats = "".join(f'<p class="src">{esc(p["category"])}: {esc(p["caveat"])}</p>' for p in patterns if p.get("caveat"))

    cover = f"""
  <div class="cap">Prepared for your attorney</div>
  <h1>Domestic violence restraining order packet</h1>
  <p style="font-size:11pt;color:#555">Built from the petitioner's own files. Every quoted line traces to a file with a fingerprint, and nothing here was written by anyone who was not in the record.</p>
  <div class="summary">
    <div><b>{len(flagged)}</b><span>flagged messages</span></div>
    <div><b>{months if times else "&mdash;"}</b><span>{"month" if months == 1 else "months"} covered</span></div>
    <div><b>{len(msgs):,}</b><span>messages read</span></div>
  </div>
  <p class="src">{esc(span)} &middot; {len(entries)} files</p>
  <h2>What is in this packet</h2>
  <table><tr><th>Page</th><th>Document</th><th>State</th></tr>{toc}</table>
  <h2>The record at a glance</h2>
  <table><tr><th>What repeats</th><th>Times</th><th>First</th><th>Most recent</th><th>Women reporting it (CDC)</th></tr>{''.join(glance)}</table>
  <p class="src">Prevalence: {esc(tl.get("prevalence_source") or "")}</p>{caveats}
  <div class="blanknote">This packet is not legal advice and no document in it has been filed. Which forms this case needs, and what to ask the judge for, is the attorney's call.</div>"""
    pages.insert(0, page(None, None, cover, f"Packet fingerprint sha256 {packet_fp[:8]}…"))

    total = len(pages)
    body_html = "\n".join(
        f'<div class="page">{p["html"]}<div class="foot"><span>{esc(p["foot"])}</span>'
        f"<span>Page {i} of {total}</span></div></div>"
        for i, p in enumerate(pages, 1))

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Attorney packet, ready to download</title>
<style>{CSS}</style>
</head>
<body>
<div class="bar">
  <b>Attorney packet, {total} pages</b>
  <button class="btn" onclick="window.print()">Download as PDF</button>
  <a class="btn ghost" href="{APP_LINK}">Back to the app</a>
</div>
<p class="hint">Print dialog opens. Choose Save as PDF, letter size, and it saves the whole packet: the DV-100 pages, the confidential sheet, the flagged forms, {len(flagged)} flagged messages in date order and the exhibits.</p>
{body_html}
</body>
</html>"""

    with open("packet.html", "w") as f:
        f.write(doc)
    print(f"Wrote packet.html — {total} pages. Open it and press Download as PDF")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "./samples")
