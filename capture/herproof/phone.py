"""Thin client for the iphone-use daemon's HTTP agent API.

Everything the extractor needs from the phone goes through here:
status, the accessibility tree, taps, scrolls, screenshots, and the
timestamp-reveal capture (a slow drag left while grabbing frames from the
daemon's MJPEG stream, because the daemon queues normal screenshots behind
gestures and a plain screenshot never catches the reveal).
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Any

import requests


class PhoneError(RuntimeError):
    pass


@dataclass
class Element:
    kind: str
    label: str
    rect: tuple[float, float, float, float]  # x, y, w, h in points
    depth: int
    identifier: str = ""
    value: str = ""
    accessible: bool = False
    visible: bool = True

    @classmethod
    def from_json(cls, e: dict[str, Any]) -> "Element":
        r = e.get("rect") or [0, 0, 0, 0]
        return cls(
            kind=e.get("kind", ""),
            label=e.get("label", "") or "",
            rect=(float(r[0]), float(r[1]), float(r[2]), float(r[3])),
            depth=int(e.get("depth", 0)),
            identifier=e.get("identifier", "") or "",
            value=str(e.get("value", "") or ""),
            accessible=bool(e.get("accessible", False)),
            visible=e.get("visible", True) is not False,
        )


@dataclass
class Screen:
    snapshot: str
    width: float
    height: float
    elements: list[Element]


class Phone:
    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        owner: str | None = None,
        mjpeg_url: str | None = None,
    ):
        self.url = (url or os.environ.get("PHONE_REMOTE_URL", "http://127.0.0.1:44321")).rstrip("/")
        self.token = token or os.environ.get("PHONE_REMOTE_TOKEN", "")
        if not self.token:
            raise PhoneError("PHONE_REMOTE_TOKEN is not set (see .env.example)")
        self.owner = owner or os.environ.get("PHONE_REMOTE_OWNER", "herproof")
        self.mjpeg_url = mjpeg_url or os.environ.get("PHONE_REMOTE_WDA_MJPEG_URL", "http://127.0.0.1:9100")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {self.token}", "X-Phone-Owner": self.owner})

    # ---- read -------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        r = self.s.get(f"{self.url}/agent/status", timeout=15)
        r.raise_for_status()
        return r.json()

    def require_drivable(self) -> dict[str, Any]:
        st = self.status()
        if not st.get("drivable"):
            raise PhoneError(
                "phone is not drivable: device_state=%s hint=%s setup_blocked_on=%s"
                % (st.get("device_state"), st.get("hint"), st.get("setup_blocked_on"))
            )
        if st.get("owner") and st["owner"] != self.owner:
            raise PhoneError(f"another session ({st['owner']}) is driving the phone; close it first")
        return st

    def elements(self) -> Screen:
        # the daemon may take up to ~35s rebuilding a failed read; give it room
        r = self.s.get(f"{self.url}/agent/elements", timeout=45)
        r.raise_for_status()
        j = r.json()
        scr = j.get("screen") or {}
        return Screen(
            snapshot=j.get("snapshot", ""),
            width=float(scr.get("width", 402)),
            height=float(scr.get("height", 874)),
            elements=[Element.from_json(e) for e in j.get("elements", [])],
        )

    def screenshot(self, path: str) -> str:
        r = self.s.get(f"{self.url}/agent/screenshot", timeout=30)
        r.raise_for_status()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(r.content)
        return path

    # ---- act --------------------------------------------------------------
    def _input(self, body: dict[str, Any]) -> dict[str, Any]:
        r = self.s.post(
            f"{self.url}/agent/input",
            json=body,
            headers={"X-Phone-Control": "1"},
            timeout=30,
        )
        try:
            j = r.json()
        except ValueError:
            raise PhoneError(f"/agent/input returned non-JSON ({r.status_code})")
        if not j.get("ok"):
            raise PhoneError(f"action {body.get('type')} refused: {j}")
        return j

    def tap(self, x: float, y: float) -> None:
        self._input({"type": "tap", "x": x, "y": y})

    def tap_point(self, px: float, py: float, screen: Screen) -> None:
        self.tap(px / screen.width, py / screen.height)

    def scroll(self, dy: float, x: float = 0.5, y: float = 0.5) -> None:
        self._input({"type": "scroll", "x": x, "y": y, "dx": 0, "dy": dy})

    def home(self) -> None:
        self._input({"type": "shortcut", "name": "home"})

    def launch_app(self, bundle: str) -> None:
        self._input({"type": "launch_app", "bundle": bundle})

    def drag(self, x1: float, y1: float, x2: float, y2: float, duration_ms: int = 2500, hold_ms: int = 150) -> None:
        self._input({"type": "drag", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "hold_ms": hold_ms, "duration_ms": duration_ms})

    # ---- timestamp reveal -------------------------------------------------
    def capture_times(self, out_png: str, seconds: float = 5.0, fps: int = 8) -> str | None:
        """Drag the Messages transcript left (reveals per-message times) while
        recording the MJPEG stream; keep the frame that differs most from the
        resting screen. Returns the PNG path, or None if ffmpeg/PIL are missing
        or nothing was revealed."""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return None
        try:
            from PIL import Image, ImageChops, ImageStat  # noqa: F401
        except ImportError:
            return None
        tmp = tempfile.mkdtemp(prefix="herproof-frames-")
        proc = subprocess.Popen(
            [ffmpeg, "-loglevel", "error", "-y", "-f", "mjpeg", "-i", self.mjpeg_url,
             "-t", str(seconds), "-vf", f"fps={fps}", "-q:v", "2", os.path.join(tmp, "f_%03d.jpg")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)
        try:
            self.drag(0.85, 0.5, 0.35, 0.5)
        finally:
            proc.wait(timeout=seconds + 10)
        frames = sorted(glob.glob(os.path.join(tmp, "f_*.jpg")))
        if len(frames) < 2:
            shutil.rmtree(tmp, ignore_errors=True)
            return None
        best = _most_different_frame(frames)
        if best is None:
            shutil.rmtree(tmp, ignore_errors=True)
            return None
        from PIL import Image
        os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
        Image.open(best).save(out_png)
        shutil.rmtree(tmp, ignore_errors=True)
        return out_png


def _most_different_frame(frames: list[str]) -> str | None:
    from PIL import Image, ImageChops, ImageStat
    base = Image.open(frames[0]).convert("L")
    best, score = None, 0.0
    for f in frames[1:]:
        d = ImageStat.Stat(ImageChops.difference(base, Image.open(f).convert("L"))).mean[0]
        if d > score:
            best, score = f, d
    # below ~1.0 mean grey difference the screen did not change at all
    return best if score >= 1.0 else None
