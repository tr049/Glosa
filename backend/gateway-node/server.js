/*
 * FDE · Assignment 1 · Node Gateway  (the "software backend")
 * ==========================================================
 * This is the ONLY server the browser widget talks to. Its jobs:
 *   - serve the widget file at /widget.js
 *   - accept translation requests from the widget (CORS, validation)
 *   - forward them to the Python AI service
 *   - expose /health and /stats
 *   - log every request
 *
 * It is ~90% done
 * Everything else works out of the box.
 *
 * Run:  npm install && npm start      (needs Node 18+ for global fetch)
 */
const express = require("express");
const cors = require("cors");
const path = require("path");
const fs = require("fs");
const crypto = require("crypto");
require("dotenv").config();

const PORT = process.env.PORT || 8787;
const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8000";
const WIDGET_PATH = path.join(__dirname, "..", "..", "widget", "translation-widget.js");

// --- structured logging --------------------------------------------------
// Write one JSON line per event to BOTH stdout and gateway.log. Writing to a
// real file (not just console) is required: the grader greps this file for the
// X-Request-Id, and `npm start` does not pipe stdout anywhere.
const LOG_FILE = path.join(__dirname, "gateway.log");
function logEvent(obj) {
  const line = JSON.stringify({ ts: new Date().toISOString(), ...obj });
  console.log(line);
  try {
    fs.appendFileSync(LOG_FILE, line + "\n");
  } catch (err) {
    console.error("gateway.log write failed:", err.message);
  }
}

const app = express();
const startedAt = Date.now();

// --- middleware ----------------------------------------------------------
app.use(cors()); // dev: allow every origin so the widget works on any page
app.use(express.json({ limit: "1mb" }));

// --- request logging + trace correlation ---------------------------------
// Reuse an inbound X-Request-Id or mint a fresh one, stash it on req so the
// proxy can forward it to the AI service, echo it back to the caller, and log
// one structured line per request once it finishes.
app.use((req, res, next) => {
  const t0 = Date.now();
  const requestId = req.headers["x-request-id"] || crypto.randomUUID();
  req.requestId = requestId;
  res.setHeader("X-Request-Id", requestId);
  res.on("finish", () => {
    logEvent({
      requestId,
      method: req.method,
      url: req.originalUrl,
      status: res.statusCode,
      durationMs: Date.now() - t0,
    });
  });
  next();
});

// --- serve the widget to the console loader ------------------------------
app.get("/widget.js", (req, res) => {
  res.type("application/javascript");
  res.sendFile(WIDGET_PATH);
});

// --- helper: forward a request to the Python AI service ------------------
// Forward `body` as JSON to the Python AI service and return the parsed JSON.
// Throws on a non-2xx so route handlers can turn it into a 502 (fail-loud —
// never serve the untranslated input). Forwards x-request-id for trace
// correlation. (Node 18+ has global fetch — no import needed.)
async function callAiService(path, body, requestId) {
  const headers = { "Content-Type": "application/json" };
  if (requestId) headers["x-request-id"] = requestId; // forward for trace correlation
  const res = await fetch(AI_SERVICE_URL + path, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("AI service " + res.status);
  return res.json();
}

// --- routes the widget calls ---------------------------------------------
app.post("/translate", async (req, res) => {
  const { text, target } = req.body || {};
  if (typeof text !== "string") return res.status(400).json({ error: "`text` (string) is required" });
  try {
    const data = await callAiService("/translate", { text, target: target || "es-MX" }, req.requestId);
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "AI service error: " + err.message });
  }
});

app.post("/translate/batch", async (req, res) => {
  const { texts, target } = req.body || {};
  if (!Array.isArray(texts)) return res.status(400).json({ error: "`texts` (array) is required" });
  try {
    const data = await callAiService("/translate/batch", { texts, target: target || "es-MX" }, req.requestId);
    res.json(data);
  } catch (err) {
    res.status(502).json({ error: "AI service error: " + err.message });
  }
});

app.get("/health", async (req, res) => {
  const uptimeSec = Math.round((Date.now() - startedAt) / 1000);
  let ai = "unreachable";
  try {
    const r = await fetch(AI_SERVICE_URL + "/health");
    ai = r.ok ? await r.json() : "error";
  } catch (_) {}
  res.json({ status: "ok", gatewayUptimeSec: uptimeSec, aiService: ai });
});

app.get("/stats", async (req, res) => {
  try {
    const r = await fetch(AI_SERVICE_URL + "/stats");
    res.json(await r.json());
  } catch (err) {
    res.status(502).json({ error: "AI service error: " + err.message });
  }
});

app.listen(PORT, () => {
  console.log(`FDE gateway on http://localhost:${PORT}  →  AI service ${AI_SERVICE_URL}`);
  console.log(`Widget served at http://localhost:${PORT}/widget.js`);
});
