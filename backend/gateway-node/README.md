# Gateway (Node / Express) — the browser-facing "software backend"

The only server the browser talks to. It serves the widget, validates and
forwards requests to the Python AI service, exposes `/health` + `/stats`, and
logs traffic. Two things worth calling out in `server.js`:

1. **Structured request logging** — one JSON line per request (method, url, status, ms, request-id), to stdout and `gateway.log`.
2. **Fail-loud proxy (`callAiService()`)** — forwards requests to the Python AI service and surfaces any downstream failure as a `502`, never a silent passthrough.

## Run it

```bash
npm install
cp .env.example .env      # PORT=8787, AI_SERVICE_URL=http://localhost:8000
npm start                 # or: npm run dev  (auto-restart)
```

Start the Python AI service first (port 8000), then this gateway (port 8787).

## Check it

```bash
curl -s localhost:8787/health           # reports the AI service health too
curl -s localhost:8787/translate -H 'content-type: application/json' \
  -d '{"text":"Hello there","target":"es-MX"}'
```

With the AI service running, load the widget (console snippet or extension) on
any page and it translates through this gateway.

## Why split the gateway from the AI service?

The browser-facing app layer (CORS, validation, logging, serving assets, rate
limits) is a different concern from the AI layer (prompts, models, caching,
keys). Keeping them as separate services lets each scale, deploy, and fail
independently — and keeps API keys off the edge that the browser can reach.
