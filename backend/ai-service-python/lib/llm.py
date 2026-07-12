"""
lib/llm.py — the LLM translation call (Anthropic + instructor structured output)
=====================================================================
One job: turn an English string into Mexican Spanish using an LLM.

  - The system prompt is rendered from prompts.yaml via Jinja2 (lib/prompts.py).
  - The model's reply is validated into the `Translation` schema by `instructor`,
    so the call site gets a typed object instead of raw text.
  - Provider is Anthropic Claude (the `anthropic` SDK, ANTHROPIC_API_KEY). It is
    kept swappable — the instructor-patched client is built in one place.

FAIL LOUD: we do NOT wrap the call in a try/except that returns `text` on error.
Any provider / SDK / schema-validation error propagates so the caller returns a
502. Silently serving the untranslated English while looking healthy is an
automatic fail on this assignment (and a real shipped bug).
"""
from __future__ import annotations

import os

import instructor
from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from lib import prompts

MODEL_DEFAULT = os.getenv("MODEL", "claude-sonnet-4-6")


class Translation(BaseModel):
    """Structured result of one translation.

    Intentionally minimal today (a single field) — the value of the schema is
    that it can grow (detected_source_language, confidence, untranslatable
    segments) without changing translate_text()'s callers."""

    translated: str = Field(
        description=(
            "The input text rendered in the target language. Translation ONLY — "
            "no surrounding quotes, notes, or commentary."
        )
    )


# Lazily-built, instructor-patched Anthropic client. Lazy so it is constructed
# AFTER app.py's load_dotenv() has populated ANTHROPIC_API_KEY; shared so the
# concurrent /translate/batch calls reuse one client instead of opening many.
_client: instructor.AsyncInstructor | None = None


def _get_client() -> instructor.AsyncInstructor:
    global _client
    if _client is None:
        # from_anthropic patches the client so messages.create accepts response_model.
        _client = instructor.from_anthropic(AsyncAnthropic())  # reads ANTHROPIC_API_KEY
    return _client


async def translate_text(text: str, target: str = "es-MX", model: str = MODEL_DEFAULT) -> str:
    """Return `text` translated into `target` (Mexican Spanish by default).

    Fails loud: any provider/SDK/validation error propagates to the caller
    (→ 502). Never returns the original English on failure.
    """
    system = prompts.render("translate_system", locale=prompts.locale_for(target))
    result: Translation = await _get_client().messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": text}],
        response_model=Translation,
        max_retries=2,  # re-ask at most once if the structured reply fails validation
    )
    return result.translated.strip()
