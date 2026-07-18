# Product Evaluation — Glosa Live Translate

- **Author:** Taimoor Raza
- **Date:** 2026-07-13
- **LLM provider / model:** Anthropic · `claude-sonnet-5` (structured output via `instructor`, per-locale es-MX prompt)
- **Backend target:** `https://glosa-gateway.fly.dev` (public gateway) → private AI service via Fly `flycast`

## Verdict

> This is shippable. A fresh clone follows the README, both services come up with one command each, and the widget's contract is satisfied exactly — verified end-to-end against the **deployed** gateway, not just localhost. The strongest part is the two-tier cache: identical `(text, target)` never hits the LLM twice, a hit is ~300× faster than a miss (7.6 ms vs 2969 ms p95), the SQLite tier survives restart, and on a real Home Depot page a repeat translation of the same 12 strings dropped from 16.7 s to 819 ms with all 12 served from cache. Translation quality is natural Mexican Spanish with numbers, prices, and product codes preserved. Errors fail loud (upstream down → `502`, never the untranslated English). The weakest points are operational, not correctness: image/banner text on real sites can't be translated (it's baked into pixels, not DOM text), and cold starts add latency to the first request after the AI machine auto-stops.

**Automated checks (from `eval/report.json`):** 70 / 70 passing — a further 30 pts (LLM-prompt quality and deploy/docs) are reviewed by hand.

## 1. Performance & cost (from `benchmark/bench.py`, cold cache, end-to-end through the gateway)

| Metric | Result | SLA | Pass? |
|---|---|---|---|
| Cache hit p95 | 7.6 ms | ≤ 60 ms | ✅ |
| Cache miss p95 | 2969 ms | ≤ 3500 ms | ✅ |
| Cache hit rate | 77.5 % | ≥ 60 % | ✅ |
| Throughput | 1622 req/s | ≥ 20 | ✅ |
| Error rate | 0.0 % | ≤ 1 % | ✅ |
| Cost per miss | $0.0001715 | — | — |
| Monthly savings from cache | $66.46 (@ 500k/mo: $85.75 → $19.29) | — | — |

`python benchmark/bench.py` exits `0` — every SLA passes with margin.

> **Cost note (honest):** `benchmark/sla.json` prices the cost model at $3/$15 per MTok — Claude Sonnet's standard published rate — so the dollar figures above are accurate at standard pricing. (Sonnet 5 has an introductory $2/$10 rate through 2026-08-31, so real spend during that window is lower.)

## 2. Live-website test

- **Site tested:** `https://www.homedepot.com` (a real, content-rich site I do not control)
- **Translated whole page?** Yes for DOM text — real navigation/category strings translated live through the **deployed** gateway and swapped into the page (18 DOM nodes flipped to es-MX in the captured screenshot). Verification driven programmatically in the page context; the CORS-open gateway served the page's own strings.
- **Coverage gaps:** Promotional banners ("$1000 OFF Select Appliances", "FAST FREE DELIVERY") stay in English — that text is **rasterized into images**, so no DOM-text translator can reach it. This is an inherent limitation, not a backend defect.
- **Cache on re-translate:** Re-sending the same 12 real page strings returned **819 ms with 12/12 `cached: true`**, vs **16.7 s** cold — the cache demonstrably works against live, uncontrolled content.
- **Resilience:** No layout breakage; the deployed gateway answered every request with correct es-MX. On strict-CSP sites the **Chrome extension** is the loader (its background worker proxies to the gateway, bypassing page CSP); this automated pass exercised the deployed backend directly against the live page's content.
- **Screenshots:** Home Depot homepage after DOM swap, captured during the run.

### Sample translations (from the live Home Depot page + a price/code probe)

| Original (EN) | Translation (es-MX) | Numbers/prices/codes kept? | OK? |
|---|---|---|---|
| Specials & Offers | Ofertas y promociones | n/a | ✅ |
| Blinds & Window Treatments | Persianas y cortinas para ventanas | n/a | ✅ |
| Lumber & Composites | Madera y compuestos | n/a | ✅ |
| Home Décor | Decoración para el Hogar | n/a | ✅ |
| Doors & Windows | Puertas y ventanas | n/a | ✅ |
| Building Materials | Materiales de Construcción | n/a | ✅ |
| Buy the DeWalt DCD771C2 drill for $99.00, save $50 today only. | Compre el taladro DeWalt DCD771C2 por $99.00, ahorre $50 solo hoy. | ✅ `DCD771C2`, `$99.00`, `$50` all preserved | ✅ |
| Add to Cart | Agregar al carrito | n/a | ✅ |

## 3. Dimension assessment

| Dimension | Pass / Partial / Fail | Evidence |
|---|---|---|
| Translation accuracy | ✅ Pass | 12/12 live Home Depot strings correct; idioms natural |
| Mexican-Spanish register (es-MX) | ✅ Pass | *usted* imperatives ("Compre", "ahorre"); es-MX vocabulary, correct accents |
| Numbers / prices / codes preserved | ✅ Pass | `DeWalt DCD771C2`, `$99.00`, `$50` verbatim through the deployed gateway |
| Page coverage | ⚠️ Partial | DOM text translated; image/banner text unreachable (baked into pixels) |
| Cache effectiveness | ✅ Pass | 12/12 `cached:true` on re-translate; 16.7 s → 819 ms; SQLite survives restart |
| Latency vs SLA | ✅ Pass | hit p95 7.6 ms, miss p95 2969 ms — both within SLA; ~300× hit speedup |
| Error handling (no silent English) | ✅ Pass | Upstream-down → `502` with error body; bad input → `400`; no English fallback |
| Resilience on a real site | ✅ Pass | Deployed gateway served homedepot.com content live; no layout breakage |
| UX polish | ✅ Pass | Correct contract shapes; gateway `/health` nests AI health; trace id correlates across both logs |

## 4. Top fixes before shipping

1. **Warm the AI machine before a live demo** — it has `min_machines_running = 0` (auto-stops when idle), so the first request after a lull is a cold start. Bump to `1` (`fly.toml`) or send a warm-up request first.
2. **Reach image/banner text** — DOM-text translation can't touch rasterized promo banners. An OCR pass or a rendered-text overlay would close the biggest coverage gap on real retail sites.
3. **Add rate limiting on the gateway** — a per-IP `429` with a friendly widget message would harden the public endpoint before real traffic.
