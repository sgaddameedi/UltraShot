// The video editor: a workspace for trimming, cutting and joining recordings without re-encoding.
// Everything heavy happens in Python (hdrvideo); this file draws the state, drives the player and
// turns pointer and key input into in/out points and segments.
window.VideoUI = (() => {
  const $ = (s) => document.querySelector(s);
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const pad = (n, w = 2) => String(n).padStart(w, "0");
  // hh:mm:ss:ff timecode (frames when the rate is known, hundredths otherwise)
  const tc = (t, fps) => {
    if (!isFinite(t) || t < 0) t = 0;
    const whole = Math.floor(t + 1e-6);
    const frac = t - whole;
    const ff = fps ? Math.min(Math.round(fps) - 1, Math.round(frac * fps)) : Math.floor(frac * 100);
    return `${pad(Math.floor(whole / 3600))}:${pad(Math.floor(whole / 60) % 60)}:${pad(whole % 60)}:${pad(ff, fps > 99 ? 3 : 2)}`;
  };
  // h:mm:ss for lengths
  const hms = (t) => { t = Math.max(0, Math.round(t || 0)); const h = Math.floor(t / 3600); return `${h ? h + ":" : ""}${pad(Math.floor(t / 60) % 60)}:${pad(t % 60)}`; };
  const secs = (t) => (t >= 60 ? hms(t) : `${t.toFixed(1)} s`);
  // "hh:mm:ss:ff", "mm:ss:ff", "mm:ss", "ss.s" -> seconds
  const parseTc = (s, fps) => {
    s = String(s || "").trim(); if (!s) return NaN;
    if (/^\d+(\.\d+)?$/.test(s)) return parseFloat(s);
    const p = s.split(/[:;.]/).map(Number); if (p.some(isNaN)) return NaN;
    let h = 0, m = 0, sec = 0, f = 0;
    if (p.length === 4) [h, m, sec, f] = p; else if (p.length === 3) [m, sec, f] = p; else if (p.length === 2) [m, sec] = p; else return NaN;
    return h * 3600 + m * 60 + sec + (fps ? f / fps : f / 100);
  };
  const fmtSize = (n) => n >= 1e9 ? (n / 1e9).toFixed(2) + " GB" : n >= 1e6 ? (n / 1e6).toFixed(0) + " MB" : (n / 1e3).toFixed(0) + " KB";
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const toast = (msg, kind) => { if (window.toast) window.toast(msg, kind); };

  const V = {
    open: false, videos: new Map(), order: [], cur: null, inT: 0, outT: 0, segs: [], sel: -1,
    join: false, where: "beside", folder: "", keys: [], proxy: false, previewEnd: null,
    stripFor: null, job: null, raf: 0, ff: null, hist: [],
    frame: "source", fsize: "full", cx: 0.5, cy: 0.5,
  };
  let P, api;

  // ------------------------------------------------------------- panel
  function isOpen() { return V.open; }
  function placePanel() { const tb = $(".topbar"); if (tb) $("#video").style.top = tb.getBoundingClientRect().bottom + "px"; }
  function setMode(video) { document.querySelectorAll("#mode button").forEach((b) => b.classList.toggle("on", (b.dataset.mode === "video") === video)); }
  function open() {
    setMode(true);
    if (V.open) return;
    V.open = true; placePanel();
    $("#video").classList.remove("hidden");
    api = window.pywebview.api;
    api.video_state().then((st) => {
      V.ff = st.ffmpeg; renderFF();
      (st.videos || []).forEach(upsert);
      if (st.job) { V.job = st.job; if (st.job.running) showProgress(st.job.pct, st.job.msg); else if (st.job.outputs?.length) renderResults(st.job); }
      renderBin();
      if (!V.cur && V.order.length) select(V.order[0]);
      renderGuide();
    });
  }
  function close() {
    setMode(false);
    if (!V.open) return;
    V.open = false;
    $("#video").classList.add("hidden");
    P.pause();
  }

  // ------------------------------------------------------------- events from Python
  function on(name, p) {
    switch (name) {
      case "video_open": open(); break;
      case "video_file":
        upsert(p); renderBin();
        if (p.id === V.cur) {
          if (p.status === "ready" && !V.videos.get(p.id)._loaded) select(p.id, true);
          if (p.proxy_url && V.proxy && P.src !== p.proxy_url) { P.src = p.proxy_url; P.load(); $("#vStageMsg").textContent = ""; }
        } else if (!V.cur && p.status === "ready") select(p.id);
        renderGuide();
        break;
      case "video_removed":
        V.videos.delete(p); V.order = V.order.filter((i) => i !== p);
        V.segs = V.segs.filter((s) => s.id !== p); renderSegs();
        if (V.cur === p) { V.cur = null; P.removeAttribute("src"); P.load(); $("#vStageChip").textContent = ""; $("#vStrip").innerHTML = ""; $("#vTicks").innerHTML = ""; $("#vRuler").innerHTML = ""; if (V.order.length) select(V.order[0]); }
        renderBin(); renderGuide(); break;
      case "video_progress":
        if (p.kind === "export" || p.kind === "ffmpeg") showProgress(p.pct, p.msg);
        else if (p.kind === "proxy" && p.id === V.cur) $("#vStageMsg").textContent = p.error ? p.msg : `${p.msg} ${Math.round(p.pct)}%`;
        break;
      case "video_done":
        V.job = p; hideProgress(); renderResults(p); updateExportBtn();
        if (p.error) toast(`Export failed: ${p.error}`, "err"); else toast(p.outputs.length === 1 ? "Exported 1 file, verified against the source" : `Exported ${p.outputs.length} files, verified against the source`, "ok");
        break;
      case "video_ffmpeg":
        V.ff = p; renderFF(); hideProgress();
        if (p.found) { toast("FFmpeg is ready", "ok"); V.order.forEach((id) => { const v = V.videos.get(id); if (v.status === "failed") api.video_add([v.path]).then(() => api.video_remove(id)); }); }
        else toast(`FFmpeg: ${p.error || "not found"}`, "err");
        break;
    }
  }
  function upsert(p) {
    const old = V.videos.get(p.id) || {};
    V.videos.set(p.id, Object.assign(old, p));
    if (!V.order.includes(p.id)) V.order.push(p.id);
  }
  function renderFF() {
    const c = $("#vFfmpeg");
    if (!V.ff || V.ff.found) { c.classList.add("hidden"); return; }
    c.classList.remove("hidden");
    c.innerHTML = "<b>FFmpeg is missing</b> · Get FFmpeg";
    c.title = "The editor needs FFmpeg. This downloads the gyan.dev essentials build (about 100 MB) into UltraShot's own folder; nothing else on the system changes.";
  }
  function renderGuide() {
    const has = !!(V.cur && V.videos.get(V.cur)?.info);
    $("#vGuide").classList.toggle("hidden", has);
    $("#vStage").classList.toggle("empty", !has);
    $("#vTimeline").classList.toggle("idle", !has);
    if (!has) $("#vCrop").classList.add("hidden");
  }
  function coach(show) {
    const c = $("#vCoach");
    if (show && !localStorage.getItem("ultrashot.vcoach")) c.classList.remove("hidden");
    if (!show) { c.classList.add("hidden"); localStorage.setItem("ultrashot.vcoach", "1"); }
  }

  // ------------------------------------------------------------- clip bin
  function renderBin() {
    const list = $("#vBinList");
    $("#vBinEmpty").classList.toggle("hidden", V.order.length > 0);
    list.innerHTML = "";
    for (const id of V.order) {
      const v = V.videos.get(id);
      const d = el("div", "v-clip" + (id === V.cur ? " on" : ""));
      const info = v.info;
      const meta = v.status === "probing" ? "Reading the file…" : v.status === "failed" ? v.error : `${fmtSize(v.size)} · ${esc(info.summary)}`;
      d.innerHTML = `<div class="th">${v.thumb ? `<img src="${v.thumb}" alt="">` : ""}${info ? `<span class="len">${hms(info.duration)}</span>` : ""}</div>
        <div class="nm" title="${esc(v.path)}">${esc(v.name)}</div>
        <div class="dm${v.status === "failed" ? " err" : ""}">${meta}</div>
        <button class="iconbtn small rm" title="Remove from the editor (the file stays on disk)"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>`;
      d.addEventListener("click", (e) => { if (e.target.closest("button")) { api.video_remove(id); return; } if (v.status === "ready") select(id); });
      list.appendChild(d);
    }
  }

  // ------------------------------------------------------------- player
  function select(id, reload = false) {
    const v = V.videos.get(id);
    if (!v) return;
    const changed = V.cur !== id;
    V.cur = id; renderBin();
    if (!v.info) { $("#vStageMsg").textContent = v.status === "failed" ? v.error : "Reading the file…"; return; }
    if (changed || reload) {
      v._loaded = true;
      V.proxy = false; V.previewEnd = null;
      P.pause();
      P.src = v.proxy_url || v.url; V.proxy = !!v.proxy_url;
      P.load();
      $("#vStageMsg").textContent = "";
      V.inT = 0; V.outT = v.info.duration; V.keys = [];
      renderStageChip(); layoutRange(); layoutPlayhead(0); renderTime(0); renderRuler(); renderFrame();
      loadStrip(id);
      api.video_keyframes(id, 0, 8).then((ks) => { if (V.cur === id && Array.isArray(ks)) { V.keys = ks; renderTicks(); } });
      renderGuide(); coach(true);
    }
  }
  function renderStageChip() {
    const v = V.videos.get(V.cur); if (!v?.info) return;
    $("#vStageChip").textContent = v.info.summary + (V.proxy ? " · SDR preview copy, the export is the original" : v.info.is_hdr ? " · preview only, the export keeps the HDR as recorded" : "");
  }
  function playerError() {
    // the browser cannot decode this one: ask for a small SDR proxy and keep editing on it
    const id = V.cur; const v = V.videos.get(id); if (!v || V.proxy) return;
    V.proxy = true; renderStageChip();
    $("#vStageMsg").textContent = "This file has no decoder in the window. Building a small preview copy…";
    api.video_proxy(id).then((r) => {
      if (r.error) { $("#vStageMsg").textContent = `No preview: ${r.error}`; return; }
      if (r.url) { P.src = r.url; P.load(); $("#vStageMsg").textContent = ""; }
    });
  }
  function dur() { const v = V.videos.get(V.cur); return v?.info?.duration || P.duration || 0; }
  function fps() { return V.videos.get(V.cur)?.info?.video?.fps || 0; }
  function seek(t) { t = clamp(t, 0, dur()); P.currentTime = t; layoutPlayhead(t); renderTime(t); }
  function togglePlay() { if (!V.cur) return; V.previewEnd = null; if (P.paused) { if (P.ended || P.currentTime >= dur() - 0.01) P.currentTime = 0; P.play(); } else P.pause(); }
  function tick() {
    const t = P.currentTime;
    layoutPlayhead(t); renderTime(t);
    if (V.previewEnd != null && t >= V.previewEnd) { P.pause(); seek(V.previewEnd); V.previewEnd = null; }
    if (!P.paused) V.raf = requestAnimationFrame(tick);
  }
  function renderTime(t) {
    $("#vTime").innerHTML = `${tc(t, fps())} <i>/ ${tc(dur(), fps())}</i>`;
    $("#vPlayIcon").setAttribute("d", P.paused ? "M7 4v16l13-8z" : "M6 4h4v16H6zM14 4h4v16h-4z");
  }
  function previewSelection() { if (!V.cur) return; seek(V.inT); V.previewEnd = V.outT; P.play(); }

  // ------------------------------------------------------------- timeline
  function loadStrip(id) {
    const tl = $("#vTimeline"); const n = Math.max(6, Math.min(40, Math.round(tl.clientWidth / 110)));
    const strip = $("#vStrip"); strip.innerHTML = ""; for (let i = 0; i < n; i++) strip.appendChild(el("div"));
    V.stripFor = id;
    api.video_filmstrip(id, n, 240).then((frames) => {
      if (V.stripFor !== id || !Array.isArray(frames)) return;
      [...strip.children].forEach((d, i) => { if (frames[i]?.url) d.style.backgroundImage = `url(${frames[i].url})`; });
    });
  }
  const x2t = (x) => { const r = $("#vTimeline").getBoundingClientRect(); return clamp((x - r.left) / r.width, 0, 1) * dur(); };
  const t2pct = (t) => (dur() ? (t / dur()) * 100 : 0) + "%";
  function layoutRange() {
    $("#vIn").style.left = t2pct(V.inT); $("#vOut").style.left = t2pct(V.outT);
    const tl = $("#vTimeline"), d0 = dur();
    tl.classList.toggle("tight", d0 > 0 && (V.outT - V.inT) / d0 * tl.clientWidth < 44);
    $("#vShadeL").style.width = t2pct(V.inT); $("#vShadeR").style.width = t2pct(Math.max(0, dur() - V.outT));
    const f = fps();
    $("#vInTc").value = tc(V.inT, f); $("#vOutTc").value = tc(V.outT, f);
    $("#vSel").textContent = V.cur ? `${secs(V.outT - V.inT)} selected` : "";
    updateAddBtn();
  }
  function layoutPlayhead(t) { $("#vPlayhead").style.left = t2pct(t); }
  function renderTicks() {
    const tk = $("#vTicks"); tk.innerHTML = ""; const d = dur(); if (!d || V.keys.length < 2) return;
    const px = $("#vTimeline").clientWidth / d; const gap = Math.min(...V.keys.slice(1).map((k, i) => k - V.keys[i]));
    if (gap * px < 6) return;
    for (const k of V.keys) { const i = document.createElement("i"); i.style.left = (k / d) * 100 + "%"; tk.appendChild(i); }
  }
  function renderRuler() {
    const r = $("#vRuler"); r.innerHTML = ""; const d = dur(); if (!d) return;
    const w = $("#vTimeline").clientWidth || 800;
    const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];
    const step = steps.find((s) => (s / d) * w >= 70) || 3600;
    for (let t = 0; t <= d; t += step) { const i = document.createElement("i"); i.style.left = (t / d) * 100 + "%"; i.textContent = hms(t); r.appendChild(i); }
  }
  async function setIn(t, snap = true) {
    if (snap && V.cur) {
      const r = await api.video_snap(V.cur, t, "nearest");
      if (!r.error) {
        V.keys = r.keyframes || V.keys; renderTicks();
        $("#vSnapHint").textContent = Math.abs(r.t - t) > 1e-3 ? `In point moved to the keyframe at ${tc(r.t, fps())} so the cut stays lossless.` : "";
        t = r.t;
      }
    }
    V.inT = clamp(t, 0, dur()); if (V.outT <= V.inT) V.outT = Math.min(dur(), V.inT + 1 / (fps() || 30));
    layoutRange();
  }
  function setOut(t) { V.outT = clamp(t, 0, dur()); if (V.outT <= V.inT) V.inT = Math.max(0, V.outT - 1 / (fps() || 30)); layoutRange(); }
  function updateAddBtn() { $("#vAddSeg").disabled = !V.cur || V.outT - V.inT < 1e-3; $("#vSplit").disabled = !V.cur; $("#vReset").disabled = !V.cur; }
  function resetSel() { if (!V.cur) return; V.inT = 0; V.outT = dur(); $("#vSnapHint").textContent = ""; layoutRange(); }
  async function splitAt(t) {
    // the selection becomes two segments that meet at the keyframe nearest the playhead, so both
    // halves stay lossless and no frame is lost or doubled between them
    if (!V.cur) return;
    t = t ?? P.currentTime;
    if (t <= V.inT + 1e-3 || t >= V.outT - 1e-3) { toast("Put the playhead inside the selection to split it", "warn"); return; }
    const r = await api.video_snap(V.cur, t, "nearest");
    const k = r.error ? t : r.t;
    if (k <= V.inT + 1e-3 || k >= V.outT - 1e-3) { toast("No keyframe inside the selection to split at", "warn"); return; }
    const v = V.videos.get(V.cur);
    pushHist();
    V.segs.push({ id: V.cur, start: V.inT, end: k, name: v.name }, { id: V.cur, start: k, end: V.outT, name: v.name });
    V.sel = V.segs.length - 1; renderSegs();
    $("#vSnapHint").textContent = Math.abs(k - t) > 1e-3 ? `Split at the keyframe at ${tc(k, fps())}, the nearest lossless cut point.` : "";
    toast(`Split into segments ${V.segs.length - 1} and ${V.segs.length}`, "ok");
  }
  function pushHist() { V.hist.push(V.segs.map((s) => ({ ...s }))); if (V.hist.length > 50) V.hist.shift(); }
  function undo() { if (!V.hist.length) { toast("Nothing to undo", "info"); return; } V.segs = V.hist.pop(); V.sel = Math.min(V.sel, V.segs.length - 1); renderSegs(); toast("Undone", "info"); }
  function clearSegs() { if (!V.segs.length) return; pushHist(); V.segs = []; V.sel = -1; renderSegs(); toast("Segments cleared. Ctrl+Z brings them back.", "info"); }
  function timelineMenu(e) {
    if (!V.cur) return;
    e.preventDefault(); coach(false);
    const t = x2t(e.clientX), f = fps();
    window.popover(null, [
      { label: `Mark in here`, hint: tc(t, f), run: () => { setIn(t); seek(t); } },
      { label: `Mark out here`, hint: tc(t, f), run: () => { setOut(t); seek(t); } },
      { label: "Split the selection here", hint: "two segments", disabled: !(t > V.inT && t < V.outT), run: () => splitAt(t) },
      "-",
      { label: "Add segment", hint: `${tc(V.inT, f)} → ${tc(V.outT, f)}`, disabled: V.outT - V.inT < 1e-3, run: addSegment },
      { label: "Play from here", run: () => { seek(t); V.previewEnd = null; P.play(); } },
      { label: "Reset in and out", run: resetSel },
    ], { x: e.clientX, y: e.clientY });
  }
  function segMenu(i, e) {
    e.preventDefault(); e.stopPropagation();
    const s = V.segs[i]; if (!s) return;
    window.popover(null, [
      { label: "Play this segment", run: () => previewSeg(i) },
      { label: "Load into in and out", hint: "to adjust it, then Add segment again", run: () => { previewSeg(i); P.pause(); } },
      "-",
      { label: "Move earlier", disabled: i === 0, run: () => moveSeg(i, -1) },
      { label: "Move later", disabled: i === V.segs.length - 1, run: () => moveSeg(i, 1) },
      "-",
      { label: "Remove", danger: true, run: () => removeSeg(i) },
    ], { x: e.clientX, y: e.clientY });
  }
  function moveSeg(i, d) { const j = i + d; if (j < 0 || j >= V.segs.length) return; pushHist(); [V.segs[i], V.segs[j]] = [V.segs[j], V.segs[i]]; V.sel = j; renderSegs(); }
  function removeSeg(i) { pushHist(); V.segs.splice(i, 1); V.sel = Math.min(V.sel, V.segs.length - 1); renderSegs(); }
  function bindTimeline() {
    const tl = $("#vTimeline");
    let drag = null;
    tl.addEventListener("pointerdown", (e) => {
      if (!V.cur) return;
      if (e.button === 2) return;
      const h = e.target.closest(".v-handle");
      drag = h ? (h.id === "vIn" ? "in" : "out") : "seek";
      if (h) coach(false);
      tl.setPointerCapture?.(e.pointerId);
      move(e); e.preventDefault();
    });
    const move = (e) => {
      const t = x2t(e.clientX);
      const c = $("#vCursor"); c.style.left = t2pct(t); c.textContent = tc(t, fps());
      if (!drag) return;
      if (drag === "seek") seek(t);
      else if (drag === "in") { V.inT = Math.min(t, V.outT); layoutRange(); seek(V.inT); }
      else { V.outT = Math.max(t, V.inT); layoutRange(); seek(V.outT); }
    };
    tl.addEventListener("pointermove", move);
    const up = () => { if (!drag) return; const d = drag; drag = null; if (d === "in") setIn(V.inT); else if (d === "out") setOut(V.outT); };
    tl.addEventListener("pointerup", up); tl.addEventListener("pointercancel", up);
    tl.addEventListener("dblclick", (e) => { e.preventDefault(); togglePlay(); });
    tl.addEventListener("contextmenu", timelineMenu);
    new ResizeObserver(() => { if (V.cur && V.open) { renderRuler(); renderTicks(); loadStripDebounced(); } }).observe(tl);
    // typed in and out points
    const bindTc = (inp, apply) => {
      inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { const t = parseTc(inp.value, fps()); if (isNaN(t)) { toast("Use hh:mm:ss:ff, mm:ss or seconds", "warn"); return; } apply(clamp(t, 0, dur())); inp.blur(); } if (e.key === "Escape") { layoutRange(); inp.blur(); } });
      inp.addEventListener("blur", () => layoutRange());
    };
    bindTc($("#vInTc"), (t) => { setIn(t); seek(t); });
    bindTc($("#vOutTc"), (t) => { setOut(t); seek(t); });
  }
  let stripTimer = 0;
  function loadStripDebounced() { clearTimeout(stripTimer); stripTimer = setTimeout(() => V.cur && loadStrip(V.cur), 400); }

  // ------------------------------------------------------------- segments
  function addSegment() {
    if (!V.cur || V.outT - V.inT < 1e-3) return;
    const v = V.videos.get(V.cur);
    pushHist(); coach(false);
    V.segs.push({ id: V.cur, start: V.inT, end: V.outT, name: v.name });
    V.sel = V.segs.length - 1;
    renderSegs(); toast(`Segment ${V.segs.length} added: ${secs(V.outT - V.inT)}`, "ok");
  }
  function renderSegs() {
    const box = $("#vSegments"); box.innerHTML = "";
    if (!V.segs.length) { box.appendChild(el("span", "empty", V.cur ? "Mark in and out above, then Add segment. Segments are exported in the order shown here." : "")); updateExportBtn(); return; }
    V.segs.forEach((s, i) => {
      const v = V.videos.get(s.id); const f = v?.info?.video?.fps || 0;
      const d = el("div", "v-seg" + (i === V.sel ? " on" : ""));
      d.title = `${s.name}\n${tc(s.start, f)} to ${tc(s.end, f)}\nClick to play this segment.`;
      d.innerHTML = `<span class="n">${i + 1}</span><span class="nm">${esc(s.name)}</span><span class="rg">${tc(s.start, f)} → ${tc(s.end, f)} · ${secs(s.end - s.start)}</span>
        <span class="mv" title="Move earlier">‹</span><span class="mv" title="Move later">›</span><span class="rm" title="Remove segment">✕</span>`;
      const [left, right] = d.querySelectorAll(".mv"); const rm = d.querySelector(".rm");
      left.addEventListener("click", (e) => { e.stopPropagation(); moveSeg(i, -1); });
      right.addEventListener("click", (e) => { e.stopPropagation(); moveSeg(i, 1); });
      rm.addEventListener("click", (e) => { e.stopPropagation(); removeSeg(i); });
      d.addEventListener("click", () => previewSeg(i));
      d.addEventListener("contextmenu", (e) => segMenu(i, e));
      box.appendChild(d);
    });
    const total = V.segs.reduce((a, s) => a + s.end - s.start, 0);
    const tot = el("span", "v-total", `<span>${V.segs.length} segment${V.segs.length > 1 ? "s" : ""} · ${hms(total)} total</span><button class="ghost tiny" title="Undo the last change to the segments (Ctrl+Z)">Undo</button><button class="ghost tiny" title="Remove every segment (Ctrl+Z brings them back)">Clear all</button>`);
    const [u, cl] = tot.querySelectorAll("button"); u.addEventListener("click", undo); cl.addEventListener("click", clearSegs);
    box.appendChild(tot);
    updateExportBtn();
  }
  function previewSeg(i) {
    const s = V.segs[i]; if (!s) return;
    V.sel = i; renderSegs();
    if (V.cur !== s.id) select(s.id);
    V.inT = s.start; V.outT = s.end; layoutRange();
    const go = () => { seek(s.start); V.previewEnd = s.end; P.play(); };
    if (P.readyState >= 1) go(); else P.addEventListener("loadedmetadata", go, { once: true });
  }

  // ------------------------------------------------------------- frame
  const FRAMES = {
    "9:16": { r: [9, 16], up: [1080, 1920], for: "YouTube Shorts, Instagram Reels, TikTok and Stories" },
    "4:5": { r: [4, 5], up: [1080, 1350], for: "Instagram feed posts in portrait" },
    "1:1": { r: [1, 1], up: [1080, 1080], for: "Instagram feed posts in square" },
    "16:9": { r: [16, 9], up: [1920, 1080], for: "YouTube videos and landscape feeds" },
  };
  const even = (n, lo = 2) => Math.max(lo, Math.floor(n / 2) * 2);
  function cropRect(sw, sh, frame, cx, cy) {
    // the same arithmetic as the exporter, so the window drawn here is the window that is cut
    const [rw, rh] = FRAMES[frame].r;
    let w, h;
    if (sw * rh > sh * rw) { h = even(sh); w = even(sh * rw / rh); } else { w = even(sw); h = even(sw * rh / rw); }
    w = Math.min(w, even(sw)); h = Math.min(h, even(sh));
    const x = even(Math.min(Math.max(cx * sw - w / 2, 0), sw - w), 0), y = even(Math.min(Math.max(cy * sh - h / 2, 0), sh - h), 0);
    return { w, h, x, y };
  }
  function framePlan() {
    const v = V.videos.get(V.cur); if (!v?.info || V.frame === "source") return null;
    const sw = v.info.video.width, sh = v.info.video.height;
    const c = cropRect(sw, sh, V.frame, V.cx, V.cy);
    let ow = c.w, oh = c.h;
    if (V.fsize === "upload") { const [uw, uh] = FRAMES[V.frame].up; if (c.w > uw || c.h > uh) { ow = uw; oh = uh; } }
    return { ...c, sw, sh, ow, oh, scale: ow !== c.w || oh !== c.h, crop: !(c.w === sw && c.h === sh), changes: !(c.w === sw && c.h === sh) || ow !== c.w || oh !== c.h };
  }
  function videoBox() {
    // where the picture sits inside the stage under object-fit: contain
    const st = $("#vStage").getBoundingClientRect(); const v = V.videos.get(V.cur);
    const sw = v?.info?.video?.width || P.videoWidth || 16, sh = v?.info?.video?.height || P.videoHeight || 9;
    const k = Math.min(st.width / sw, st.height / sh), w = sw * k, h = sh * k;
    return { left: (st.width - w) / 2, top: (st.height - h) / 2, width: w, height: h, k };
  }
  function layoutCrop() {
    const box = $("#vCrop"), p = framePlan();
    if (!p || $("#vStage").classList.contains("empty")) { box.classList.add("hidden"); return; }
    box.classList.remove("hidden");
    const b = videoBox(), win = $("#vCropWin");
    win.style.left = (b.left + p.x * b.k) + "px"; win.style.top = (b.top + p.y * b.k) + "px";
    win.style.width = (p.w * b.k) + "px"; win.style.height = (p.h * b.k) + "px";
    win.classList.toggle("full", !p.crop);
    $("#vCropTag").textContent = `${V.frame} · ${p.w}×${p.h}` + (p.scale ? ` → ${p.ow}×${p.oh}` : "");
  }
  function frameNote() {
    const p = framePlan();
    if (!p) return "";
    if (!p.changes) return `${FRAMES[V.frame].for}. This recording is already ${V.frame}, so it is copied losslessly as it is.`;
    const size = p.scale ? `Scaled to ${p.ow}×${p.oh}, the largest size the platform keeps.` : `${p.w}×${p.h}, every pixel inside the window kept.`;
    return `${FRAMES[V.frame].for}. ${p.crop ? "Drag the window on the player to choose what stays in the picture. " : ""}${size} Re-encoded on the GPU at near-lossless quality with the HDR metadata carried across.`;
  }
  function setFrame(f) {
    V.frame = f;
    [...$("#vFrame").children].forEach((b) => b.classList.toggle("on", b.dataset.v === f));
    renderFrame();
  }
  function renderFrame() {
    const p = framePlan(), on = !!p && p.changes;
    $("#vSizeRow").classList.toggle("hidden", V.frame === "source");
    $("#vFrameNote").textContent = frameNote();
    $("#vKeepLossless").classList.toggle("hidden", on);
    $("#vKeepFrame").classList.toggle("hidden", !on);
    layoutCrop(); updateExportBtn();
  }
  function bindCrop() {
    const win = $("#vCropWin"); let drag = null;
    win.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return; const p = framePlan(); if (!p || !p.crop) return;
      drag = { x: e.clientX, y: e.clientY, cx: V.cx, cy: V.cy, k: videoBox().k, sw: p.sw, sh: p.sh };
      win.setPointerCapture?.(e.pointerId); e.preventDefault(); e.stopPropagation();
    });
    win.addEventListener("pointermove", (e) => {
      if (!drag) return;
      V.cx = clamp(drag.cx + (e.clientX - drag.x) / drag.k / drag.sw, 0, 1);
      V.cy = clamp(drag.cy + (e.clientY - drag.y) / drag.k / drag.sh, 0, 1);
      layoutCrop();
    });
    const up = () => { drag = null; };
    win.addEventListener("pointerup", up); win.addEventListener("pointercancel", up);
    win.addEventListener("click", (e) => e.stopPropagation());
    win.addEventListener("dblclick", (e) => { e.stopPropagation(); V.cx = 0.5; V.cy = 0.5; layoutCrop(); });
    new ResizeObserver(() => { if (V.open) layoutCrop(); }).observe($("#vStage"));
  }

  // ------------------------------------------------------------- export
  function updateExportBtn() {
    const running = V.job?.running, n = V.segs.length, join = V.join && n > 1;
    $("#vExport").disabled = running || !n || !(V.ff?.found ?? true);
    $("#vExport").textContent = running ? "Exporting…" : !n ? "Export" : join ? "Export 1 joined file" : `Export ${n} file${n === 1 ? "" : "s"}`;
    $("#vNameRow").classList.toggle("hidden", !join);
    const total = V.segs.reduce((a, s) => a + s.end - s.start, 0);
    const srcs = new Set(V.segs.map((s) => s.id)).size;
    const p = framePlan();
    $("#vSummary").innerHTML = !n ? "No segments yet. Each segment you add becomes a file here, or part of one joined file."
      : `<b>${n} segment${n > 1 ? "s" : ""}</b> from ${srcs} recording${srcs > 1 ? "s" : ""}, <b>${hms(total)}</b> in total, ${join ? "joined into <b>one file</b>" : n > 1 ? "as <b>separate files</b>" : "as <b>one file</b>"}${p?.changes ? `, framed <b>${V.frame}</b> at ${p.ow}×${p.oh}` : ""}.`;
  }
  async function doExport() {
    if (!V.segs.length) return;
    const segs = V.segs.map((s) => ({ id: s.id, start: s.start, end: s.end }));
    $("#vResults").innerHTML = "";
    showProgress(0, "starting");
    const frame = V.frame === "source" ? null : { frame: V.frame, cx: V.cx, cy: V.cy, size: V.fsize };
    const r = await api.video_export(segs, V.join && V.segs.length > 1, V.where === "folder" ? V.folder : "", $("#vName").value.trim(), frame);
    if (r.error) { hideProgress(); toast(`Export: ${r.error}`, "err"); return; }
    V.job = r; updateExportBtn();
  }
  function showProgress(pct, msg) { $("#vProgress").classList.remove("hidden"); $("#vFill").style.width = clamp(pct, 0, 100) + "%"; $("#vPmsg").textContent = msg || ""; updateExportBtn(); }
  function hideProgress() { $("#vProgress").classList.add("hidden"); }
  function renderResults(job) {
    const box = $("#vResults"); box.innerHTML = "";
    if (job.error) { box.appendChild(el("div", "v-result", `<div class="nm bad">Export failed</div><div>${esc(job.error)}</div>`)); return; }
    for (const rep of job.verify || []) {
      const d = el("div", "v-result");
      const rows = (rep.rows || []).map((r) => `<tr><td>${esc(r.label)}</td><td class="${r.ok ? "" : "diff"}">${esc(r.ok ? (r.source && r.source !== r.output ? `${r.output} · from ${r.source}` : r.output) : `${r.output} (source: ${r.source})`)}</td></tr>`).join("");
      const rf = rep.reframed;
      const head = rf ? (rep.all_ok ? `✓ ${rf.frame} · ${rf.size[0]}×${rf.size[1]} · HDR kept · ${rf.encoder}` : "⚠ Not what was asked for") : (rep.all_ok ? "✓ Matches the source" : "⚠ Differs from the source");
      d.innerHTML = `<div class="nm">${esc(rep.output.split(/[\\/]/).pop())}</div>
        <div class="${rep.all_ok ? "ok" : "bad"}">${esc(head)} · ${hms(rep.duration)} · ${fmtSize(rep.size)}</div>
        <details${rep.all_ok ? "" : " open"}><summary>${esc(rep.summary)}</summary><table>${rows}</table></details>
        <div class="acts"><button class="ghost tiny" data-open>Open</button><button class="ghost tiny" data-reveal>Show in folder</button><button class="ghost tiny" data-add>Add to editor</button></div>`;
      d.querySelector("[data-open]").addEventListener("click", () => api.open_path(rep.output));
      d.querySelector("[data-reveal]").addEventListener("click", () => api.reveal(rep.output));
      d.querySelector("[data-add]").addEventListener("click", () => api.video_add([rep.output]));
      box.appendChild(d);
    }
  }

  // ------------------------------------------------------------- keys
  function key(e) {
    const inInput = e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA");
    if (e.key === "Escape") { if (inInput) { e.target.blur(); return true; } close(); return true; }
    if (inInput) return false;
    const f = fps() || 30, step = e.shiftKey ? 1 : 1 / f;
    switch (e.key) {
      case " ": togglePlay(); return true;
      case "i": case "I": setIn(P.currentTime); return true;
      case "o": case "O": setOut(P.currentTime); return true;
      case "p": case "P": previewSelection(); return true;
      case "s": case "S": splitAt(); return true;
      case "r": case "R": resetSel(); return true;
      case "z": case "Z": if (e.ctrlKey || e.metaKey) { undo(); return true; } return false;
      case "Enter": addSegment(); return true;
      case "ArrowLeft": P.pause(); seek(P.currentTime - step); return true;
      case "ArrowRight": P.pause(); seek(P.currentTime + step); return true;
      case "Home": seek(0); return true;
      case "End": seek(dur()); return true;
      case "[": jumpKey("prev"); return true;
      case "]": jumpKey("next"); return true;
      case "Delete": case "Backspace": if (V.sel >= 0 && V.segs[V.sel]) removeSeg(V.sel); return true;
    }
    return false;
  }
  async function jumpKey(dir) {
    if (!V.cur) return; P.pause();
    const t = P.currentTime + (dir === "next" ? 0.02 : -0.02);
    const r = await api.video_snap(V.cur, t, dir);
    if (!r.error) { V.keys = r.keyframes || V.keys; renderTicks(); seek(r.t); }
  }

  // ------------------------------------------------------------- wiring
  document.addEventListener("DOMContentLoaded", () => {
    P = $("#vPlayer");
    P.addEventListener("error", playerError);
    P.addEventListener("play", () => { cancelAnimationFrame(V.raf); V.raf = requestAnimationFrame(tick); renderTime(P.currentTime); });
    P.addEventListener("pause", () => { cancelAnimationFrame(V.raf); renderTime(P.currentTime); });
    P.addEventListener("ended", () => renderTime(P.currentTime));
    P.addEventListener("loadedmetadata", () => { renderTime(0); layoutCrop(); });
    P.addEventListener("click", togglePlay);
    $("#vAdd").addEventListener("click", () => api.video_pick());
    $("#vPlay").addEventListener("click", togglePlay);
    $("#vPrevKey").addEventListener("click", () => jumpKey("prev"));
    $("#vNextKey").addEventListener("click", () => jumpKey("next"));
    $("#vSetIn").addEventListener("click", (e) => { e.preventDefault(); coach(false); setIn(P.currentTime); });
    $("#vSetOut").addEventListener("click", (e) => { e.preventDefault(); coach(false); setOut(P.currentTime); });
    $("#vSplit").addEventListener("click", () => splitAt());
    $("#vReset").addEventListener("click", resetSel);
    $("#vGuideAdd").addEventListener("click", (e) => { e.stopPropagation(); api.video_pick(); });
    $("#vStage").addEventListener("click", (e) => { if ($("#vStage").classList.contains("empty")) api.video_pick(); });
    $("#vBinEmpty").addEventListener("click", () => api.video_pick());
    $("#vPreview").addEventListener("click", previewSelection);
    $("#vAddSeg").addEventListener("click", addSegment);
    $("#vExport").addEventListener("click", doExport);
    $("#vJoin").addEventListener("click", () => { V.join = !V.join; $("#vJoin").classList.toggle("on", V.join); updateExportBtn(); });
    $("#vWhere").addEventListener("click", async (e) => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.v === "folder") { const f = await api.video_pick_folder(); if (!f) return; V.folder = f; }
      V.where = b.dataset.v; [...$("#vWhere").children].forEach((x) => x.classList.toggle("on", x === b));
      $("#vFolder").textContent = V.where === "folder" ? V.folder : "";
    });
    $("#vFrame").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) setFrame(b.dataset.v); });
    $("#vSize").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; V.fsize = b.dataset.v; [...$("#vSize").children].forEach((x) => x.classList.toggle("on", x === b)); renderFrame(); });
    $("#vFfmpeg").addEventListener("click", () => { showProgress(0, "downloading FFmpeg"); api.ffmpeg_install(); });
    bindCrop();
    window.addEventListener("resize", () => { if (V.open) placePanel(); });
    bindTimeline();
    renderSegs(); updateExportBtn();
  });

  return { open, close, isOpen, on, key };
})();
