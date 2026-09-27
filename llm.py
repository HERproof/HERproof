"""
HerProof — shared Gemini client (google-genai SDK).

Privacy: everything passed to `generate()` is sent to Google's Gemini API.
Before running on real survivor evidence, check the API's data-retention and
training terms for the key's account tier.
"""

import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL = os.environ.get("HERPROOF_MODEL", "gemini-3.8-flash")

_client = None


def generate(contents):
    """Send contents (strings / PIL images) to Gemini, return the response text."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = _client.models.generate_content(model=MODEL, contents=contents)
    return resp.text or ""
