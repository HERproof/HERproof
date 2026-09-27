"""HerProof demo server: static site + a capture API, standard library only.

    cd <repo root>
    capture/.venv/bin/python capture/server.py          # http://localhost:8000

Serves the repo like `python -m http.server`, plus:

  GET  /api/phone                 -> {"usb": bool, "drivable": bool, ...}  (cable seen by libimobiledevice; drivable per the daemon)
  GET  /api/runs                  -> [{"run": "alex", "chat": "Alex", ...}, ...]
  POST /api/capture  {"chat": "Alex"}
        Runs, in a background thread: herproof.extract --chat <chat> --out capture/evidence/<slug>
        then organize.py and export_packet.py at the repo root. Progress is readable at
        GET /api/status. If the phone is not drivable and a saved run for that chat exists,
        the response is {"cached": true, "run": "<slug>"} and nothing runs.
  GET  /api/status                -> {"state": "idle|running|done|error", "phase": "...", "run": "...", "log": [...]}

Everything stays on this machine: the daemon is on localhost, and the only
outbound call is organize.py's Gemini summary (GEMINI_API_KEY in .env).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CAPTURE = os.path.join(ROOT, "capture")
EVIDENCE = os.path.join(CAPTURE, "evidence")
PY = os.path.join(CAPTURE, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable

STATUS: dict = {"state": "idle", "phase": "", "run": None, "chat": None, "log": [], "started": None, "finished": None}
LOCK = threading.Lock()


def _env() -> dict:
    env = dict(os.environ)
    for p in (os.path.join(ROOT, ".env"), os.path.join(CAPTURE, ".env")):
        if os.path.exists(p):
            for line in open(p):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env.setdefault(k.strip(), v.strip())
    return env


def slug(chat: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in chat.strip())[:40].lower()


def usb_present() -> bool:
    """True when libimobiledevice sees an iPhone on the cable (even if locked)."""
    try:
        out = subprocess.run(["idevice_id", "-l"], capture_output=True, text=True, timeout=4).stdout
        return any(line.strip() for line in out.splitlines())
    except Exception:
        return False


def phone_status() -> dict:
    env = _env()
    url = env.get("PHONE_REMOTE_URL", "http://127.0.0.1:44321").rstrip("/") + "/agent/status"
    try:
        req = Request(url, headers={"Authorization": "Bearer " + env.get("PHONE_REMOTE_TOKEN", "")})
        with urlopen(req, timeout=4) as r:
            d = json.load(r)
        return {"drivable": bool(d.get("drivable")), "usb": usb_present(), "device_state": d.get("device_state"), "hint": d.get("hint", ""), "owner": d.get("owner")}
    except Exception as e:  # daemon down, no token, etc.
        return {"drivable": False, "usb": usb_present(), "device_state": "offline", "hint": f"daemon unreachable: {e}"}


def list_runs() -> list[dict]:
    out = []
    if not os.path.isdir(EVIDENCE):
        return out
    for run in sorted(os.listdir(EVIDENCE)):
        d = os.path.join(EVIDENCE, run)
        tags = os.path.join(d, "capture-tags.json")
        if os.path.isfile(tags):
            try:
                t = json.load(open(tags))
                out.append({"run": run, "chat": t.get("chat"), "date": t.get("date"), "flagged": len(t.get("tags", [])),
                            "screens": len([f for f in os.listdir(os.path.join(d, "screens")) if f.endswith(".png")]) if os.path.isdir(os.path.join(d, "screens")) else 0})
            except Exception:
                pass
    return out


def find_cached(chat: str) -> str | None:
    want = chat.strip().lower()
    runs = list_runs()
    for r in runs:  # exact chat name first
        if (r["chat"] or "").strip().lower() == want:
            return r["run"]
    s = slug(chat)
    for r in runs:
        if r["run"] == s:
            return r["run"]
    return None


def _set(**kw) -> None:
    with LOCK:
        STATUS.update(kw)


def _log(line: str) -> None:
    with LOCK:
        STATUS["log"].append(line)
        STATUS["log"] = STATUS["log"][-60:]
    print(line, flush=True)


def _run(cmd: list[str], cwd: str, phase: str) -> int:
    _set(phase=phase)
    _log(f"$ {' '.join(cmd)}")
    p = subprocess.Popen(cmd, cwd=cwd, env=_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in p.stdout:  # type: ignore[union-attr]
        line = line.rstrip()
        if line:
            _log(line)
            m = re.match(r"\[walk\] screen (\d+)", line)
            if m:
                _set(phase=f"Saving screen {m.group(1)} with its times")
    return p.wait()


def capture_job(chat: str) -> None:
    run = slug(chat)
    out = os.path.join("evidence", run)
    _set(state="running", run=run, chat=chat, log=[], started=time.time(), finished=None, phase="Opening Messages")
    try:
        rc = _run([PY, "-m", "herproof.extract", "--chat", chat, "--out", out], CAPTURE, "Opening Messages")
        if rc != 0:
            raise RuntimeError(f"capture failed (exit {rc})")
        _set(phase="Fingerprinting what came across")
        entries = os.path.join(EVIDENCE, run, "entries.json")
        import shutil
        shutil.copyfile(entries, os.path.join(ROOT, "entries.json"))
        rc = _run([PY, "organize.py"], ROOT, "Gemini grouping what repeats")
        if rc != 0:
            raise RuntimeError(f"organize.py failed (exit {rc})")
        rc = _run([PY, "export_packet.py", os.path.join("capture", out, "screens")], ROOT, "Drafting the packet")
        if rc != 0:
            raise RuntimeError(f"export_packet.py failed (exit {rc})")
        _set(state="done", phase="Encrypted into your vault", finished=time.time())
    except Exception as e:
        _log(f"error: {e}")
        cached = find_cached(chat)
        _set(state="error", phase=str(e), finished=time.time(), cached=cached)


class Handler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"   # keep-alive + byte ranges: what <video> needs

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    # Range requests, so <video> can seek and Chrome plays .mp4 files reliably.
    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path):
            return super().send_head()
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        size = os.path.getsize(path)
        if not m:
            return super().send_head()
        start = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2) or 0))
        end = int(m.group(2)) if m.group(2) and m.group(1) else size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._range_len = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        n = getattr(self, "_range_len", None)
        if n is None:
            return super().copyfile(source, outputfile)
        self._range_len = None
        while n > 0:
            chunk = source.read(min(65536, n))
            if not chunk:
                break
            outputfile.write(chunk)
            n -= len(chunk)

    def log_message(self, fmt, *args):  # quieter static log (set HERPROOF_LOG=1 for everything)
        first = str(args[0]) if args else ""
        if os.environ.get("HERPROOF_LOG") or "/api/" in first or fmt.startswith("code"):
            super().log_message(fmt, *args)

    def _json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        if self.path.startswith("/capture/evidence/") or self.path.endswith((".json", ".txt", ".html")):
            self.send_header("Cache-Control", "no-store")
        if self.path.endswith((".mp4", ".mov", ".m4v", ".webm")) and not getattr(self, "_range_len", None):
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_GET(self) -> None:
        if self.path.startswith("/api/phone"):
            return self._json(phone_status())
        if self.path.startswith("/api/runs"):
            return self._json(list_runs())
        if self.path.startswith("/api/status"):
            with LOCK:
                return self._json(dict(STATUS))
        return super().do_GET()

    def do_POST(self) -> None:
        if not self.path.startswith("/api/capture"):
            return self._json({"error": "not found"}, 404)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json({"error": "bad json"}, 400)
        chat = (body.get("chat") or "").strip()
        if not chat:
            return self._json({"error": "chat is required"}, 400)
        with LOCK:
            running = STATUS["state"] == "running"
        if running:
            return self._json({"error": "a capture is already running"}, 409)
        cached = find_cached(chat)
        ph = phone_status()
        if not ph["drivable"] or body.get("prefer_cached"):
            if cached:
                return self._json({"cached": True, "run": cached, "phone": ph})
            return self._json({"error": "phone not drivable and no saved run for this chat", "phone": ph}, 503)
        threading.Thread(target=capture_job, args=(chat,), daemon=True).start()
        return self._json({"started": True, "run": slug(chat), "phone": ph})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"HerProof demo server on http://localhost:{port}  (root: {ROOT})")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
