# Eval — how Glosa's quality and SLAs are measured

Glosa is validated against a measurable set of quality criteria. Running the
eval generates a **Product Evaluation** report backed by real, captured evidence.

> **Shortcut:** run the **`/product-eval`** skill (in `.claude/skills/`). It runs
> everything below *plus* a live-website test on a real site (e.g. homedepot.com)
> and writes **`PRODUCT_EVAL.md`** at the repo root. The steps below are what the
> skill runs under the hood; run them directly to score the criteria without the skill.

## Run the checks

With both services running:

```bash
python eval/eval.py --deploy-url "https://your-gateway.fly.dev"   # --deploy-url optional
```

This writes, next to this file:

- **`REPORT.md`** — human-readable evaluation report (scored criteria + captured
  evidence). Read it to see where the product stands and fix any Fail/Partial rows.
- **`report.json`** — the same data, machine-readable.

## How scoring works

- **`auto` criteria** are checked right here by running the backend: contract
  shapes, cache behavior + persistence, the SLA benchmark, logging/observability,
  and status codes. See `rubric.json` for the exact checks.
- **`manual` criteria** — Mexican-Spanish quality and deploy/docs — are reviewed
  by hand using the evidence the report captures (sample translations, cost/latency numbers).

The report also flags red lines automatically: committed secrets, or accidental
edits to the widget / extension / benchmark reference files.
