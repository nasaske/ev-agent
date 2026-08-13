from __future__ import annotations

import json

from . import i18n
from .config import Config
from .focus import EN, PT

_TEMPLATE = """<!doctype html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>E.V Agent</title>
<style>
:root {
  --paper: #FFFFFF;
  --ink: #0E1622;
  --sans-ink: #4B5B70;
  --muted: #94A3B8;
  --edge: #E6EBF0;
  --edge-soft: #F1F5F8;
  --red: #E01B3D;
  --blue: #1B4DE0;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--paper); }
body {
  color: var(--ink); font-family: var(--sans); font-size: 14px; line-height: 1.55;
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}
.wrap { max-width: 940px; margin: 0 auto; padding: 48px 40px 64px; }

/* masthead ------------------------------------------------------------ */
.mast { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.brand { font-family: var(--mono); font-size: 15px; font-weight: 600; letter-spacing: 3.4px; }
.tagline { font-size: 12.5px; color: var(--muted); margin-top: 5px; letter-spacing: .1px; }
.rig { text-align: right; font-family: var(--mono); font-size: 11px; color: var(--muted);
  letter-spacing: .7px; line-height: 1.8; white-space: nowrap; }
.rig .live-chip { display: inline-flex; align-items: center; gap: 7px; color: var(--sans-ink); }
.pulse { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); flex: none; }
.pulse.on { background: var(--blue); animation: breathe 3.2s ease-in-out infinite; }
@keyframes breathe { 0%,100% { opacity: 1 } 50% { opacity: .32 } }

.hair { height: 1px; background: var(--edge); margin: 26px 0 0; }

/* figures -------------------------------------------------------------- */
.figures { display: grid; grid-template-columns: repeat(4, 1fr); }
.fig { padding: 26px 0 24px; border-right: 1px solid var(--edge-soft); }
.fig:last-child { border-right: none; }
.fig b { display: block; font-family: var(--mono); font-weight: 500; font-size: 32px;
  line-height: 1; letter-spacing: -.6px; color: var(--ink); font-variant-numeric: tabular-nums; }
.fig.good b { color: var(--blue); }
.fig.bad b { color: var(--red); }
.fig.nil b { color: var(--muted); }
.fig span { display: block; margin-top: 9px; font-size: 11px; letter-spacing: 1.3px;
  text-transform: uppercase; color: var(--muted); font-family: var(--mono); }

/* current session ------------------------------------------------------ */
.card { border: 1px solid var(--edge); padding: 22px 24px 26px; margin-top: 4px; }
.card-head { display: flex; justify-content: space-between; align-items: baseline; gap: 14px; }
.session { font-family: var(--mono); font-size: 13.5px; letter-spacing: .2px; }
.meta { font-family: var(--mono); font-size: 12px; color: var(--muted);
  font-variant-numeric: tabular-nums; }

.rail { position: relative; display: flex; margin: 30px 0 4px; }
.track { position: absolute; left: 10%; right: 10%; top: 4px; height: 1px;
  background: var(--edge); }
.track em { position: absolute; left: 0; top: 0; height: 1px; background: var(--blue);
  width: 0; transition: width .5s cubic-bezier(.4,0,.2,1); display: block; }
.stop { position: relative; display: flex; flex-direction: column; align-items: center;
  gap: 10px; flex: 1; }
.stop i { width: 9px; height: 9px; border-radius: 50%; background: var(--paper);
  border: 1px solid var(--edge); display: block; position: relative; z-index: 1;
  transition: background .3s, border-color .3s; }
.stop u { font-style: normal; text-decoration: none; font-size: 10px; letter-spacing: 1.1px;
  text-transform: uppercase; font-family: var(--mono); color: var(--muted); }
.stop.past i { background: var(--blue); border-color: var(--blue); opacity: .35; }
.stop.past u { color: var(--sans-ink); }
.stop.now i { background: var(--blue); border-color: var(--blue);
  box-shadow: 0 0 0 4px rgba(27,77,224,.12); }
.stop.now u { color: var(--ink); }

/* sections ------------------------------------------------------------- */
.label { font-family: var(--mono); font-size: 10.5px; letter-spacing: 1.8px;
  text-transform: uppercase; color: var(--muted); margin: 44px 0 16px; }
.lede { font-size: 13px; color: var(--sans-ink); margin: 0 0 18px; max-width: 62ch; }

.recent { border-top: 1px solid var(--edge); margin-top: 14px; }
.row { display: grid; grid-template-columns: 116px 1fr; gap: 16px; padding: 11px 0;
  border-bottom: 1px solid var(--edge-soft); font-size: 12.5px; align-items: baseline; }
.row .out { font-family: var(--mono); font-size: 11px; letter-spacing: 1.1px;
  text-transform: uppercase; color: var(--muted); }
.row .out.good { color: var(--blue); }
.row .out.bad { color: var(--red); }
.row .det { font-family: var(--mono); font-size: 12px; color: var(--sans-ink);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.blank { color: var(--muted); font-size: 13px; padding: 16px 0; }

/* focus chips ---------------------------------------------------------- */
.chips { display: flex; flex-wrap: wrap; gap: 9px; }
.chip { display: inline-flex; align-items: center; gap: 9px; cursor: pointer;
  border: 1px solid var(--edge); padding: 8px 15px 8px 12px; font-size: 13px;
  color: var(--sans-ink); transition: border-color .18s, color .18s, background .18s;
  user-select: none; }
.chip:hover { border-color: var(--muted); }
.chip input { appearance: none; width: 12px; height: 12px; border: 1px solid var(--muted);
  border-radius: 50%; flex: none; cursor: pointer; transition: background .18s, border-color .18s; }
.chip input:checked { background: var(--blue); border-color: var(--blue);
  box-shadow: inset 0 0 0 2px var(--paper); }
.chip.on { border-color: var(--blue); color: var(--ink); background: rgba(27,77,224,.035); }
.chip .kill { border: none; background: none; color: var(--muted); cursor: pointer;
  font-family: var(--mono); font-size: 15px; line-height: 1; padding: 0 0 0 3px; }
.chip .kill:hover { color: var(--red); }

.adder { display: flex; gap: 12px; margin-top: 18px; max-width: 460px; }
.adder input[type=text] { flex: 1; border: none; border-bottom: 1px solid var(--edge);
  padding: 8px 2px; font-family: var(--sans); font-size: 13.5px; color: var(--ink);
  background: none; transition: border-color .18s; }
.adder input[type=text]::placeholder { color: var(--muted); }
.adder input[type=text]:focus { outline: none; border-bottom-color: var(--blue); }
.adder button { border: 1px solid var(--edge); background: none; padding: 7px 18px;
  cursor: pointer; font-family: var(--mono); font-size: 10.5px; letter-spacing: 1.4px;
  text-transform: uppercase; color: var(--sans-ink); transition: border-color .18s, color .18s; }
.adder button:hover { border-color: var(--blue); color: var(--blue); }

.note { font-size: 12.5px; color: var(--muted); margin-top: 14px; display: flex;
  align-items: center; gap: 12px; }
.saved { color: var(--blue); font-family: var(--mono); font-size: 10.5px; letter-spacing: 1.4px;
  text-transform: uppercase; opacity: 0; transition: opacity .3s; }
.saved.on { opacity: 1; }

/* preferences ---------------------------------------------------------- */
.prefs { display: flex; gap: 40px; flex-wrap: wrap; }
.pref { display: flex; flex-direction: column; gap: 5px; }
.pref span { font-size: 12.5px; letter-spacing: 0; text-transform: none;
  color: var(--sans-ink); font-family: var(--sans); }
.pref select { border: none; border-bottom: 1px solid var(--edge); background: none;
  padding: 5px 18px 5px 2px; font-family: var(--sans); font-size: 13.5px; color: var(--ink);
  cursor: pointer; transition: border-color .18s; }
.pref select:focus { outline: none; border-bottom-color: var(--blue); }

footer { margin-top: 54px; padding-top: 18px; border-top: 1px solid var(--edge);
  font-size: 12px; color: var(--muted); display: flex; justify-content: space-between;
  gap: 16px; align-items: baseline; }
footer code { font-family: var(--mono); font-size: 11px; letter-spacing: .6px; }

@media (max-width: 700px) {
  .wrap { padding: 32px 22px 48px; }
  .figures { grid-template-columns: repeat(2, 1fr); }
  .fig:nth-child(2) { border-right: none; }
  .stop u { display: none; }
}
</style>
</head>
<body>
<div class="wrap">
  <div class="mast">
    <div>
      <div class="brand">E.V AGENT</div>
      <div class="tagline" id="tagline"></div>
    </div>
    <div class="rig">
      <div class="live-chip"><span class="pulse" id="pulse"></span><span id="phase"></span></div>
      <div id="rig"></div>
    </div>
  </div>
  <div class="hair"></div>

  <div class="figures" id="figures"></div>

  <div class="card" id="card" hidden>
    <div class="card-head">
      <span class="session" id="session"></span>
      <span class="meta" id="meta"></span>
    </div>
    <div class="rail" id="rail"><div class="track"><em id="fill"></em></div></div>
  </div>

  <div class="label" id="lbl-recent"></div>
  <div class="recent" id="recent"></div>

  <div class="label" id="lbl-focus"></div>
  <p class="lede" id="focus-lede"></p>
  <div class="chips" id="areas"></div>
  <div class="adder">
    <input type="text" id="newArea" maxlength="48">
    <button id="addBtn"></button>
  </div>
  <div class="note"><span id="focusHint"></span><span class="saved" id="saved"></span></div>

  <div class="label" id="lbl-prefs"></div>
  <div class="prefs">
    <label class="pref"><span id="lbl-note"></span>
      <select id="noteLang"><option value="en">English</option><option value="pt-BR">Português (BR)</option></select>
    </label>
    <label class="pref"><span id="lbl-ui"></span>
      <select id="uiLang"><option value="en">English</option><option value="pt-BR">Português (BR)</option></select>
    </label>
  </div>

  <footer><span id="privacy"></span><code id="port"></code></footer>
</div>
<script>
const TOKEN = __TOKEN__;
const STRINGS = __STRINGS__;
const STAGES = [
  ["reading", "stage_reading"], ["scrubbing", "stage_scrubbing"],
  ["weighing", "stage_weighing"], ["asking model", "stage_asking"],
  ["writing", "stage_writing"]
];
const GOOD = new Set(["written"]);
const BAD = new Set(["quarantined", "failed"]);

let ui = localStorage.getItem("ev-ui-lang") || __LANGJS__;
let latest = null;

const t = (k) => (STRINGS[ui] && STRINGS[ui][k]) || STRINGS.en[k] || k;
const el = (id) => document.getElementById(id);
const word = (name) => t("outcome_" + name) === "outcome_" + name ? name : t("outcome_" + name);

function elapsed(started) {
  if (!started) return "--:--";
  const began = Date.parse(started);
  if (isNaN(began)) return "--:--";
  const secs = Math.floor((Date.now() - began) / 1000);
  if (secs < 0 || secs > 86400) return "--:--";
  return String(Math.floor(secs / 60)).padStart(2, "0") + ":" + String(secs % 60).padStart(2, "0");
}

function figures(s) {
  const tally = s.tally || {};
  return [
    { n: tally.written || 0, key: "outcome_written", tone: tally.written ? "good" : "nil" },
    { n: tally.quarantined || 0, key: "outcome_quarantined", tone: tally.quarantined ? "bad" : "nil" },
    { n: s.candidates || 0, key: "fig_inbox", tone: s.candidates ? "" : "nil" },
    { n: s.queued || 0, key: "queue", tone: s.queued ? "" : "nil" }
  ];
}

function paint(s) {
  latest = s;
  el("rig").textContent = s.backend + " · " + s.model;
  el("pulse").className = "pulse" + (s.running ? " on" : "");
  el("phase").textContent = s.running
    ? t("working") + (s.total ? "  " + s.done + " " + t("of") + " " + s.total : "")
    : t("idle");
  el("tagline").textContent = t("tagline");

  const box = el("figures");
  box.innerHTML = "";
  figures(s).forEach((f) => {
    const d = document.createElement("div");
    d.className = "fig " + f.tone;
    d.innerHTML = "<b>" + f.n + "</b><span></span>";
    d.querySelector("span").textContent = t(f.key);
    box.appendChild(d);
  });

  const live = s.running && s.current.session;
  el("card").hidden = !live;
  if (live) {
    el("session").textContent = s.current.session;
    el("meta").textContent = elapsed(s.current.started_at)
      + (s.current.specificity ? "   " + t("specificity") + " " + s.current.specificity.toFixed(2) : "");
    const at = STAGES.findIndex(([name]) => name === s.current.stage);
    const rail = el("rail");
    [...rail.querySelectorAll(".stop")].forEach((n) => n.remove());
    STAGES.forEach(([, key], i) => {
      const stop = document.createElement("div");
      stop.className = "stop" + (i === at ? " now" : i < at ? " past" : "");
      stop.innerHTML = "<i></i><u></u>";
      stop.querySelector("u").textContent = t(key);
      rail.appendChild(stop);
    });
    const pct = at <= 0 ? 0 : (at / (STAGES.length - 1)) * 100;
    el("fill").style.width = pct + "%";
  }

  const recent = el("recent");
  recent.innerHTML = "";
  const items = s.recent || [];
  if (!items.length) {
    const blank = document.createElement("div");
    blank.className = "blank";
    blank.textContent = t("nothing_yet");
    recent.appendChild(blank);
  }
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "row";
    const out = document.createElement("span");
    const name = item.outcome || "";
    out.className = "out" + (GOOD.has(name) ? " good" : BAD.has(name) ? " bad" : "");
    out.textContent = word(name);
    const det = document.createElement("span");
    det.className = "det";
    det.textContent = item.detail || item.session || "";
    row.append(out, det);
    recent.appendChild(row);
  });

  paintAreas(s);
  el("noteLang").value = s.note_language;
}

function chip(checked, text, dataset, removable) {
  const lab = document.createElement("label");
  lab.className = "chip" + (checked ? " on" : "");
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = checked;
  Object.assign(cb.dataset, dataset);
  cb.addEventListener("change", () => push());
  lab.append(cb, document.createTextNode(text));
  if (removable) {
    const kill = document.createElement("button");
    kill.className = "kill";
    kill.type = "button";
    kill.textContent = "×";
    kill.title = t("remove");
    kill.addEventListener("click", (e) => { e.preventDefault(); dropCustom(text); });
    lab.appendChild(kill);
  }
  return lab;
}

function paintAreas(s) {
  const box = el("areas");
  box.innerHTML = "";
  s.areas.forEach((a) => box.appendChild(
    chip(s.focus.chosen.includes(a.slug), ui === "pt-BR" ? a.pt : a.en, { slug: a.slug }, false)
  ));
  s.focus.custom.forEach((text) => box.appendChild(
    chip(true, text, { custom: text }, true)
  ));
  el("focusHint").textContent = s.focus.everything ? t("focus_everything") : "";
}

function gather() {
  const pick = (sel, key) => [...document.querySelectorAll(sel)]
    .filter((c) => c.checked).map((c) => c.dataset[key]);
  return {
    chosen: pick("[data-slug]", "slug"),
    custom: pick("[data-custom]", "custom"),
    note_language: el("noteLang").value
  };
}

async function push(body) {
  const payload = body && body.chosen ? body : gather();
  let res;
  try {
    res = await fetch("/api/focus?t=" + encodeURIComponent(TOKEN), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch (err) { return; }
  if (!res.ok) return;
  paint(await res.json());
  const flag = el("saved");
  flag.textContent = t("focus_saved");
  flag.classList.add("on");
  setTimeout(() => flag.classList.remove("on"), 1400);
}

function dropCustom(text) {
  const body = gather();
  body.custom = body.custom.filter((c) => c !== text);
  push(body);
}

function addCustom() {
  const field = el("newArea");
  const value = field.value.trim();
  if (!value) return;
  const body = gather();
  if (!body.custom.includes(value)) body.custom.push(value);
  field.value = "";
  push(body);
}

function chrome() {
  el("lbl-recent").textContent = t("recent");
  el("lbl-focus").textContent = t("focus");
  el("focus-lede").textContent = t("focus_lede");
  el("lbl-prefs").textContent = t("preferences");
  el("lbl-note").textContent = t("note_language");
  el("lbl-ui").textContent = t("interface_language");
  el("addBtn").textContent = t("add");
  el("newArea").placeholder = t("add_your_own");
  el("privacy").textContent = t("local_only");
  el("port").textContent = location.host;
  el("uiLang").value = ui;
  document.title = "E.V Agent";
  if (latest) paint(latest);
}

el("addBtn").addEventListener("click", addCustom);
el("newArea").addEventListener("keydown", (e) => { if (e.key === "Enter") addCustom(); });
el("noteLang").addEventListener("change", () => push());
el("uiLang").addEventListener("change", (e) => {
  ui = e.target.value;
  localStorage.setItem("ev-ui-lang", ui);
  document.documentElement.lang = ui;
  chrome();
});

async function tick() {
  try {
    const res = await fetch("/api/state?t=" + encodeURIComponent(TOKEN));
    if (res.ok) paint(await res.json());
  } catch (err) { /* server closed */ }
}

chrome();
tick();
setInterval(tick, 1000);
</script>
</body>
</html>
"""


def render(token: str, config: Config) -> str:
    language = i18n.normalise(config.language)
    strings = {EN: i18n.table(EN), PT: i18n.table(PT)}
    return (
        _TEMPLATE.replace("__TOKEN__", json.dumps(token))
        .replace("__STRINGS__", json.dumps(strings, ensure_ascii=False))
        .replace("__LANGJS__", json.dumps(language))
        .replace("__LANG__", language)
    )
