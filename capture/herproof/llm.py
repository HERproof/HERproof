"""LLM providers behind one call: `complete_json(system, user, schema)`.

Supported providers:
  claude   Anthropic SDK   (ANTHROPIC_API_KEY, or `ant auth login`)   default model claude-opus-5
  gemini   google-genai    (GEMINI_API_KEY or GOOGLE_API_KEY)          default model gemini-2.5-pro

Pick with --provider on the CLI, HERPROOF_PROVIDER in .env, or leave it on
"auto" to use whichever key is configured (Claude first). Override the model
with --model, ANTHROPIC_MODEL, or GEMINI_MODEL.
"""
from __future__ import annotations

import copy
import json
import os
from typing import Any

PROVIDERS = ("claude", "gemini")

DEFAULT_MODELS = {
    "claude": os.environ.get("ANTHROPIC_MODEL", "claude-opus-5"),
    # HERPROOF_MODEL is what the rest of the HerProof pipeline (llm.py at the repo root) uses
    "gemini": os.environ.get("GEMINI_MODEL") or os.environ.get("HERPROOF_MODEL", "gemini-2.5-pro"),
}


class LLMError(RuntimeError):
    pass


def available_provider() -> str | None:
    """First provider with credentials, or None."""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or _has_ant_profile():
        return "claude"
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    return None


def _has_ant_profile() -> bool:
    return os.path.isdir(os.path.expanduser("~/.config/anthropic"))


def resolve_provider(name: str | None) -> str:
    name = (name or os.environ.get("HERPROOF_PROVIDER") or "auto").lower()
    if name == "auto":
        p = available_provider()
        if p is None:
            raise LLMError("no LLM credentials found: set ANTHROPIC_API_KEY or GEMINI_API_KEY (or use --no-classify)")
        return p
    if name not in PROVIDERS:
        raise LLMError(f"unknown provider {name!r}; choose one of {PROVIDERS}")
    return name


def complete_json(system: str, user: str, schema: dict[str, Any], provider: str = "auto", model: str | None = None) -> dict[str, Any]:
    provider = resolve_provider(provider)
    model = model or DEFAULT_MODELS[provider]
    if provider == "claude":
        return _claude(system, user, schema, model)
    return _gemini(system, user, schema, model)


# ---- Claude -----------------------------------------------------------------
def _claude(system: str, user: str, schema: dict[str, Any], model: str) -> dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        system=system,
        thinking={"type": "adaptive"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    if resp.stop_reason == "refusal":
        raise LLMError(f"Claude declined: {getattr(resp, 'stop_details', None)}")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


# ---- Gemini -----------------------------------------------------------------
def _gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Gemini's response_schema is an OpenAPI-style subset: no additionalProperties."""
    s = copy.deepcopy(schema)

    def strip(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("additionalProperties", None)
            for v in node.values():
                strip(v)
        elif isinstance(node, list):
            for v in node:
                strip(v)

    strip(s)
    return s


def _gemini(system: str, user: str, schema: dict[str, Any], model: str) -> dict[str, Any]:
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise LLMError("pip install google-genai   (the Gemini SDK is not installed)") from e

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    resp = client.models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=_gemini_schema(schema),
            temperature=0.2,
        ),
    )
    if not resp.text:
        fb = getattr(resp, "prompt_feedback", None)
        raise LLMError(f"Gemini returned no text (block reason: {getattr(fb, 'block_reason', None)})")
    return json.loads(resp.text)
