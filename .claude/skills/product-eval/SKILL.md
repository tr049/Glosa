---
name: product-eval
description: Generate a Product Evaluation report (PRODUCT_EVAL.md, optionally PDF) for Glosa Live Translate. Runs the automated checks + benchmark, then a live-website test on a real site (e.g. homedepot.com), and writes PRODUCT_EVAL.md. Use to evaluate the translation product or produce a fresh evaluation report.
---

# Glosa — Product Evaluation

Goal: produce **`PRODUCT_EVAL.md`** at the repo root — an evidence-first evaluation
of Glosa Live Translate. It combines (1) automated check + benchmark numbers and
(2) a **live-website test** on a real site you do not control (default:
`https://www.homedepot.com`).

Work through the steps in order. Do not fabricate results — every number and
sample comes from an actual run. If a step cannot be completed, say so in the
report rather than inventing data.

## Step 0 — Preconditions
1. Confirm both services are up:
   - AI service: `curl -sf localhost:8000/health`
   - Gateway: `curl -sf localhost:8787/health`
   If either is down, start them (see `README.md`), then resume.

## Step 1 — Automated checks + benchmark
Run these and capture the output:
```bash
python benchmark/bench.py --json benchmark/_bench.json     # SLA gate + latency + cost
python eval/eval.py                                        # checks -> eval/REPORT.md
```
Read `eval/report.json` and `benchmark/_bench.json` for the numbers.

## Step 2 — Live-website test
Pick a real, content-rich site you did NOT build. Default `https://www.homedepot.com`;
a product page works best. Load the widget there via the **Chrome extension** (`extension/`,
Load unpacked) — the extension injects the widget and proxies through its background worker,
so it works on strict-CSP sites. Console injection is **blocked by CSP on sites like
homedepot.com**, so don't rely on it for this test. Then click **Translate page**.

Capture, honestly:
- **Did it translate?** Whole page flipped to Mexican Spanish, layout intact?
- **Quality:** sample **6–8** original→translated string pairs. Judge es-MX register (not generic/Castilian), fluency, and that **numbers, prices ($), model/SKU codes are preserved**.
- **Coverage:** anything left in English (nav, dynamically-loaded content, image text)?
- **Cache:** click Restore, then Translate again — note the cache-hit badge and the latency drop.
- **Resilience:** did site CSP block injection? Any console errors? Did the page break?
- **Screenshot:** if browser tooling is available, capture before/after and reference the files.

> Note in the report if a strict-CSP site blocked the widget — that is a real finding, not a defect. If so, also test a permissive site and report both.

## Step 3 — Assess the product
Score each dimension **Pass / Partial / Fail** with one line of evidence:
translation accuracy · es-MX register · numbers/prices preserved · page coverage ·
cache effectiveness · latency vs SLA · error handling (no silent English) · resilience on a real site · UX polish.

## Step 4 — Write PRODUCT_EVAL.md
Fill `references/product-eval-template.md` with real data and write it to the
repo root as `PRODUCT_EVAL.md`. Keep it tight and evidence-first; embed the
automated-check summary from `eval/report.json` and the benchmark/cost numbers
from `benchmark/_bench.json`.

## Step 5 — Optional PDF
If a PDF is wanted, convert it:
- Prefer the `md-to-pdf` skill if available, or
- `pandoc PRODUCT_EVAL.md -o PRODUCT_EVAL.pdf` if pandoc is installed.
Report which was used; if neither is available, leave the `.md` and say so.

## Done
Surface any Fail/Partial dimensions worth fixing first.
