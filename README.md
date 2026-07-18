# Glosa — Live Translate

> A browser widget that translates any English web page into **Mexican Spanish**
> in real time and on demand — backed by a two-service LLM API with a two-tier cache.

Glosa drops a floating **Translate** button onto any page. Click **Translate
page** and the whole page flips to natural Mexican Spanish; click **Restore** to
bring the English back. It ships three ways off one widget — a Chrome extension,
a DevTools console snippet, and a gateway-served `<script>` — and it works on
real, third-party sites it doesn't control (homedepot.com, GitHub, Google).

Behind the widget are two independently-deployable services: a **Node gateway**
(browser-facing: CORS, validation, logging, request tracing) and a **Python AI
service** (the LLM call, a two-tier cache, and structured logs). API keys never
touch the browser edge.

## Highlights

- **Real LLM translation** into es-MX (Mexican Spanish) — natural register, not generic Spanish; numbers, prices, and product/SKU codes preserved verbatim.
- **Two-tier cache** (in-memory + SQLite, SHA-256 keyed) — identical text never hits the LLM twice; a cache hit is **~300× faster** than a miss and the SQLite tier survives a restart.
- **Fail-loud by design** — a provider error surfaces as `502`; the service never serves untranslated English as if it succeeded.
- **Observable** — one structured JSON log line per request/translation, correlated end-to-end across both services by a single `X-Request-Id`.
- **Proven, not eyeballed** — a standard-library benchmark enforces an SLA and exits non-zero on breach (usable as a CI gate).
- **Deployed** — both services run on Fly.io; the gateway is public, the AI service private over `flycast`.

### Measured performance (end-to-end through the deployed gateway)

| Metric | Result | SLA |
|---|---|---|
| Cache hit p95 | **7.6 ms** | ≤ 60 ms |
| Cache miss p95 | **2969 ms** | ≤ 3500 ms |
| Cache hit rate | **77.5 %** | ≥ 60 % |
| Throughput | **1622 req/s** | ≥ 20 |
| Error rate | **0.0 %** | ≤ 1 % |

Full write-up in [`PRODUCT_EVAL.md`](PRODUCT_EVAL.md).

## Architecture

Three moving parts: a browser frontend and two backend services.

```
   ┌─────────────────────────┐
   │  Browser (any web page) │
   │  ┌───────────────────┐  │
   │  │  🌐 Widget         │  │   ← MV3 extension / console loader / <script>
   │  │  (or extension)   │  │
   │  └─────────┬─────────┘  │
   └────────────┼────────────┘
                │  POST /translate           (JSON over HTTP, CORS)
                ▼
   ┌─────────────────────────┐
   │  Node Gateway  :8787     │   ← CORS · validate · log · trace · serve widget · proxy
   └────────────┬────────────┘
                │  POST /translate
                ▼
   ┌─────────────────────────┐
   │  Python AI Service :8000 │   ← LLM · two-tier cache · structured logs
   └────────────┬────────────┘
                │
       ┌────────┴────────┐
       ▼                 ▼
   LLM provider    SQLite cache (translations.db)
```

**Why two services?** The browser-facing concerns (CORS, validation, serving
assets, rate limiting, request logs) are genuinely different from the AI
concerns (prompts, model choice, caching, API keys). Splitting them means each
service deploys and fails independently, and API keys never live on a
browser-reachable edge.

## Repository layout

| Component | Path |
|-----------|------|
| Translation widget | `widget/translation-widget.js` |
| Console loader | `loader/console-snippet.js` |
| Chrome extension (MV3) | `extension/` |
| Demo page | `demo-pages/index.html` |
| Node gateway | `backend/gateway-node/` |
| Python AI service | `backend/ai-service-python/` |
| Benchmark & SLA gate | `benchmark/` |
| Quality evaluation | `eval/`, `PRODUCT_EVAL.md` |

## The API contract

The widget speaks this to the **Node gateway**, which forwards the same shapes to
the **Python AI service**.

### `POST /translate`
```jsonc
// request
{ "text": "Good morning, welcome!", "target": "es-MX" }
// response
{ "translated": "¡Buenos días, bienvenido!", "cached": false, "latencyMs": 812, "model": "claude-sonnet-4-6" }
```

### `POST /translate/batch`  (used by "Translate page")
```jsonc
// request
{ "texts": ["Home", "Best sellers", "Add to cart"], "target": "es-MX" }
// response
{ "results": [ { "translated": "Inicio", "cached": true }, ... ], "latencyMs": 40 }
```

### `GET /health`
```jsonc
{ "status": "ok", "model": "claude-sonnet-4-6", "cacheSize": 128 }
```

### `GET /stats`
```jsonc
{ "requests": 40, "memory_hits": 22, "db_hits": 6, "misses": 12, "hit_rate_pct": 70.0 }
```

**Contract invariants:**
- `cached` is **true** only when the answer came from cache (no LLM call).
- `latencyMs` is measured server-side on both paths — a cache hit is *dramatically* faster than a miss.
- Identical `(text, target)` never hits the LLM twice.
- Errors return a JSON body and a sensible status (`400` bad input, `502` upstream failure, `501` not-implemented).

## Running it locally

Two services, two terminals. Start the AI service first (it can be tested with
`curl`, no browser needed), then the gateway, then load the widget.

### Python AI service
```bash
cd backend/ai-service-python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add ANTHROPIC_API_KEY (and optionally MODEL=claude-sonnet-5)
uvicorn app:app --port 8000
```
Test it in isolation:
```bash
curl -s localhost:8000/translate -H 'content-type: application/json' \
  -d '{"text":"Good morning, welcome!","target":"es-MX"}'   # run twice → 2nd is cached
```

### Node gateway
```bash
cd backend/gateway-node
npm install
cp .env.example .env            # AI_SERVICE_URL defaults to http://localhost:8000
npm start                       # http://localhost:8787
```

### Load the widget in the browser
- **Extension (recommended — required for real sites):** `chrome://extensions` → enable Developer mode → *Load unpacked* → select `extension/`. Its content script injects the widget on every page and its background worker proxies to the gateway, so it works even on strict-CSP sites. Set the backend URL in the popup.
- **Console (quick, permissive pages only):** open a page → DevTools → Console → paste `loader/console-snippet.js`. Strict-CSP sites block this — use the extension there.
- **Demo page:** open `demo-pages/index.html` and uncomment the `<script src=".../widget.js">` line at the bottom.

Open the **Translate** button (bottom-right) → **Translate page** → the whole
page flips to Mexican Spanish. Click **Restore page**, then **Translate page**
again → the badges show **cache hits** and the latency drops.

> The extension bundles its own copy of the widget at
> `extension/translation-widget.js`, kept byte-identical to `widget/translation-widget.js`.

## Performance, SLA & cost

A translation that's correct but slow or expensive fails in production. Glosa
meets the SLA in [`benchmark/sla.json`](benchmark/sla.json), verified by the
benchmark — measured, not eyeballed.

| Metric | Target | Why it matters |
|--------|--------|----------------|
| Cache **hit** latency, p95 | ≤ 60 ms | a cache hit should feel instant |
| Cache **miss** latency, p95 | ≤ 3500 ms | one LLM round-trip, end to end |
| **Cache hit rate** | ≥ 60 % | repeated text served from cache |
| Error rate | ≤ 1 % | reliability under concurrency |
| Warm **throughput** | ≥ 20 req/s | translate a page's worth of chunks fast |

Every **cache miss** costs an LLM call; every **hit** is effectively free — so
the hit rate is a direct lever on cost. `bench.py` reports latency percentiles,
throughput, cost per miss, and projected monthly cost with vs. without the cache.

```bash
# with both services running:
python benchmark/bench.py                  # end-to-end through the gateway
python benchmark/bench.py --direct         # straight to the AI service (:8000)
python benchmark/bench.py --json out.json  # also write machine-readable results
```

`bench.py` **exits non-zero if any SLA fails**, so it doubles as a CI gate.

## Deploy

Both services run on [Fly.io](https://fly.io) — the gateway public, the AI
service private over `flycast` so only the gateway can reach it. Full runbook in
[`DEPLOY.md`](DEPLOY.md):

```bash
# AI service (private)
cd backend/ai-service-python && fly launch --no-deploy
fly secrets set ANTHROPIC_API_KEY=...        # never baked into the image
fly deploy

# Gateway (public) — built from the repo root so it can serve widget/
cd .. && fly launch --no-deploy --config backend/gateway-node/fly.toml
fly secrets set AI_SERVICE_URL=http://<your-ai-app>.flycast
fly deploy --config backend/gateway-node/fly.toml .
```

Point the extension popup at the public gateway URL and translate a real site.

## Feature checklist

Glosa's backend:

- [x] **LLM** — translates EN → **Mexican Spanish** (es-MX register) via a real LLM call.
- [x] **Caching** — two-tier (in-memory + SQLite), keyed by a hash of `(text, target)`; identical input never calls the LLM twice.
- [x] **Logging** — one structured line per request in the gateway and per translation in the AI service.
- [x] **Tracing** — an `X-Request-Id` set at the gateway (reusing an inbound header if present), forwarded to the AI service, logged by both; one request is greppable end-to-end.
- [x] **Performance** — meets every SLA in `benchmark/sla.json`; `python benchmark/bench.py` exits `0`.
- [x] **Runs locally** — each service starts with one documented command; secrets come from `.env`.
- [x] **Deployed on Fly.io** — both services deployed; the extension works against the public gateway URL.
- [x] **Contract** — every endpoint matches the shapes above; the widget works unmodified.

## Configuration & providers

**LLM provider:** Anthropic. **Model:** `claude-sonnet-5` (set via `MODEL` in
`backend/ai-service-python/.env`, overriding the code default `claude-sonnet-4-6`).
Translations use structured output — the reply is validated into a Pydantic model —
with the es-MX prompt rendered per-locale from `lib/prompts.yaml`. The provider is
swappable; the API key is read from `.env` and never committed.

The gateway writes one structured JSON line per request to `gateway.log`; the AI
service writes one per translation to `ai-service.log`. An `X-Request-Id` is
forwarded gateway → AI service and logged by both, so a single request is
greppable end-to-end:

```bash
grep "<request-id>" backend/gateway-node/gateway.log backend/ai-service-python/ai-service.log
```

## Roadmap

- **Dockerize** with a `docker-compose.yml` so `docker compose up` runs everything.
- **Rate limiting** on the gateway (per-IP) with a `429` + friendly widget message.
- **Streaming** long translations token-by-token into the widget.
- **Cache TTL / invalidation** and a `POST /clear-cache` endpoint.
- **Language picker** in the widget/popup (es-MX, es-ES, pt-BR…) threaded through the contract — the prompt library already ships config for 10 locales.

## Troubleshooting

- **Widget shows "Can't reach backend"** → the Node gateway isn't running, or the widget's `API_URL` doesn't match. Set it in the extension popup, or `window.GLOSA_CONFIG = { API_URL: "..." }` before pasting the console snippet.
- **CORS errors** → the gateway enables CORS for all origins in dev; make sure requests go to the gateway (`:8787`), not the AI service (`:8000`).
- **macOS port 5000 is taken** → that's AirPlay Receiver. Glosa uses `8787`/`8000` on purpose.
- **Extension didn't update after a code change** → the extension bundles its own copy of the widget; re-copy it (`cp widget/translation-widget.js extension/`) and hit *Reload* on `chrome://extensions`.

## License

MIT © 2026 Taimoor Raza — see [`LICENSE.md`](LICENSE.md).
