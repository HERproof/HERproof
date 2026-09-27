"""Model-driven mode: the LLM drives the phone through the tools in tools.py.

    python -m herproof.agent --chat "Team 2"                       # provider from .env / auto
    python -m herproof.agent --chat "Team 2" --provider gemini
    python -m herproof.agent --goal "Open Instagram, go to DMs, ..." --provider claude
    python -m herproof.agent --chat "Team 2" --provider scripted   # no API key: replays the fixed procedure (plumbing test)

This is the same thing Claude Code does when it drives the phone through the
iphone-use MCP server, without Claude Code: any model with function calling
gets the same tools. For the fixed "walk one iMessage chat" job the
deterministic `herproof.extract` is cheaper and more predictable; use this
mode for other apps or open-ended instructions.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from typing import Any

from .extract import _load_dotenv
from .llm import DEFAULT_MODELS, LLMError, resolve_provider
from .phone import Phone, PhoneError
from .tools import TOOLS, Executor, ToolResult, png_b64

SYSTEM = """You are operating a real iPhone over USB on behalf of its owner, who is documenting
abusive or bullying messages sent to them. You see the phone only through the tools.

Rules:
- Read-only. Never type, send, react, forward, delete, or open links or attachments. Never open a
  conversation other than the one you were asked to review.
- Start with phone_status, then read_screen. Prefer read_screen over screenshots to decide what to
  do; take a screenshot when you need to confirm or to save evidence.
- iOS Messages: after launch_app the app may reopen inside the last conversation; use back until the
  conversation list is showing, then tap the requested conversation by its element index. If the
  first tap only collapses the large title, read_screen again and tap again. Verify the
  conversation_title before doing anything else.
- Walk the conversation from newest to oldest: on each screen call read_screen, then
  screenshot_with_times (falls back to screenshot), then scroll dy=-70. Stop when read_screen
  reports at_top_of_conversation, when a date separator earlier than today appears (unless told to
  cover all days), or when scrolling stops producing new bubbles.
- Flag with flag_message every message from someone other than the owner ("Your iMessage" / "me")
  that insults, threatens, humiliates, excludes, pressures, or controls the owner, judged in context.
  Quote the text exactly as read_screen shows it. When unsure, flag with confidence "low".
  Work links, file names, emails and logistics are not abuse.
- When done, go home, take a final screenshot, and call finish once."""


def goal_for(chat: str | None, goal: str | None, all_days: bool) -> str:
    if goal:
        return goal
    days = "Cover every day in the conversation." if all_days else "Only today's messages matter; stop at the first earlier-day separator."
    return (f"Open Messages, open the conversation titled exactly {chat!r}, review it from newest to oldest, "
            f"flag every abusive or bullying message with flag_message, then finish. {days}")


# ---- providers ---------------------------------------------------------------
def run_claude(exe: Executor, goal: str, model: str, max_steps: int, log) -> None:
    import anthropic

    client = anthropic.Anthropic()
    tools = [{"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]} for t in TOOLS]
    messages: list[dict[str, Any]] = [{"role": "user", "content": goal}]
    for step in range(max_steps):
        resp = client.beta.messages.create(
            model=model, max_tokens=8000, system=SYSTEM, tools=tools,
            thinking={"type": "adaptive"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            messages=messages,
        )
        if resp.stop_reason == "refusal":
            raise LLMError(f"Claude declined: {getattr(resp, 'stop_details', None)}")
        messages.append({"role": "assistant", "content": resp.content})
        calls = [b for b in resp.content if b.type == "tool_use"]
        for b in resp.content:
            if b.type == "text" and b.text.strip():
                log(f"[claude] {b.text.strip()[:300]}")
        if not calls:
            if exe.finished:
                return
            messages.append({"role": "user", "content": "Continue with the tools; call finish when done."})
            continue
        results = []
        for c in calls:
            r = exe.run(c.name, dict(c.input))
            log(f"[tool] {c.name}({json.dumps(c.input)[:120]}) -> {r.text()[:200]}")
            content: list[dict[str, Any]] = [{"type": "text", "text": r.text()}]
            if r.image_png:
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png_b64(r.image_png)}})
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": content})
        messages.append({"role": "user", "content": results})
        if exe.finished:
            return
    raise LLMError(f"stopped after {max_steps} steps without finish")


def run_gemini(exe: Executor, goal: str, model: str, max_steps: int, log) -> None:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    decls = [types.FunctionDeclaration(name=t["name"], description=t["description"], parameters=_gemini_params(t["input_schema"]))
             for t in TOOLS]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        tools=[types.Tool(function_declarations=decls)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.2,
    )
    history: list[types.Content] = [types.Content(role="user", parts=[types.Part.from_text(text=goal)])]
    for step in range(max_steps):
        resp = client.models.generate_content(model=model, contents=history, config=config)
        cand = resp.candidates[0] if resp.candidates else None
        if cand is None or cand.content is None:
            raise LLMError(f"Gemini returned no candidate (prompt_feedback={getattr(resp, 'prompt_feedback', None)})")
        history.append(cand.content)
        calls = [p.function_call for p in (cand.content.parts or []) if getattr(p, "function_call", None)]
        for p in cand.content.parts or []:
            if getattr(p, "text", None) and p.text.strip():
                log(f"[gemini] {p.text.strip()[:300]}")
        if not calls:
            if exe.finished:
                return
            history.append(types.Content(role="user", parts=[types.Part.from_text(text="Continue with the tools; call finish when done.")]))
            continue
        parts: list[types.Part] = []
        for fc in calls:
            args = dict(fc.args or {})
            r = exe.run(fc.name, args)
            log(f"[tool] {fc.name}({json.dumps(args)[:120]}) -> {r.text()[:200]}")
            parts.append(types.Part.from_function_response(name=fc.name, response={"result": r.data}))
            if r.image_png:
                parts.append(types.Part.from_bytes(data=r.image_png, mime_type="image/png"))
        history.append(types.Content(role="user", parts=parts))
        if exe.finished:
            return
    raise LLMError(f"stopped after {max_steps} steps without finish")


def _gemini_params(schema: dict[str, Any]) -> dict[str, Any] | None:
    if not schema.get("properties"):
        return None
    s = json.loads(json.dumps(schema))
    s.pop("additionalProperties", None)
    return s


def run_scripted(exe: Executor, chat: str, max_steps: int, log) -> None:
    """A stand-in 'model' that replays the fixed iMessage procedure through the
    same tools. Proves the tool plumbing on a real phone without an API key."""
    def call(name, **args):
        r = exe.run(name, args)
        log(f"[tool] {name}({json.dumps(args)[:120]}) -> {r.text()[:200]}")
        return r.data

    st = call("phone_status")
    if not st.get("drivable"):
        raise PhoneError(f"not drivable: {st}")
    call("home"); call("launch_app", bundle="com.apple.MobileSMS")
    scr = call("read_screen")
    for _ in range(4):
        if not scr.get("conversation_title"):
            break
        call("back"); scr = call("read_screen")
    call("screenshot", name="conversation_list")
    want = chat.strip().lower()
    for _ in range(4):
        if scr.get("conversation_title", "").strip().lower() == want:
            break
        if scr.get("conversation_title"):
            call("back"); scr = call("read_screen"); continue
        idx = next((int(r.split("]")[0][1:]) for r in scr["elements"]
                    if r.split(" ", 1)[1].startswith("Cell") and f"'{chat}," in r), None)
        if idx is None:
            raise PhoneError(f"{chat!r} not in list")
        call("tap_element", index=idx); scr = call("read_screen")
    if scr.get("conversation_title", "").strip().lower() != want:
        raise PhoneError("conversation did not open")
    seen: set[str] = set()
    for i in range(max_steps):
        bubbles = [r for r in scr["elements"] if "Cell" in r and (" AM'" in r or " PM'" in r)]
        new = [b for b in bubbles if b not in seen]
        seen.update(bubbles)
        shot = call("screenshot_with_times", name=f"screen{i + 1}_times")
        if "error" in shot:
            shot = call("screenshot", name=f"screen{i + 1}")
        for b in new:
            if any(k in b.lower() for k in ("useless", "even work", "taking the kids", "so dramatic", "more useful than you", "sleep like a cat")):
                lbl = b.split("'", 1)[1].rsplit("'", 1)[0]
                sender, rest = lbl.split(", ", 1); text, t = rest.rsplit(", ", 1)
                call("flag_message", sender=sender, text=text, time=t, category="insult", confidence="medium",
                     why="scripted keyword match", screenshot=shot.get("saved", ""))
        older = [s for s in scr.get("date_separators", []) if not s.startswith("Today")]
        if scr.get("at_top_of_conversation") or older or (i > 0 and not new):
            break
        call("scroll", dy=-70); scr = call("read_screen")
    call("home"); call("screenshot", name="home_final")
    call("finish", summary=f"scripted walk of {chat!r}", messages_reviewed=len(seen))


# ---- main ------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chat", help='conversation title, e.g. "Team 2"')
    ap.add_argument("--goal", help="free-form instruction instead of --chat (any app)")
    ap.add_argument("--provider", default=None, choices=["auto", "claude", "gemini", "scripted"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", default="evidence")
    ap.add_argument("--max-steps", type=int, default=60)
    ap.add_argument("--all-days", action="store_true")
    args = ap.parse_args(argv)
    if not args.chat and not args.goal:
        ap.error("give --chat or --goal")

    _load_dotenv()
    provider = args.provider or os.environ.get("HERPROOF_PROVIDER") or "auto"
    if provider != "scripted":
        provider = resolve_provider(provider)
    model = args.model or DEFAULT_MODELS.get(provider, "")
    today = dt.date.today().isoformat()
    log = lambda s: print(s, flush=True)  # noqa: E731

    phone = Phone()
    phone.require_drivable()
    exe = Executor(phone=phone, out_dir=args.out)
    goal = goal_for(args.chat, args.goal, args.all_days)
    log(f"[agent] provider={provider} model={model or '-'}")
    t0 = time.time()
    try:
        if provider == "claude":
            run_claude(exe, goal, model, args.max_steps, log)
        elif provider == "gemini":
            run_gemini(exe, goal, model, args.max_steps, log)
        else:
            run_scripted(exe, args.chat or "", args.max_steps, log)
    finally:
        slug = "".join(c if c.isalnum() else "_" for c in (args.chat or "agent"))[:40].lower()
        d = os.path.join(args.out, slug); os.makedirs(d, exist_ok=True)
        out = {
            "mode": "agent", "provider": provider, "model": model, "goal": goal, "date": today,
            "extracted_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "duration_s": round(time.time() - t0, 1),
            "finished": exe.finished, "flagged_count": len(exe.flagged), "flagged": exe.flagged,
            "screenshots": exe.shots,
        }
        p = os.path.join(d, f"{slug}_{today}_agent.json")
        json.dump(out, open(p, "w"), indent=2, ensure_ascii=False)
        log(f"[done] {p}  ({len(exe.flagged)} flagged, {len(exe.shots)} screenshots, finished={bool(exe.finished)})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (PhoneError, LLMError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
