/* Ultra HDR front end. Talks to Python through pywebview.api; Python pushes events via app.on(). */
"use strict";

const $ = (s) => document.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtNits = (n) => n >= 1000 ? (n / 1000).toFixed(1) + "k" : Math.round(n);

const S = {
  settings: {},
  files: new Map(),      // id -> record
  order: [],
  selected: null,
  watching: false,
  batch: null,           // Set of ids in the current conversion batch
  inspTarget: "full",    // full | ig | heat
  api: null,
};
let previewSeq = 0, previewTimer = null, previewBusy = false, previewAgain = false;

/* ------------------------------------------------------------------ boot */
window.addEventListener("pywebviewready", async () => {
  S.api = window.pywebview.api;
  const st = await S.api.state();
  applyState(st);
  bindUI();
  renderAll();
});

function applyState(st) {
  S.settings = st.settings;
  S.watching = st.watching;
  S.version = st.version; S.codec = st.codec; S.packaged = !!st.packaged;
  appendLog(new Date().toTimeString().slice(0, 8), `UltraShot ${st.version} ready · libultrahdr via imagecodecs ${st.codec}` + (st.watching ? ` · watching ${st.settings.watch_dir}` : ""));
  S.files.clear(); S.order = [];
  for (const f of st.files) { S.files.set(f.id, f); S.order.push(f.id); }
  $("#ver").textContent = "v" + st.version;
  applyTheme();
}

function applyTheme() {
  const t = S.settings.theme;
  const dark = t === "dark" || (t === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.body.classList.toggle("theme-dark", dark);
  document.body.classList.toggle("theme-light", !dark);
}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);

/* ------------------------------------------------------------------ events from Python */
window.app = {
  on(name, p) {
    switch (name) {
      case "file": {
        const had = S.files.has(p.id);
        S.files.set(p.id, p);
        if (!had) S.order.push(p.id);
        had ? updateCard(p) : renderGrid();
        if (S.selected === p.id) renderInspectorInfo(p);
        updateProgress();
        updateConvertButton();
        break;
      }
      case "files": { for (const f of p) { if (!S.files.has(f.id)) S.order.push(f.id); S.files.set(f.id, f); } renderGrid(); updateProgress(); break; }
      case "removed": S.files.delete(p); S.order = S.order.filter((i) => i !== p); if (S.selected === p) closeInspector(); renderGrid(); updateProgress(); break;
      case "cleared": { const keep = new Set(p); for (const id of [...S.files.keys()]) if (!keep.has(id)) S.files.delete(id); S.order = S.order.filter((i) => keep.has(i)); closeInspector(); S.batch = null; renderGrid(); updateProgress(); break; }
      case "log": appendLog(p.t, p.msg); break;
      case "toast": toast(p.msg, p.kind); break;
      case "watch": S.watching = p.on; S.settings.watch = p.on; renderWatch(); renderSettings(); break;
      case "settings": S.settings = p; renderChips(); renderWatch(); renderSettings(); renderInspectorControls(); break;
      case "idle": updateProgress(true); break;
    }
  },
};

/* ------------------------------------------------------------------ rendering */
function renderAll() { renderGrid(); renderChips(); renderWatch(); renderInspectorControls(); updateProgress(); }

function renderGrid() {
  const grid = $("#grid"), empty = $("#empty");
  const has = S.order.length > 0;
  grid.classList.toggle("hidden", !has);
  empty.classList.toggle("hidden", has);
  grid.innerHTML = "";
  for (const id of S.order) grid.appendChild(cardFor(S.files.get(id)));
  updateConvertButton();
}

function pendingIds() {
  const redo = !!S.settings.overwrite;
  return S.order.filter((id) => { const f = S.files.get(id); return f && (f.status === "queued" || f.status === "failed" || (redo && f.status !== "working")); });
}

function updateConvertButton() {
  const b = $("#btnConvert"), pending = pendingIds().length, total = S.order.length;
  const working = S.order.some((id) => S.files.get(id)?.status === "working");
  b.disabled = pending === 0;
  if (!total) b.textContent = "Convert";
  else if (pending) b.textContent = pending === 1 ? "Convert 1 file" : `Convert ${pending} files`;
  else b.textContent = working ? "Converting…" : "All converted";
  $("#btnClearDone").classList.toggle("hidden", !S.order.some((id) => ["done", "skipped"].includes(S.files.get(id)?.status)));
}

function cardFor(f) {
  const c = el("div", "card" + (S.selected === f.id ? " selected" : ""));
  c.dataset.id = f.id;
  c.innerHTML = cardInner(f);
  c.addEventListener("click", () => select(f.id));
  c.addEventListener("dblclick", () => openResult(f.id));
  return c;
}

function cardInner(f) {
  const st = f.stats;
  const thumb = f.thumb ? `<img src="${f.thumb}" alt="">` : `<div class="skeleton"></div>`;
  const statusText = { queued: "Ready", working: "Converting", done: "Done", skipped: "Already converted", failed: "Failed" }[f.status] || f.status;
  const badge = `<div class="badge ${f.status}">${f.status === "working" ? '<span class="spinner"></span>' : ""}${statusText}</div>`;
  const peak = st ? `<div class="peak ${st.peak > 600 ? "hot" : ""}">${fmtNits(st.peak)} nits</div>` : "";
  const dim = st ? `${st.w}×${st.h} · ${st.transfer}` : (f.status === "failed" ? esc(f.error) : "reading…");
  const meter = st ? Math.min(100, Math.round(100 * Math.log2(Math.max(1, st.peak / 203)) / Math.log2(4000 / 203))) : 0;
  return `<div class="thumb">${thumb}${badge}${peak}</div>
    <div class="meta"><div class="name" title="${esc(f.path)}">${esc(f.name)}</div>
    <div class="dim"><span>${dim}</span><span>${st ? hdrLabel(st) : ""}</span></div>
    <div class="meter"><i style="width:${meter}%"></i></div></div>`;
}

function hdrLabel(st) {
  if (st.peak <= 210) return "SDR range";
  if (st.above_sdr >= 5) return "strong HDR";
  if (st.above_sdr >= 0.5) return "HDR";
  return "subtle HDR";
}

function updateCard(f) {
  const c = document.querySelector(`.card[data-id="${f.id}"]`);
  if (c) c.innerHTML = cardInner(f); else renderGrid();
}

function renderChips() {
  const s = S.settings;
  const outs = [s.make_full && "Full size", s.make_ig && "Instagram"].filter(Boolean);
  $("#chipOut").innerHTML = `<b>${outs.length ? outs.join(" + ") : "No outputs"}</b>`;
  $("#chipSave").innerHTML = s.save_mode === "folder" && s.save_dir ? `Save to <b>${esc(s.save_dir.split(/[\\/]/).pop())}</b>` : `<b>Next to originals</b>`;
  const look = lookName(s);
  $("#chipLook").innerHTML = `SDR look <b>${look}</b>`;
}
const LOOKS = [
  ["Neutral", 0, 0.6, "matches the game's SDR output"],
  ["Brighter", 0.5, 0.6, "+½ stop for dark scenes"],
  ["Punchy", 0.3, 0.45, "brighter mids, softer highlights"],
  ["Flat", 0, 0.3, "keeps the most highlight detail"],
];
function lookName(s) {
  if (s.auto_sdr) return "Automatic";
  for (const [n, e, k] of LOOKS) if (Math.abs(s.exposure - e) < 1e-6 && Math.abs(s.knee - k) < 1e-6) return n;
  return `${s.exposure >= 0 ? "+" : ""}${s.exposure.toFixed(2)} / ${s.knee.toFixed(2)}`;
}

function renderWatch() {
  const pill = $("#watchPill");
  pill.classList.toggle("on", S.watching);
  const dir = (S.settings.watch_dir || "").split(/[\\/]/).filter(Boolean).pop() || "folder";
  $("#watchText").textContent = S.watching ? `Watching ${dir}` : "Watch folder off";
}

function updateProgress(idle) {
  const p = $("#progress");
  if (!S.batch) { p.classList.add("hidden"); return; }
  let done = 0, total = 0, failed = 0;
  for (const id of S.batch) { const f = S.files.get(id); if (!f) continue; total++; if (["done", "skipped", "failed"].includes(f.status)) done++; if (f.status === "failed") failed++; }
  p.classList.remove("hidden");
  p.querySelector(".fill").style.width = total ? (100 * done / total) + "%" : "0%";
  p.querySelector(".ptext").textContent = done < total ? `${done} / ${total}` : `${total} done${failed ? `, ${failed} failed` : ""}`;
  if (done >= total && total) {
    const b = S.batch; setTimeout(() => { if (S.batch === b) { S.batch = null; p.classList.add("hidden"); } }, 4000);
    if (idle !== true) return;
  }
}

/* ------------------------------------------------------------------ inspector */
function select(id) {
  S.selected = id;
  document.querySelectorAll(".card").forEach((c) => c.classList.toggle("selected", c.dataset.id === id));
  const f = S.files.get(id);
  $("#inspName").textContent = f.name;
  openPane("inspector");
  renderInspectorControls();
  renderInspectorInfo(f);
  requestPreview();
}
function closeInspector() { S.selected = null; closePane("inspector"); document.querySelectorAll(".card.selected").forEach((c) => c.classList.remove("selected")); }

function renderInspectorControls() {
  const s = S.settings;
  $("#rExposure").value = s.exposure; $("#vExposure").textContent = (s.exposure >= 0 ? "+" : "") + Number(s.exposure).toFixed(2) + " st";
  $("#rKnee").value = s.knee; $("#vKnee").textContent = Number(s.knee).toFixed(2);
  $("#rCx").value = s.crop_x; $("#vCx").textContent = s.crop_x + "%";
  $("#rCy").value = s.crop_y; $("#vCy").textContent = s.crop_y + "%";
  $("#inspCrop").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === (s.ig_crop || "none")));
  $("#inspTarget").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === S.inspTarget));
  $("#cropFields").style.display = S.inspTarget === "ig" ? "" : "none";
  const dis = !!s.auto_sdr;
  $("#rExposure").disabled = dis; $("#rKnee").disabled = dis;
}

function renderInspectorInfo(f) {
  const st = f.stats, box = $("#inspInfo");
  if (!st) { box.innerHTML = `<div class="kv"><div class="k">Status</div><div class="v">${esc(f.error || "reading…")}</div></div>`; return; }
  const kv = (k, v) => `<div class="kv"><div class="k">${k}</div><div class="v">${v}</div></div>`;
  box.innerHTML = kv("Resolution", `${st.w}×${st.h}`) + kv("Source", st.transfer) +
    kv("Peak", `${Math.round(st.peak)} nits`) + kv("Bright 0.5%", `${Math.round(st.p99)} nits`) +
    kv("Above SDR white", `${st.above_sdr.toFixed(2)}%`) + kv("Above 1000 nits", `${st.above_1k.toFixed(2)}%`) +
    kv("Status", { queued: "Ready to convert", working: "Converting…", done: "Converted", skipped: "Outputs already exist", failed: esc(f.error || "failed") }[f.status] || f.status) +
    kv("Outputs", f.outputs?.length ? f.outputs.map((o) => esc(o.split(/[\\/]/).slice(-2).join("\\"))).join("<br>") : "—");
  const hasOut = !!(f.outputs && f.outputs.length);
  $("#inspReveal").disabled = !hasOut; $("#inspView").disabled = !hasOut; $("#inspOpen").disabled = !hasOut;
}

function requestPreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(doPreview, 60);
}
async function doPreview() {
  if (!S.selected) return;
  if (previewBusy) { previewAgain = true; return; }
  previewBusy = true;
  const seq = ++previewSeq, s = S.settings, id = S.selected;
  const opts = { exposure: s.exposure, knee: s.knee, auto_sdr: s.auto_sdr, heat: S.inspTarget === "heat", width: 1100 };
  if (S.inspTarget === "ig") Object.assign(opts, { crop: s.ig_crop || "none", cx: s.crop_x, cy: s.crop_y, width: Math.min(1100, s.ig_width) });
  $("#inspLoading").style.display = "";
  try {
    const r = await S.api.preview(id, opts);
    if (seq === previewSeq && r && r.url) {
      $("#inspImg").src = r.url;
      $("#inspBadge").textContent = S.inspTarget === "heat" ? "orange > 203 nits · pink > 600 nits" : S.inspTarget === "ig" ? `Instagram ${r.w}×${r.h}` : `SDR base · ${r.w}×${r.h} preview`;
      if (r.stats && S.files.get(id)) { S.files.get(id).stats = r.stats; }
    } else if (r && r.error) toast(r.error, "err");
  } catch (e) { toast("preview failed: " + e, "err"); }
  $("#inspLoading").style.display = "none";
  previewBusy = false;
  if (previewAgain) { previewAgain = false; requestPreview(); }
}

/* ------------------------------------------------------------------ settings page */
const SECTIONS = [
  { title: "General", rows: [
    { key: "theme", lbl: "Theme", type: "seg", opts: [["system", "System"], ["light", "Light"], ["dark", "Dark"]] },
    { key: "notifications", lbl: "Notifications", hint: "Notify when images are converted in the background", type: "toggle" },
    { key: "keep_list", lbl: "Remember the list", hint: "Restore the cards and their results at the next launch", type: "toggle" },
  ]},
  { title: "Output", rows: [
    { key: "make_full", lbl: "Full size", hint: "Full-resolution Ultra HDR JPEG, quality 100, 4:4:4", type: "toggle" },
    { key: "full_dir", lbl: "Subfolder", type: "text", sub: true, dep: "make_full" },
    { key: "make_ig", lbl: "Instagram", hint: "Downscaled copy that still carries the full gain map", type: "toggle" },
    { key: "ig_width", lbl: "Width", hint: "Instagram re-encodes anything wider than 1440 px", type: "number", min: 320, max: 8192, step: 10, suffix: "px", sub: true, dep: "make_ig" },
    { key: "ig_crop", lbl: "Crop", hint: "Instagram's upload crop strips HDR, so crop here and choose “original” when posting", type: "seg", opts: [["none", "Original"], ["4:5", "4:5"], ["1:1", "1:1"], ["16:9", "16:9"], ["9:16", "9:16"], ["1.91:1", "1.91:1"]], sub: true, dep: "make_ig" },
    { key: "ig_dir", lbl: "Subfolder", type: "text", sub: true, dep: "make_ig" },
  ]},
  { title: "Saving", rows: [
    { key: "save_mode", lbl: "Save to", type: "seg", opts: [["beside", "Next to each original"], ["folder", "Fixed folder"]] },
    { key: "save_dir", lbl: "Folder", type: "folder", sub: true, dep: (s) => s.save_mode === "folder" },
    { key: "keep_date", lbl: "Keep the capture date", hint: "Outputs get the screenshot's modified time", type: "toggle" },
    { key: "overwrite", lbl: "Overwrite existing outputs", hint: "Off: files that already exist are skipped", type: "toggle" },
    { key: "suffix", lbl: "File name suffix", hint: "e.g. _hdr", type: "text" },
    { type: "example" },
  ]},
  { title: "Watch folder", rows: [
    { key: "watch", lbl: "Convert new captures automatically", hint: "Each new .jxl / .jxr saved in the folder is converted once it is fully written", type: "toggle" },
    { key: "watch_dir", lbl: "Folder", type: "folder", sub: true },
    { key: "watch_subfolders", lbl: "Include subfolders", hint: "NVIDIA App saves each game's screenshots in its own subfolder", type: "toggle", sub: true },
    { key: "watch_existing", lbl: "Also convert files already there", hint: "Off: only captures made after watching starts", type: "toggle", sub: true },
    { key: "settle", lbl: "Wait until the file is stable for", type: "number", min: 0.5, max: 60, step: 0.5, suffix: "s", sub: true },
  ]},
  { title: "Background", rows: [
    { key: "tray", lbl: "Keep running in the tray when the window is closed", hint: "Right-click the tray icon to quit", type: "toggle" },
    { key: "startup", lbl: "Start with Windows, in the tray", hint: "Adds an UltraShot shortcut to your Startup folder; the watch folder starts with it", type: "toggle" },
    { key: "explorer_menu", lbl: "“Convert with UltraShot” in Explorer's right-click menu", hint: "For .jxl and .jxr files (current user only)", type: "toggle" },
  ]},
  { title: "Fine-tuning", rows: [
    { type: "note", text: "The HDR layer is always written untouched. These settings only shape the SDR base image (what SDR screens and thumbnails show) and how the gain map is encoded." },
    { key: "auto_sdr", lbl: "Automatic SDR base", hint: "Let libultrahdr tone-map the base image (ignores exposure and knee)", type: "toggle" },
    { key: "exposure", lbl: "SDR exposure", type: "range", min: -3, max: 3, step: 0.05, fmt: (v) => (v >= 0 ? "+" : "") + Number(v).toFixed(2) + " st", dep: (s) => !s.auto_sdr },
    { key: "knee", lbl: "Highlight knee", hint: "Where the roll-off starts (1.0 = 203 nits). Lower keeps more highlight detail, looks flatter", type: "range", min: 0.1, max: 1, step: 0.05, fmt: (v) => Number(v).toFixed(2), dep: (s) => !s.auto_sdr },
    { key: "quality", lbl: "JPEG quality", hint: "Base image and gain map", type: "number", min: 50, max: 100, step: 1 },
    { key: "limit_nits", lbl: "Limit HDR peak", hint: "Soft-limits highlights to your display's peak (e.g. 1000) so phones show what you saw in game. 0 keeps the capture's full range. This is the only setting that alters the HDR layer", type: "number", min: 0, max: 10000, step: 50, suffix: "nits" },
    { key: "peak_nits", lbl: "Gain map target peak", hint: "0 = match the gain map's own maximum (recommended). Otherwise 250–10000", type: "number", min: 0, max: 10000, step: 50, suffix: "nits" },
    { key: "transfer", lbl: "Input transfer", hint: "auto: float = scRGB (JXR, scRGB JXL), 16-bit = PQ", type: "seg", opts: [["auto", "Auto"], ["scrgb", "scRGB"], ["pq", "PQ"], ["hlg", "HLG"]] },
  ]},
  { title: "About", rows: [
    { type: "about" },
  ]},
];

function renderSettings() {
  const body = $("#settingsBody");
  if (!$("#settings").classList.contains("open")) return;
  const s = S.settings;
  body.innerHTML = "";
  for (const sec of SECTIONS) {
    body.appendChild(el("div", "section-title", sec.title));
    const box = el("div", "section");
    for (const r of sec.rows) {
      if (r.type === "example") {
        const ex = el("div", "example");
        const base = s.save_mode === "folder" && s.save_dir ? s.save_dir : "<folder of the screenshot>";
        ex.innerHTML = `Screenshot 2026-11-11 11-39-10.jxl becomes<b>${esc(base)}\\${esc(s.full_dir || "4K HDR")}\\Screenshot 2026-11-11 11-39-10${esc(s.suffix || "")}.jpg</b>`;
        box.appendChild(ex); continue;
      }
      if (r.type === "note") { const n = el("div", "example", esc(r.text)); n.style.margin = "12px 16px"; box.appendChild(n); continue; }
      if (r.type === "about") {
        const n = el("div", "example"); n.style.margin = "12px 16px";
        n.innerHTML = `<b>UltraShot ${esc(S.version)}</b>Converts ReShade (.jxl) and NVIDIA / Game Bar (.jxr) HDR screenshots to Ultra HDR JPEGs with a gain map (ISO 21496-1 + XMP). Encoder: libultrahdr via imagecodecs ${esc(S.codec)}. Settings: %APPDATA%\\UltraShot\\settings.json`;
        box.appendChild(n); continue;
      }
      if (S.packaged && (r.key === "explorer_menu")) continue;   // the Store package provides "Open with"
      const dep = typeof r.dep === "function" ? r.dep(s) : (r.dep ? !!s[r.dep] : true);
      const row = el("div", "row" + (r.sub ? " sub" : ""));
      if (!dep) row.style.opacity = ".45";
      row.innerHTML = `<div><div class="lbl">${esc(r.lbl)}</div>${r.hint ? `<div class="hint">${r.hint}</div>` : ""}</div><div class="ctl"></div>`;
      row.querySelector(".ctl").appendChild(control(r, s[r.key]));
      box.appendChild(row);
    }
    body.appendChild(box);
  }
}

function control(r, v) {
  const set = (val) => saveSetting(r.key, val);
  if (r.type === "toggle") { const b = el("button", "switch" + (v ? " on" : "")); b.setAttribute("role", "switch"); b.addEventListener("click", () => { b.classList.toggle("on"); set(b.classList.contains("on")); }); return b; }
  if (r.type === "seg") {
    const g = el("div", "seg");
    for (const [val, label] of r.opts) { const b = el("button", val === v ? "on" : "", esc(label)); b.addEventListener("click", () => { g.querySelectorAll("button").forEach((x) => x.classList.remove("on")); b.classList.add("on"); set(val); }); g.appendChild(b); }
    return g;
  }
  if (r.type === "text") { const i = el("input"); i.type = "text"; i.value = v ?? ""; i.addEventListener("change", () => set(i.value)); return i; }
  if (r.type === "number") {
    const w = el("div", "pathbox"); const i = el("input"); i.type = "number"; i.min = r.min; i.max = r.max; i.step = r.step; i.value = v;
    i.addEventListener("change", () => set(Number(i.value))); w.appendChild(i); if (r.suffix) w.appendChild(el("span", "hint", r.suffix)); return w;
  }
  if (r.type === "range") {
    const w = el("div", "pathbox"); const i = el("input"); i.type = "range"; i.min = r.min; i.max = r.max; i.step = r.step; i.value = v;
    const lab = el("span", "val", r.fmt(v)); lab.style.width = "70px"; lab.style.textAlign = "right";
    i.addEventListener("input", () => { lab.textContent = r.fmt(i.value); }); i.addEventListener("change", () => set(Number(i.value)));
    w.appendChild(i); w.appendChild(lab); return w;
  }
  if (r.type === "folder") {
    const w = el("div", "pathbox"); const p = el("span", "path", esc(v || "not set")); p.title = v || "";
    const b = el("button", "ghost tiny", "Choose…"); b.style.margin = "0";
    b.addEventListener("click", async () => { const res = await S.api.choose_dir(r.key); if (res) { S.settings[r.key] = res; renderSettings(); renderChips(); renderWatch(); } });
    w.appendChild(p); w.appendChild(b); return w;
  }
  return el("span");
}

async function saveSetting(key, val) {
  const patch = {}; patch[key] = val;
  S.settings = await S.api.set_settings(patch);
  if (key === "theme") applyTheme();
  renderChips(); renderWatch(); renderInspectorControls();
  if (["save_mode", "save_dir", "make_full", "make_ig", "auto_sdr", "suffix", "full_dir", "watch", "watch_subfolders"].includes(key)) renderSettings();
  if (["exposure", "knee", "auto_sdr", "ig_crop", "crop_x", "crop_y", "transfer", "ig_width"].includes(key)) requestPreview();
}

/* Side panes keep comfortable widths; when another pane would not fit beside the content,
   the pane opened longest ago is closed instead of squeezing all of them. */
const PANES = { inspector: 420, logdrawer: 440, settings: 600 };
const paneOrder = [];
const CONTENT_MIN = 300;
function openPane(id) {
  const i = paneOrder.indexOf(id); if (i >= 0) paneOrder.splice(i, 1);
  paneOrder.push(id);
  document.getElementById(id).classList.add("open");
  fitPanes();
}
function closePane(id) {
  const i = paneOrder.indexOf(id); if (i >= 0) paneOrder.splice(i, 1);
  document.getElementById(id).classList.remove("open");
}
function fitPanes() {
  const avail = window.innerWidth - CONTENT_MIN;
  while (paneOrder.length > 1 && paneOrder.reduce((s, id) => s + PANES[id], 0) > avail) {
    const oldest = paneOrder[0];
    if (oldest === "inspector") { closeInspector(); } else { closePane(oldest); }
  }
}
window.addEventListener("resize", fitPanes);
function openSettings() { openPane("settings"); renderSettings(); }
function closeSettings() { closePane("settings"); }
function openLog() { openPane("logdrawer"); const pre = $("#logbody"); pre.scrollTop = pre.scrollHeight; }
function closeLog() { closePane("logdrawer"); }
function toggleLog() { $("#logdrawer").classList.contains("open") ? closeLog() : openLog(); }

/* ------------------------------------------------------------------ popovers, toasts, log */
function popover(anchor, items) {
  const p = $("#popover"); p.innerHTML = ""; p.classList.remove("hidden");
  for (const it of items) {
    if (it === "-") { p.appendChild(el("div", "sep")); continue; }
    const b = el("button", "item");
    b.innerHTML = `<span><span>${it.label}</span>${it.hint ? `<small>${it.hint}</small>` : ""}</span><span class="check">${it.checked ? "✓" : ""}</span>`;
    b.addEventListener("click", () => { p.classList.add("hidden"); it.run(); });
    p.appendChild(b);
  }
  const r = anchor.getBoundingClientRect();
  p.style.left = r.left + "px"; p.style.bottom = (innerHeight - r.top + 8) + "px"; p.style.top = "auto";
  const close = (e) => { if (!p.contains(e.target) && e.target !== anchor) { p.classList.add("hidden"); document.removeEventListener("mousedown", close); } };
  setTimeout(() => document.addEventListener("mousedown", close), 0);
}

function toast(msg, kind = "info") {
  const t = el("div", "toast " + kind, esc(msg));
  $("#toasts").appendChild(t);
  setTimeout(() => t.classList.add("fade"), 3200);
  setTimeout(() => t.remove(), 3700);
}

function appendLog(t, msg) {
  const pre = $("#logbody");
  const line = el("div");
  line.innerHTML = `<span class="t">${esc(t)}</span> <span class="${/FAILED|error/i.test(msg) ? "err" : ""}">${esc(msg)}</span>`;
  pre.appendChild(line);
  while (pre.childElementCount > 600) pre.firstChild.remove();
  pre.scrollTop = pre.scrollHeight;
}

/* ------------------------------------------------------------------ result viewer */
const LB = { ids: [], i: 0, which: "ig", path: null, seq: 0, info: false, report: "", compare: false, cmpMode: "sdrhdr", cmpSeq: 0 };

function convertedIds() { return S.order.filter((id) => { const f = S.files.get(id); return f && f.outputs && f.outputs.length; }); }

function openResult(id) {
  const f = S.files.get(id);
  if (!f?.outputs?.length) { toast("Not converted yet", "warn"); return; }
  if (convertedIds().length === 1) S.api.open_path(f.outputs[0]);   // one result: the default viewer
  else openLightbox(id);                                              // several: slide through in-app
}

function openLightbox(id) {
  LB.ids = convertedIds();
  if (!LB.ids.length) return;
  LB.i = Math.max(0, LB.ids.indexOf(id));
  $("#lightbox").classList.remove("hidden");
  showLightbox();
}
function closeLightbox() { $("#lightbox").classList.add("hidden"); $("#lbImg").removeAttribute("src"); setCompare(false); }

/* ---- compare (wipe) view */
function setCompare(on) {
  LB.compare = on;
  $("#lbCompare").classList.toggle("hidden", !on);
  $("#lbStage").classList.toggle("hidden", on);
  $("#lbCompareBtn").classList.toggle("on", on);
  if (on) loadCompare(); else { $("#cmpImgA").removeAttribute("src"); $("#cmpImgB").removeAttribute("src"); }
}
function setWipe(pct) { const p = Math.max(0, Math.min(100, pct)); $("#cmpStage").style.setProperty("--wipe", p + "%"); }
async function loadCompare() {
  const id = LB.ids[LB.i]; if (!id) return;
  const seq = ++LB.cmpSeq, stage = $("#cmpStage"), one = LB.cmpMode === "source";
  $("#cmpMode").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === LB.cmpMode));
  $("#cmpLoading").style.display = ""; $("#cmpMetrics").innerHTML = ""; $("#cmpHint").textContent = "";
  stage.classList.toggle("one-to-one", one);
  stage.style.maxWidth = ""; stage.style.maxHeight = "";
  stage.style.setProperty("--px", "0px"); stage.style.setProperty("--py", "0px");
  setWipe(50);
  let r;
  try { r = one ? await S.api.compare_source(id) : await S.api.compare_sdr_hdr(id, LB.which); } catch (e) { r = { error: String(e) }; }
  if (seq !== LB.cmpSeq) return;
  $("#cmpLoading").style.display = "none";
  if (!r || r.error) { $("#cmpMetrics").innerHTML = `<span class="warn">${esc(r?.error || "nothing to compare")}</span>`; return; }
  if (one) {
    $("#cmpImgA").src = r.src_url; $("#cmpImgB").src = r.base_url;
    $("#cmpLabelA").textContent = "Source, same tone map"; $("#cmpLabelB").textContent = "Output base image";
    $("#cmpHint").textContent = "Actual pixels. Drag the image to pan, the handle to wipe.";
    const m = r.metrics, sdrOk = m.sdr_psnr_db >= 40, hdrOk = m.hdr_p99_rel_err <= 5;
    $("#cmpMetrics").innerHTML =
      `<span>SDR base vs source: <b class="${sdrOk ? "ok" : "warn"}">${m.sdr_psnr_db >= 99 ? "identical" : m.sdr_psnr_db.toFixed(1) + " dB PSNR"}</b>, max ${m.sdr_max_diff}/255, ${m.sdr_pixels_over_2.toFixed(2)}% of pixels off by more than 2 levels</span>` +
      `<span>HDR layer vs source: <b class="${hdrOk ? "ok" : "warn"}">${m.hdr_mean_rel_err.toFixed(2)}% mean luminance error</b>, ${m.hdr_p99_rel_err.toFixed(1)}% at the 99th percentile, ${m.hdr_pixels_over_5pct.toFixed(2)}% of pixels off by more than 5% (pixels above 5 nits)</span>` +
      `<span>Peak: source <b>${Math.round(m.hdr_peak_source)}</b> nits, output <b>${Math.round(m.hdr_peak_output)}</b> nits</span>` +
      `<span>Rendered with the current look (exposure ${m.look.exposure >= 0 ? "+" : ""}${m.look.exposure.toFixed(2)}, knee ${m.look.knee.toFixed(2)}${m.look.limit_nits ? ", limit " + m.look.limit_nits + " nits" : ""})</span>`;
    // At 1:1 the stage never exceeds the image, so a small capture sits centred with the wipe
    // running across the picture, and a large one starts centred on its middle.
    $("#cmpImgA").onload = () => {
      const img = $("#cmpImgA");
      stage.style.maxWidth = img.naturalWidth + "px"; stage.style.maxHeight = img.naturalHeight + "px";
      const dx = Math.min(0, (stage.clientWidth - img.naturalWidth) / 2), dy = Math.min(0, (stage.clientHeight - img.naturalHeight) / 2);
      stage.style.setProperty("--px", dx + "px"); stage.style.setProperty("--py", dy + "px");
    };
  } else {
    stage.style.maxWidth = ""; stage.style.maxHeight = "";
    $("#cmpImgA").src = r.base_url; $("#cmpImgB").src = r.full_url;
    $("#cmpLabelA").textContent = "SDR base · what SDR screens and thumbnails show"; $("#cmpLabelB").textContent = "Ultra HDR · what HDR phones and Chrome show";
    $("#cmpHint").textContent = "On an HDR display the right side is brighter; on an SDR display both halves look the same, which is the point.";
    $("#cmpMetrics").innerHTML = `<span>${r.w}×${r.h} · ${LB.which === "full" ? "full-size file" : "Instagram copy"} · drag the handle to wipe</span>`;
  }
}
function bindWipe() {
  const stage = $("#cmpStage"); let drag = null;
  stage.addEventListener("pointerdown", (e) => {
    const rect = stage.getBoundingClientRect();
    const onHandle = e.target.closest("#cmpHandle") || Math.abs(e.clientX - (rect.left + rect.width * parseFloat(getComputedStyle(stage).getPropertyValue("--wipe")) / 100)) < 14;
    drag = { mode: onHandle ? "wipe" : (stage.classList.contains("one-to-one") ? "pan" : "wipe"), x: e.clientX, y: e.clientY,
             px: parseFloat(stage.style.getPropertyValue("--px")) || 0, py: parseFloat(stage.style.getPropertyValue("--py")) || 0 };
    stage.setPointerCapture(e.pointerId);
    if (drag.mode === "wipe") setWipe((e.clientX - rect.left) / rect.width * 100);
  });
  stage.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const rect = stage.getBoundingClientRect();
    if (drag.mode === "wipe") { setWipe((e.clientX - rect.left) / rect.width * 100); return; }
    const img = $("#cmpImgA"); if (!img.naturalWidth) return;
    const nx = Math.min(0, Math.max(rect.width - img.naturalWidth, drag.px + e.clientX - drag.x));
    const ny = Math.min(0, Math.max(rect.height - img.naturalHeight, drag.py + e.clientY - drag.y));
    stage.style.setProperty("--px", nx + "px"); stage.style.setProperty("--py", ny + "px");
  });
  const end = () => { drag = null; };
  stage.addEventListener("pointerup", end); stage.addEventListener("pointercancel", end);
}
function stepLightbox(d) { if (!LB.ids.length) return; LB.i = (LB.i + d + LB.ids.length) % LB.ids.length; showLightbox(); }

async function showLightbox() {
  const id = LB.ids[LB.i], f = S.files.get(id);
  if (!f) { closeLightbox(); return; }
  const seq = ++LB.seq;
  $("#lbName").textContent = f.name;
  $("#lbMeta").textContent = `${LB.i + 1} / ${LB.ids.length}`;
  $("#lbLoading").style.display = "";
  const r = await S.api.output_image(id, LB.which);
  if (seq !== LB.seq) return;
  $("#lbLoading").style.display = "none";
  if (!r) { toast("Output file not found", "err"); return; }
  LB.path = r.path; LB.which = r.which;
  $("#lbImg").src = r.url;
  $("#lbWhich").querySelectorAll("button").forEach((b) => { b.classList.toggle("on", b.dataset.v === r.which); b.disabled = (b.dataset.v === "full" && !r.has_full) || (b.dataset.v === "ig" && !r.has_ig); });
  $("#lbFoot").textContent = `${r.path.split(/[\\/]/).slice(-2).join("\\")} · ${(r.size / 1e6).toFixed(1)} MB · gain-map JPEG, shown in HDR when this display is in HDR mode`;
  $("#lbPrev").style.visibility = $("#lbNext").style.visibility = LB.ids.length > 1 ? "visible" : "hidden";
  if (LB.info) loadInfo();
  if (LB.compare) loadCompare();
}

const fmtBytes = (b) => b >= 1e6 ? (b / 1e6).toFixed(1) + " MB" : Math.round(b / 1e3) + " KB";
const fmt3 = (a) => a.every((v) => Math.abs(v - a[0]) < 1e-4) ? a[0].toFixed(3) : a.map((v) => v.toFixed(3)).join(" / ");

async function loadInfo() {
  const id = LB.ids[LB.i];
  const body = $("#lbInfoBody");
  body.innerHTML = `<div class="kv"><span>Reading the file…</span><span class="spinner"></span></div>`;
  const r = await S.api.output_info(id, LB.which);
  if (!r || r.error) { body.innerHTML = `<div class="kv"><span>Error</span><span class="bad">${esc(r?.error || "no output")}</span></div>`; return; }
  const rows = [], lines = [];
  const sec = (t) => { rows.push(`<h4>${t}</h4>`); lines.push("", t.toUpperCase()); };
  const kv = (k, v, cls) => { rows.push(`<div class="kv"><span>${k}</span><span class="${cls || ""}">${v}</span></div>`); lines.push(`${k}: ${String(v).replace(/<[^>]+>/g, "")}`); };
  const yn = (b, good) => b ? `<span class="${good === false ? "" : "ok"}">yes</span>` : `<span class="${good === false ? "" : "bad"}">no</span>`;
  lines.push(r.name);
  const src = S.files.get(id)?.stats?.source;
  if (src && src.format) {
    sec("Source capture");
    kv("Container", src.format + (src.format === "JPEG XL" ? " (ReShade)" : " (NVIDIA App / Game Bar)"));
    kv("Pixel data", src.pixel_type); kv("Transfer curve", src.transfer); kv("Primaries", src.primaries);
    kv("Channels", src.channels === 4 ? "RGBA" : "RGB"); kv("File size", fmtBytes(src.size_bytes));
    kv("MaxCLL (brightest pixel)", `${Math.round(src.maxcll)} nits`); kv("MaxFALL (frame average)", `${src.maxfall.toFixed(1)} nits`);
    kv("Peak as PQ code", `${src.peak_pq.toFixed(3)} (${Math.round(src.peak_pq * 1023)} / 1023)`);
  }
  sec("File");
  kv("Name", esc(r.name)); kv("Size", fmtBytes(r.file.size_bytes)); kv("Modified", r.file.modified);
  kv("Ultra HDR (gain map found)", yn(r.file.ultra_hdr));
  sec("Base image (what SDR viewers see)");
  kv("Resolution", `${r.base.width}×${r.base.height}`); kv("Chroma subsampling", r.base.chroma + (r.base.chroma === "4:4:4" ? " (full colour)" : ""));
  kv("Estimated JPEG quality", r.base.quality_estimate ?? "—"); kv("Colour profile", r.base.icc_profile ? esc(r.base.icc_profile) : "none (sRGB assumed)");
  kv("Transfer curve", "sRGB (gamma-encoded, 8-bit)");
  kv("Progressive", r.base.progressive ? "yes" : "no"); kv("Encoded size", fmtBytes(r.base.size_bytes));
  if (r.gainmap) {
    sec("Gain map");
    kv("Resolution", `${r.gainmap.width}×${r.gainmap.height}` + (r.gainmap.width === r.base.width ? " (full)" : " (reduced)"));
    kv("Channels", r.gainmap.mode === "RGB" || r.metadata.multichannel ? "per channel (RGB)" : "single"); kv("Chroma subsampling", r.gainmap.chroma);
    kv("Estimated JPEG quality", r.gainmap.quality_estimate ?? "—"); kv("Encoded size", fmtBytes(r.gainmap.size_bytes));
    const m = r.metadata;
    sec("Gain map metadata");
    kv("Max content boost", `${fmt3(m.max_content_boost)}× (${Math.round(m.peak_nits_declared)} nits)`);
    kv("Min content boost", fmt3(m.min_content_boost) + "×"); kv("Gamma", fmt3(m.gamma));
    kv("Offsets (SDR / HDR)", `${m.offset_sdr[0].toExponential(1)} / ${m.offset_hdr[0].toExponential(1)}`);
    kv("HDR capacity min", m.hdr_capacity_min.toFixed(2) + "×"); kv("HDR capacity max", m.hdr_capacity_max.toFixed(2) + "×");
    kv("Capacity matches boost", yn(m.capacity_matches_boost));
    kv("Gain map colour gamut", m.use_base_colour_gamut ? "base image's" : "HDR image's");
    sec("HDR as a viewer reconstructs it");
    kv("Encoding", "linear gain over the base, relative to SDR white (203 nits); not PQ-coded");
    kv("Peak", `${Math.round(r.hdr.peak_nits)} nits`); kv("Mean", `${r.hdr.mean_nits.toFixed(1)} nits`);
    kv("MaxCLL / MaxFALL", `${Math.round(r.hdr.maxcll)} / ${r.hdr.maxfall.toFixed(1)} nits`);
    kv("Peak as PQ code", `${r.hdr.peak_pq.toFixed(3)} (${Math.round(r.hdr.peak_pq * 1023)} / 1023)`);
    kv("Headroom needed for full HDR", `${r.hdr.headroom_stops.toFixed(2)} stops (${(2 ** r.hdr.headroom_stops).toFixed(2)}× SDR white)`);
    kv("Above SDR white (203 nits)", r.hdr.above_sdr_percent.toFixed(2) + "%"); kv("Above 1000 nits", r.hdr.above_1000_percent.toFixed(2) + "%");
  }
  sec("Metadata signalling");
  kv("ISO 21496-1 (Android 15, iOS 18, Chrome)", yn(r.signalling.iso_21496));
  kv("XMP hdrgm (older Android, Adobe)", yn(r.signalling.xmp_hdrgm));
  kv("MPF container", yn(r.signalling.mpf)); kv("ICC profile segment", yn(r.signalling.icc, false)); kv("EXIF", yn(r.signalling.exif, false));
  body.innerHTML = rows.join("");
  LB.report = lines.join("\n");
}

/* ------------------------------------------------------------------ actions */
async function convertAll() { const ids = pendingIds(); if (!ids.length) return; S.batch = new Set(ids); await S.api.convert(ids); updateProgress(); updateConvertButton(); }
async function convertOne(id) { S.batch = new Set([...(S.batch || []), id]); await S.api.convert([id]); updateProgress(); }

function bindUI() {
  $("#empty").addEventListener("click", () => S.api.pick_files());
  $("#btnAdd").addEventListener("click", () => S.api.pick_files());
  $("#btnClear").addEventListener("click", () => S.api.clear());
  $("#btnClearDone").addEventListener("click", () => S.api.clear_done());
  $("#btnConvert").addEventListener("click", convertAll);
  $("#btnSettings").addEventListener("click", () => $("#settings").classList.contains("open") ? closeSettings() : openSettings());
  $("#settingsBack").addEventListener("click", closeSettings);
  $("#btnLog").addEventListener("click", toggleLog);
  $("#btnLogClose").addEventListener("click", closeLog);
  $("#btnLogClear").addEventListener("click", () => { $("#logbody").innerHTML = ""; });
  $("#watchPill").addEventListener("click", () => S.api.set_watch(!S.watching));
  $("#inspClose").addEventListener("click", closeInspector);
  $("#inspConvert").addEventListener("click", () => S.selected && convertOne(S.selected));
  $("#inspRemove").addEventListener("click", () => S.selected && S.api.remove(S.selected));
  $("#inspReveal").addEventListener("click", () => { const f = S.files.get(S.selected); if (f?.outputs?.length) S.api.reveal(f.outputs[0]); });
  $("#inspView").addEventListener("click", () => S.selected && openLightbox(S.selected));
  $("#inspOpen").addEventListener("click", () => { const f = S.files.get(S.selected); if (f?.outputs?.length) S.api.open_path(f.outputs[0]); });
  $("#lbClose").addEventListener("click", closeLightbox);
  $("#lbPrev").addEventListener("click", () => stepLightbox(-1));
  $("#lbNext").addEventListener("click", () => stepLightbox(1));
  $("#lbOpen").addEventListener("click", () => { if (LB.path) S.api.open_path(LB.path); });
  $("#lbReveal").addEventListener("click", () => { if (LB.path) S.api.reveal(LB.path); });
  $("#lbWhich").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { LB.which = b.dataset.v; showLightbox(); } });
  $("#lbInfo").addEventListener("click", () => { LB.info = !LB.info; $("#lbInfoPanel").classList.toggle("hidden", !LB.info); if (LB.info) loadInfo(); });
  $("#lbCompareBtn").addEventListener("click", () => setCompare(!LB.compare));
  $("#cmpMode").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { LB.cmpMode = b.dataset.v; loadCompare(); } });
  bindWipe();
  $("#lbInfoClose").addEventListener("click", () => { LB.info = false; $("#lbInfoPanel").classList.add("hidden"); });
  $("#lbCopyReport").addEventListener("click", async () => { try { await navigator.clipboard.writeText(LB.report || ""); toast("Report copied", "ok"); } catch (e) { toast("Could not copy", "err"); } });
  $("#lightbox").addEventListener("click", (e) => { if (e.target.id === "lightbox" || e.target.classList.contains("lb-stage")) closeLightbox(); });
  $("#inspTarget").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; S.inspTarget = b.dataset.v; renderInspectorControls(); requestPreview(); });
  $("#inspCrop").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) saveSetting("ig_crop", b.dataset.v); });
  const live = (id, key, fmt, label) => {
    const r = $(id);
    r.addEventListener("input", () => { S.settings[key] = Number(r.value); $(label).textContent = fmt(r.value); requestPreview(); });
    r.addEventListener("change", () => saveSetting(key, Number(r.value)));
  };
  live("#rExposure", "exposure", (v) => (v >= 0 ? "+" : "") + Number(v).toFixed(2) + " st", "#vExposure");
  live("#rKnee", "knee", (v) => Number(v).toFixed(2), "#vKnee");
  live("#rCx", "crop_x", (v) => v + "%", "#vCx");
  live("#rCy", "crop_y", (v) => v + "%", "#vCy");

  $("#chipOut").addEventListener("click", (e) => popover(e.currentTarget, [
    { label: "Full size", hint: "4K HDR subfolder", checked: S.settings.make_full, run: () => saveSetting("make_full", !S.settings.make_full) },
    { label: "Instagram", hint: `${S.settings.ig_width} px wide${S.settings.ig_crop !== "none" ? ", " + S.settings.ig_crop : ""}`, checked: S.settings.make_ig, run: () => saveSetting("make_ig", !S.settings.make_ig) },
    "-", { label: "Output settings…", run: openSettings },
  ]));
  $("#chipSave").addEventListener("click", (e) => popover(e.currentTarget, [
    { label: "Next to each original", checked: S.settings.save_mode === "beside", run: () => saveSetting("save_mode", "beside") },
    { label: "Fixed folder…", hint: S.settings.save_dir || "choose a folder", checked: S.settings.save_mode === "folder", run: async () => { const d = await S.api.choose_dir("save_dir"); if (d) saveSetting("save_mode", "folder"); } },
    "-", { label: "Open output folder", run: async () => { const d = await S.api.output_dir(S.selected); if (d) S.api.open_path(d); } },
  ]));
  $("#chipLook").addEventListener("click", (e) => popover(e.currentTarget, [
    ...LOOKS.map(([n, ex, kn, hint]) => ({ label: n, hint, checked: !S.settings.auto_sdr && lookName(S.settings) === n, run: async () => { await S.api.set_settings({ auto_sdr: false }); await saveSetting("exposure", ex); await saveSetting("knee", kn); } })),
    { label: "Automatic", hint: "libultrahdr's own tone map", checked: !!S.settings.auto_sdr, run: () => saveSetting("auto_sdr", true) },
    "-", { label: "Fine-tune…", run: openSettings },
  ]));

  // drag & drop visuals (file paths arrive through Python's DOM drop handler)
  let depth = 0;
  window.addEventListener("dragenter", (e) => { e.preventDefault(); depth++; $("#dragover").classList.add("show"); });
  window.addEventListener("dragover", (e) => { e.preventDefault(); });
  window.addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; $("#dragover").classList.remove("show"); } });
  window.addEventListener("drop", (e) => { e.preventDefault(); depth = 0; $("#dragover").classList.remove("show"); });

  document.addEventListener("keydown", (e) => {
    const lbOpen = !$("#lightbox").classList.contains("hidden");
    if (lbOpen && e.key === "ArrowLeft") { stepLightbox(-1); return; }
    if (lbOpen && e.key === "ArrowRight") { stepLightbox(1); return; }
    if (e.key === "Escape") { if (lbOpen) closeLightbox(); else if ($("#settings").classList.contains("open")) closeSettings(); else if ($("#logdrawer").classList.contains("open")) closeLog(); else if (!$("#popover").classList.contains("hidden")) $("#popover").classList.add("hidden"); else closeInspector(); }
    if (e.key === "Enter" && !e.ctrlKey && S.selected && document.activeElement.tagName !== "INPUT" && !lbOpen) openResult(S.selected);
    if (e.key === "Delete" && S.selected && document.activeElement.tagName !== "INPUT") S.api.remove(S.selected);
    if (e.ctrlKey && e.key.toLowerCase() === "o") { e.preventDefault(); S.api.pick_files(); }
    if (e.ctrlKey && e.key === "Enter") convertAll();
  });
  document.addEventListener("contextmenu", (e) => { if (e.target.tagName !== "INPUT") e.preventDefault(); });
}
