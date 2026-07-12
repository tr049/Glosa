"""
lib/prompts.py — YAML + Jinja2 prompt management.
=====================================================================
All prompt text lives in prompts.yaml; this module loads it once and renders a
named prompt as a Jinja2 template. Adding, editing, or versioning a prompt is a
YAML change with no code edit — the seam that lets prompt management grow.

Design choices:
  - autoescape=False: prompts are plain text for an LLM, not HTML. Escaping would
    corrupt <, &, and quotes in the instructions.
  - StrictUndefined: a missing template variable raises instead of silently
    rendering an empty string into the model's instructions (fail loud).
  - lru_cache: the YAML file is read and parsed once per process.
"""
from __future__ import annotations

import functools
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

_PROMPTS_PATH = Path(__file__).with_name("prompts.yaml")

_env = Environment(
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
)


@functools.lru_cache(maxsize=1)
def _load() -> dict:
    with _PROMPTS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def locale_for(target: str) -> dict:
    """Return the merged per-language config for `target`: `locale_defaults`
    overlaid with the locale's own overrides from prompts.yaml. Unknown locales
    fall back to a minimal config using the code as the name, so callers always
    get a dict carrying name/register/formality/notes."""
    data = _load()
    defaults = data.get("locale_defaults", {})
    specific = data.get("locales", {}).get(target, {"name": target})
    return {**defaults, **specific}


@functools.lru_cache(maxsize=None)
def _template(name: str):
    """Compile and cache the named prompt template (once per process)."""
    return _env.from_string(_load()["prompts"][name]["template"])


def render(name: str, **variables) -> str:
    """Render the named prompt template from prompts.yaml with `variables`.
    Raises KeyError if the prompt name is unknown and UndefinedError if a
    required template variable is missing (both fail loud, by design)."""
    return _template(name).render(**variables).strip()
