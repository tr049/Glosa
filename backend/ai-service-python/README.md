# AI Service (Python / FastAPI) — Glosa's translation core

This service does the actual translating, caching, and AI-side logging. The
Node gateway forwards requests here; the browser never talks to it directly.

## Components

| File | Responsibility |
|------|----------------|
| `app.py` | FastAPI endpoints (`/translate`, `/translate/batch`, `/health`, `/stats`), locale validation, structured logging, and the cache→LLM flow in `translate_one()` |
| `lib/llm.py` | The LLM call — Anthropic + `instructor` structured output, returning a validated `Translation` object (fail-loud: never returns the untranslated input) |
| `lib/cache.py` | Two-tier cache — in-memory dict + SQLite — keyed by a SHA-256 hash of `(text, target)`, with hit-rate stats |
| `lib/prompts.py` + `lib/prompts.yaml` | Per-locale prompt library rendered with Jinja2 (`StrictUndefined`); adding a language is a YAML edit |
| `lib/logger.py` | Structured JSON logging (one line per translation) to stdout and `ai-service.log` |

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your API key, pick your MODEL
uvicorn app:app --reload --port 8000
```

Then hit it directly to test without the browser:

```bash
curl -s localhost:8000/health
curl -s localhost:8000/translate -H 'content-type: application/json' \
  -d '{"text":"Good morning, welcome!","target":"es-MX"}'
# run the same command twice — the second shows "cached": true and a far lower latencyMs
curl -s localhost:8000/stats
```

## Key design decisions

1. **Register-specific prompt** — natural Mexican Spanish (es-MX), not generic Spanish; numbers, prices, and product/model codes preserved verbatim.
2. **Two-tier cache** — memory + SQLite, keyed by a hash of `(text, target)`. Identical text never hits the LLM twice; the SQLite tier survives a restart. Verify via `latencyMs` and `/stats`.
3. **Fail loud** — a provider/LLM error propagates as a `502`; the service never serves the untranslated English as if it succeeded.
4. **Structured logs** — one JSON line per translation in `ai-service.log`, correlated across services by `X-Request-Id`.
