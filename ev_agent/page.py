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
  --red: #E01B3D;
  --blue: #1B4DE0;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 920px; margin: 0 auto; padding: 34px 30px 56px; }

header { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.brand {
  font-family: var(--mono); font-size: 13px; font-weight: 600;
  letter-spacing: 2.4px; color: var(--ink);
}
.rig { font-family: var(--mono); font-size: 11px; color: var(--muted); letter-spacing: .6px; }

.rule { height: 1px; background: var(--edge); margin: 18px 0 26px; }

.status { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); flex: none; }
.dot.live { background: var(--blue); animation: breathe 3.2s ease-in-out infinite; }
@keyframes breathe { 0%, 100% { opacity: 1; } 50% { opacity: .38; } }
.phase { font-size: 14px; color: var(--ink); }
.counts { font-family: var(--mono); font-size: 12px; color: var(--muted); letter-spacing: .4px; }

.card { border: 1px solid var(--edge); padding: 18px 20px; margin-top: 22px; }
.session-line { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.session { font-family: var(--mono); font-size: 13px; color: var(--ink); }
.elapsed { font-family: var(--mono); font-size: 12px; color: var(--muted); }

.rail { display: flex; gap: 20px; margin-top: 14px; flex-wrap: wrap; }
.step { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--muted); }
.step .pip { width: 7px; height: 7px; border-radius: 50%; border: 1px solid var(--muted); }
.step.past { color: var(--sans-ink); }
.step.past .pip { background: var(--blue); border-color: var(--blue); opacity: .45; }
.step.now { color: var(--ink); }
.step.now .pip { background: var(--blue); border-color: var(--blue); }

.tally { display: flex; gap: 22px; flex-wrap: wrap; margin-top: 22px; }
.tally b { font-family: var(--mono); font-weight: 600; font-size: 17px; color: var(--ink); }
.tally span { font-size: 12px; color: var(--sans-ink); margin-left: 7px; }
.tally .good b { color: var(--blue); }
.tally .bad b { color: var(--red); }

.label {
  font-family: var(--mono); font-size: 10.5px; letter-spacing: 1.6px;
  text-transform: uppercase; color: var(--muted); margin: 30px 0 12px;
}

.recent { border-top: 1px solid var(--edge); }
.recent div {
  display: flex; gap: 14px; padding: 8px 0; border-bottom: 1px solid var(--edge);
  font-size: 12.5px;
}
.recent .out { font-family: var(--mono); min-width: 108px; color: var(--sans-ink); }
.recent .out.good { color: var(--blue); }
.recent .out.bad { color: var(--red); }
.recent .det { color: var(--muted); font-family: var(--mono); font-size: 12px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.areas { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 2px 18px; }
.area { display: flex; align-items: center; gap: 9px; padding: 7px 0; cursor: pointer; font-size: 13.5px; }
.area input { appearance: none; width: 14px; height: 14px; border: 1px solid var(--muted);
  flex: none; cursor: pointer; background: var(--paper); }
.area input:checked { background: var(--blue); border-color: var(--blue); }
.area.custom { color: var(--sans-ink); }
.drop { border: none; background: none; color: var(--muted); cursor: pointer;
  font-family: var(--mono); font-size: 15px; line-height: 1; padding: 0 2px; }
.drop:hover { color: var(--red); }

.adder { display: flex; gap: 10px; margin-top: 14px; }
.adder input[type=text] {
  flex: 1; border: none; border-bottom: 1px solid var(--edge); padding: 7px 2px;
  font-family: var(--sans); font-size: 13.5px; color: var(--ink); background: none;
}
.adder input[type=text]:focus { outline: none; border-bottom-color: var(--blue); }
.adder button {
  border: 1px solid var(--edge); background: none; padding: 6px 16px; cursor: pointer;
  font-family: var(--mono); font-size: 11px; letter-spacing: 1px; text-transform: uppercase;
  color: var(--sans-ink);
}
.adder button:hover { border-color: var(--blue); color: var(--blue); }

.hint { font-size: 12.5px; color: var(--muted); margin-top: 12px; }
.saved { color: var(--blue); opacity: 0; transition: opacity .25s; font-family: var(--mono);
  font-size: 11px; letter-spacing: 1px; text-transform: uppercase; }
.saved.on { opacity: 1; }

.prefs { display: flex; gap: 30px; flex-wrap: wrap; align-items: center; margin-top: 6px; }
.pref { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--sans-ink); }
.pref select {
  border: none; border-bottom: 1px solid var(--edge); background: none; padding: 4px 2px;
  font-family: var(--mono); font-size: 12.5px; color: var(--ink); cursor: pointer;
}
.pref select:focus { outline: none; border-bottom-color: var(--blue); }

footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--edge);
  font-size: 12px; color: var(--muted); display: flex; justify-content: space-between; gap: 14px; }
footer code { font-family: var(--mono); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand" id="brand">E.V AGENT</div>
    <div class="rig" id="rig"></div>
  </header>
  <div class="rule"></div>

  <div class="status">
    <span class="dot" id="dot"></span>
    <span class="phase" id="phase"></span>
    <span class="counts" id="counts"></span>
  </div>

  <div class="card" id="card" hidden>
    <div class="session-line">
      <span class="session" id="session"></span>
      <span class="elapsed" id="elapsed"></span>
    </div>
    <div class="rail" id="rail"></div>
  </div>

  <div class="tally" id="tally"></div>

  <div class="label" id="lbl-recent"></div>
  <div class="recent" id="recent"></div>

  <div class="label" id="lbl-focus"></div>
  <div class="areas" id="areas"></div>
  <div class="adder">
    <input type="text" id="newArea" maxlength="48">
    <button id="addBtn"></button>
  </div>
  <div class="hint"><span id="focusHint"></span> <span class="saved" id="saved"></span></div>

  <div class="label" id="lbl-prefs"></div>
  <div class="prefs">
    <div class="pref"><span id="lbl-note"></span>
      <select id="noteLang"><option value="en">English</option><option value="pt-BR">Português (BR)</option></select>
    </div>
    <div class="pref"><span id="lbl-ui"></span>
      <select id="uiLang"><option value="en">English</option><option value="pt-BR">Português (BR)</option></select>
    </div>
  </div>

  <footer>
    <span id="privacy"></span>
    <code id="port"></code>
  </footer>
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

const t = (key) => (STRINGS[ui] && STRINGS[ui][key]) || STRINGS.en[key] || key;
const el = (id) => document.getElementById(id);

function elapsed(started) {
  if (!started) return "--:--";
  const began = Date.parse(started);
  if (isNaN(began)) return "--:--";
  const secs = Math.floor((Date.now() - began) / 1000);
  if (secs < 0 || secs > 86400) return "--:--";
  return String(Math.floor(secs / 60)).padStart(2, "0") + ":" + String(secs % 60).padStart(2, "0");
}

function paint(s) {
  latest = s;
  el("rig").textContent = s.backend + " · " + s.model;
  el("dot").className = "dot" + (s.running ? " live" : "");
  el("phase").textContent = s.running ? t("working") : t("idle");

  const bits = [];
  if (s.running && s.total) bits.push(s.done + " " + t("of") + " " + s.total);
  if (s.queued) bits.push(t("queue") + " " + s.queued);
  if (!s.running && s.queued) bits.push(t("run_drain"));
  el("counts").textContent = bits.join("   ");

  const live = s.running && s.current.session;
  el("card").hidden = !live;
  if (live) {
    el("session").textContent = s.current.session;
    el("elapsed").textContent = elapsed(s.current.started_at)
      + (s.current.specificity ? "   " + t("specificity") + " " + s.current.specificity.toFixed(2) : "");
    const at = STAGES.findIndex(([name]) => name === s.current.stage);
    el("rail").innerHTML = "";
    STAGES.forEach(([, key], i) => {
      const d = document.createElement("div");
      d.className = "step" + (i === at ? " now" : i < at ? " past" : "");
      d.innerHTML = '<span class="pip"></span>' + t(key);
      el("rail").appendChild(d);
    });
  }

  const tally = el("tally");
  tally.innerHTML = "";
  const entries = Object.entries(s.tally || {}).sort();
  if (!entries.length) {
    tally.innerHTML = '<span class="counts">' + t("nothing_yet") + "</span>";
  }
  entries.forEach(([name, n]) => {
    const box = document.createElement("div");
    box.className = GOOD.has(name) ? "good" : BAD.has(name) ? "bad" : "";
    const word = t("outcome_" + name) === "outcome_" + name ? name : t("outcome_" + name);
    box.innerHTML = "<b>" + n + "</b><span>" + word + "</span>";
    tally.appendChild(box);
  });

  const recent = el("recent");
  recent.innerHTML = "";
  (s.recent || []).forEach((item) => {
    const row = document.createElement("div");
    const out = document.createElement("span");
    const name = item.outcome || "";
    out.className = "out" + (GOOD.has(name) ? " good" : BAD.has(name) ? " bad" : "");
    out.textContent = t("outcome_" + name) === "outcome_" + name ? name : t("outcome_" + name);
    const det = document.createElement("span");
    det.className = "det";
    det.textContent = item.detail || item.session || "";
    row.append(out, det);
    recent.appendChild(row);
  });

  paintAreas(s);
  el("noteLang").value = s.note_language;
}

function paintAreas(s) {
  const box = el("areas");
  box.innerHTML = "";
  s.areas.forEach((area) => {
    const lab = document.createElement("label");
    lab.className = "area";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = s.focus.chosen.includes(area.slug);
    cb.dataset.slug = area.slug;
    cb.addEventListener("change", push);
    lab.append(cb, document.createTextNode(ui === "pt-BR" ? area.pt : area.en));
    box.appendChild(lab);
  });
  s.focus.custom.forEach((text) => {
    const lab = document.createElement("label");
    lab.className = "area custom";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = true;
    cb.dataset.custom = text;
    cb.addEventListener("change", push);
    const kill = document.createElement("button");
    kill.className = "drop";
    kill.textContent = "×";
    kill.title = t("remove");
    kill.addEventListener("click", (e) => { e.preventDefault(); dropCustom(text); });
    lab.append(cb, document.createTextNode(text), kill);
    box.appendChild(lab);
  });
  el("focusHint").textContent = s.focus.everything ? t("focus_everything") : "";
}

function gather() {
  const chosen = [...document.querySelectorAll("[data-slug]")].filter((c) => c.checked)
    .map((c) => c.dataset.slug);
  const custom = [...document.querySelectorAll("[data-custom]")].filter((c) => c.checked)
    .map((c) => c.dataset.custom);
  return { chosen, custom, note_language: el("noteLang").value };
}

async function push(body) {
  const payload = body && body.chosen ? body : gather();
  const res = await fetch("/api/focus?t=" + encodeURIComponent(TOKEN), {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) return;
  paint(await res.json());
  const flag = el("saved");
  flag.textContent = t("focus_saved");
  flag.classList.add("on");
  setTimeout(() => flag.classList.remove("on"), 1200);
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
  el("lbl-prefs").textContent = t("interface_language");
  el("lbl-note").textContent = t("note_language");
  el("lbl-ui").textContent = t("interface_language");
  el("addBtn").textContent = t("add");
  el("newArea").placeholder = t("add_your_own");
  el("privacy").textContent = t("local_only");
  el("port").textContent = location.host;
  el("uiLang").value = ui;
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
setInterval(() => { if (latest && latest.running) paint(latest); }, 1000);
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
