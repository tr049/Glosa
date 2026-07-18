/*
 * Glosa — console loader
 * -----------------------------------
 * Fastest way to see the widget on ANY page: open DevTools (Cmd/Ctrl+Opt+J),
 * paste this whole snippet into the Console, hit Enter.
 *
 * It fetches the widget from the Node gateway (which serves it at /widget.js)
 * and injects it into the current page. The gateway must be running first.
 *
 * To point at a different gateway, set window.GLOSA_CONFIG before pasting, e.g.
 *   window.GLOSA_CONFIG = { API_URL: "http://localhost:8787" }
 */
(async function () {
  const API = (window.GLOSA_CONFIG && window.GLOSA_CONFIG.API_URL) || "http://localhost:8787";
  try {
    console.log("🔄 Loading Glosa translate widget from", API + "/widget.js");
    const res = await fetch(API + "/widget.js");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const code = await res.text();
    const s = document.createElement("script");
    s.textContent = code;
    document.head.appendChild(s);
    console.log("✅ Widget injected. Look for the 🌐 button bottom-right.");
  } catch (err) {
    console.error("❌ Could not load widget:", err);
    console.log("Is your Node gateway running and serving /widget.js at " + API + "?");
  }
})();
