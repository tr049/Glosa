# Deploy to Fly.io

Two apps, one per service. The **gateway is public** (the browser/extension talks
to it); the **AI service is private** (only the gateway reaches it, over Fly's
private `flycast` network — so your API key never sits on a browser-reachable box).

All commands are run **from the repo root** unless noted. Replace `glosa-ai` /
`glosa-gateway` with your own names if you change them in the `fly.toml`s.

---

## 0. One-time setup

```bash
# Install flyctl (macOS)
brew install flyctl        # or: curl -L https://fly.io/install.sh | sh
fly auth login             # opens the browser  (run yourself: `! fly auth login`)
```

---

## 1. Python AI service (private)

```bash
cd backend/ai-service-python

# Create the app from the existing fly.toml (don't deploy yet).
# `fly launch` may pick your NEAREST region (e.g. bom) and rewrite primary_region.
fly launch --no-deploy --copy-config --name glosa-ai

# Persistent volume for the SQLite cache (survives restarts/redeploys).
# IMPORTANT: --region MUST equal primary_region in fly.toml, or the machine
# won't be able to mount it. Check with: grep primary_region fly.toml
fly volumes create glosa_data --region bom --size 1 -a glosa-ai

# Secret: your provider key (never baked into the image)
fly secrets set ANTHROPIC_API_KEY=sk-ant-... -a glosa-ai

# Deploy
fly deploy -a glosa-ai

# --- Make it PRIVATE: drop the public IPs, add a private flycast IP ---
fly ips list -a glosa-ai                     # note any public v4/v6
fly ips release <public-ipv4> -a glosa-ai    # release each public IP shown
fly ips release <public-ipv6> -a glosa-ai
fly ips allocate-v6 --private -a glosa-ai     # flycast address (org-private)
```

Now the AI service is reachable **only** from inside your Fly org at
`http://glosa-ai.flycast`.

> Quick fallback if flycast gives you trouble: skip the three `fly ips` lines and
> leave the service public at `https://glosa-ai.fly.dev`. It works, but the rubric
> prefers keeping the AI service private.

---

## 2. Node gateway (public)

The gateway serves the widget from `../../widget/`, so its image **must build
from the repo root** — you run `fly deploy` from the repo root and pass `.` as
the build context. Two rules that bite if you get them wrong:

- In `backend/gateway-node/fly.toml`, `dockerfile` is resolved **relative to the
  fly.toml's own directory**, so it must be just `dockerfile = 'Dockerfile'`
  (NOT `backend/gateway-node/Dockerfile`, which Fly would double up into
  `backend/gateway-node/backend/gateway-node/Dockerfile`).
- Run from the **repo root** with a trailing `.` so the build context includes
  `widget/`. Running from inside `backend/gateway-node/` makes the context that
  folder, and the `widget/` COPY fails.

```bash
cd ..                       # back to repo root
# Use the SAME region as the AI service so gateway→AI stays fast.
fly launch --no-deploy --copy-config --name glosa-gateway --region iad \
  --config backend/gateway-node/fly.toml

# Point the gateway at the private AI service
fly secrets set AI_SERVICE_URL=http://glosa-ai.flycast -a glosa-gateway
#   (public fallback: AI_SERVICE_URL=https://glosa-ai.fly.dev)

# Deploy — run from the REPO ROOT; `.` = build context = repo root
fly deploy --config backend/gateway-node/fly.toml .
```

---

## 3. Verify the deployed stack

```bash
GW=https://glosa-gateway.fly.dev

# Health — gateway should nest the AI service's health
curl -sf $GW/health

# Translate (cold miss, then run again for cached:true)
curl -s $GW/translate -H 'content-type: application/json' \
  -d '{"text":"Add to cart","target":"es-MX"}'
curl -s $GW/translate -H 'content-type: application/json' \
  -d '{"text":"Add to cart","target":"es-MX"}'   # cached:true, tiny latencyMs

# Trace correlation across both services' logs (two terminals)
curl -s $GW/translate -H 'content-type: application/json' \
  -H 'X-Request-Id: deploytest-123' -d '{"text":"Checkout","target":"es-MX"}'
fly logs -a glosa-gateway | grep deploytest-123
fly logs -a glosa-ai      | grep deploytest-123
```

> On Fly, logs go to the platform log stream (`fly logs`), not to files — the
> `gateway.log`/`ai-service.log` files are for local grading. The same request id
> still appears in both apps' streams.

---

## 4. Point the extension at production

1. `chrome://extensions` → Developer mode → **Load unpacked** → `extension/`
2. Open the extension **popup** → set the backend URL to
   `https://glosa-gateway.fly.dev`
3. Visit a real site you don't control (e.g. **homedepot.com**) → open the
   widget → **Translate page**. This is your graded live-website test — it must
   pass against the **deployed** gateway, not localhost.

---

## Notes

- **Cold starts:** the AI machine has `min_machines_running = 0` (auto-stops when
  idle). Before recording your demo, bump it to `1` (`fly scale count 1 -a
  glosa-ai`, or edit the `fly.toml`) so the first request isn't slow.
- **Regions:** keep both apps in the same `primary_region` so gateway→AI hops
  stay fast. The volume pins the AI service to one region.
- **Secrets, never files:** `ANTHROPIC_API_KEY` and `AI_SERVICE_URL` are set via
  `fly secrets` — `.env` is git-ignored and never shipped in the image.
