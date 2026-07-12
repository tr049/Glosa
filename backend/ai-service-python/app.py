"""
FDE · Assignment 1 · Python AI Service  (this is the real assignment)
=====================================================================
A small FastAPI service that translates English → Mexican Spanish with:
  - an LLM call            (lib/llm.py)
  - a two-tier cache       (lib/cache.py)  — memory + SQLite
  - structured logging     (lib/logger.py) — provided, wired for you

The Node gateway forwards the browser's requests here. You implement the
TODOs so the widget lights up. Run:

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env          # then add your API key
    uvicorn app:app --reload --port 8000
"""
import os
import re
import time
import uuid
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AfterValidator, BaseModel

from lib.cache import TwoTierCache
from lib.llm import translate_text
from lib.logger import get_logger

load_dotenv()

MODEL = os.getenv("MODEL", "claude-sonnet-4-6")
DB_PATH = os.getenv("TRANSLATION_DB_PATH", "translations.db")

app = FastAPI(title="FDE Live Translate — AI Service")
log = get_logger("ai-service")
cache = TwoTierCache(DB_PATH)


# The contract specifies 400 for a bad request body; FastAPI's default for a
# validation failure is 422. Remap it so the AI service returns 400 (matching the
# gateway and the assignment contract) whether hit via the gateway or directly.
@app.exception_handler(RequestValidationError)
async def _on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "invalid request", "detail": jsonable_encoder(exc.errors())},
    )


# A well-formed BCP-47-ish locale code (es-MX, zh-Hans, pt-BR, es-419). Validating
# the shape here rejects junk / prompt-injection payloads in `target` before they
# reach the LLM prompt, while still allowing locales not yet listed in prompts.yaml.
_LOCALE_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def _check_locale(v: str) -> str:
    if not _LOCALE_RE.match(v):
        raise ValueError("target must be a locale code like 'es-MX'")
    return v


LocaleCode = Annotated[str, AfterValidator(_check_locale)]


# request/response shapes ----------------------------------------------------
class TranslateIn(BaseModel):
    text: str
    target: LocaleCode = "es-MX"

class BatchIn(BaseModel):
    texts: list[str]
    target: LocaleCode = "es-MX"


@app.on_event("startup")
async def startup():
    await cache.init()
    log.info("ai_service_started", extra={"model": MODEL, "db": DB_PATH})


# --- core: translate one string --------------------------------------------
async def translate_one(text: str, target: str) -> dict:
    """Translate a single string, using the cache first.

    Returns a dict shaped exactly like the widget expects:
        {"translated": str, "cached": bool, "latencyMs": int, "model": str}
    """
    text = (text or "").strip()
    if not text:
        return {"translated": "", "cached": False, "latencyMs": 0, "model": MODEL}

    t0 = time.perf_counter()

    # Cache-first flow. A cache HIT never calls the LLM (the assignment's core
    # invariant); a MISS translates once, then stores it so the next identical
    # (text, target) is a hit. latencyMs is measured from t0 on BOTH paths, so a
    # hit (memory/SQLite) reads dramatically faster than a miss (LLM round-trip).
    cached_value = await cache.get(text, target)
    if cached_value is not None:
        translated, cached = cached_value, True
    else:
        translated = await translate_text(text, target, model=MODEL)
        await cache.set(text, target, translated, model=MODEL)
        cached = False

    latency_ms = int((time.perf_counter() - t0) * 1000)
    return {"translated": translated, "cached": cached, "latencyMs": latency_ms, "model": MODEL}


@app.post("/translate")
async def translate(body: TranslateIn, request: Request):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    result = await translate_one(body.text, body.target)
    log.info(
        "translate",
        extra={"requestId": request_id, "cached": result["cached"], "latencyMs": result["latencyMs"], "chars": len(body.text)},
    )
    return result


@app.post("/translate/batch")
async def translate_batch(body: BatchIn, request: Request):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    t0 = time.perf_counter()
    results = []
    for t in body.texts:
        results.append(await translate_one(t, body.target))
    latency = int((time.perf_counter() - t0) * 1000)
    hits = sum(1 for r in results if r["cached"])
    log.info("translate_batch", extra={"requestId": request_id, "count": len(results), "hits": hits, "latencyMs": latency})
    # widget expects {results: [{translated, cached}], latencyMs}
    return {"results": [{"translated": r["translated"], "cached": r["cached"]} for r in results], "latencyMs": latency}


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL, "cacheSize": await cache.size()}


@app.get("/stats")
async def stats():
    return await cache.stats()
