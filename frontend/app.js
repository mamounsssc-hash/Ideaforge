// IdeaForge Clipper — front-end logic (vanilla JS, no build step).
const $ = (s) => document.querySelector(s);
const API = "";
const APP_VERSION = "2.5";

// On load, confirm the backend is the same version as this page. A mismatch
// means the Python files weren't updated (or the browser cached the old page).
(async () => {
  try {
    const v = (await (await fetch("/api/version")).json()).version;
    const pill = $("#versionPill");
    if (!pill) return;
    if (v === APP_VERSION) { pill.textContent = "v" + v + " ✓"; pill.style.background = "#123a1f"; pill.style.color = "#7ff0a8"; }
    else { pill.textContent = "backend v" + v + " ≠ page v" + APP_VERSION; pill.style.background = "#3a1212"; pill.style.color = "#ff9a9a"; }
  } catch { /* backend not reachable yet */ }
})();

let currentJob = null;
let styles = [];
let mode = "clip";

// ---------- mode switch (clip vs create) ----------
document.querySelectorAll(".mode").forEach((b) => {
  b.addEventListener("click", async () => {
    document.querySelectorAll(".mode").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    mode = b.dataset.mode;
    $("#inputCard").classList.toggle("hidden", mode !== "clip");
    $("#createCard").classList.toggle("hidden", mode !== "create");
    ["progressCard", "resultsSection", "createResult"].forEach((id) => $("#" + id).classList.add("hidden"));
    if (mode === "create") await initCreate();
  });
});

// ---------- tabs ----------
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    const tab = t.dataset.tab;
    $("#pane-file").classList.toggle("hidden", tab !== "file");
    $("#pane-url").classList.toggle("hidden", tab !== "url");
    $("#pane-local").classList.toggle("hidden", tab !== "local");
  });
});

// ---------- file drop ----------
const dz = $("#dropzone");
const fileInput = $("#fileInput");
let chosenFile = null;
dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
dz.addEventListener("drop", (e) => {
  e.preventDefault(); dz.classList.remove("drag");
  if (e.dataTransfer.files.length) { chosenFile = e.dataTransfer.files[0]; $("#fileName").textContent = chosenFile.name; }
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) { chosenFile = fileInput.files[0]; $("#fileName").textContent = chosenFile.name; }
});

// ---------- start ----------
$("#startBtn").addEventListener("click", start);

function analyzeParams() {
  const language = $("#langSelect").value || null;
  const len = $("#lenSelect").value;
  const [mn, mx] = len ? len.split("-").map(Number) : [null, null];
  return {
    language,
    caption_language: $("#capLang").value,
    topic: $("#topicInput").value.trim(),
    min_seconds: mn,
    max_seconds: mx,
    target_count: parseInt($("#countInput").value) || null,
  };
}

async function start() {
  const activeTab = document.querySelector(".tab.active").dataset.tab;
  const p = analyzeParams();
  $("#startBtn").disabled = true;
  try {
    let jobId;
    if (activeTab === "file") {
      if (!chosenFile) { alert("Choose a video file first."); return; }
      const fd = new FormData();
      fd.append("file", chosenFile);
      const qs = new URLSearchParams();
      Object.entries(p).forEach(([k, v]) => { if (v !== null && v !== "") qs.append(k, v); });
      const r = await fetch("/api/upload?" + qs.toString(), { method: "POST", body: fd });
      jobId = (await r.json()).job_id;
    } else if (activeTab === "local") {
      const path = $("#localInput").value.trim();
      if (!path) { alert("Paste the full path to a video file on your PC."); return; }
      const r = await fetch("/api/local", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, ...p }),
      });
      if (!r.ok) { alert("Could not open that file: " + (await r.json()).detail); return; }
      jobId = (await r.json()).job_id;
    } else {
      const u = $("#urlInput").value.trim();
      if (!u) { alert("Paste a video URL first."); return; }
      const r = await fetch("/api/url", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: u, ...p }),
      });
      jobId = (await r.json()).job_id;
    }
    currentJob = jobId;
    $("#inputCard").classList.add("hidden");
    $("#progressCard").classList.remove("hidden");
    trackProgress(jobId);
  } catch (err) {
    alert("Failed to start: " + err);
  } finally {
    $("#startBtn").disabled = false;
  }
}

// ---------- progress via websocket (falls back to polling) ----------
function trackProgress(jobId) {
  const wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/" + jobId;
  let ws;
  try { ws = new WebSocket(wsUrl); } catch { return poll(jobId); }
  ws.onmessage = (ev) => handleState(JSON.parse(ev.data));
  ws.onerror = () => poll(jobId);
}
async function poll(jobId) {
  const r = await fetch(`/api/jobs/${jobId}`);
  const state = await r.json();
  handleState(state);
  if (state.status !== "ready" && state.status !== "error") setTimeout(() => poll(jobId), 800);
}
function handleState(s) {
  $("#progBar").style.width = Math.round((s.progress || 0) * 100) + "%";
  $("#progMsg").textContent = s.message || "";
  $("#progTitle").textContent = titleFor(s.status);
  if (s.status === "error") { $("#progMsg").textContent = "Error: " + s.error; return; }
  if (s.status === "ready") {
    if (s.kind === "create") { showCreateResult(s); } else { showResults(s); }
  }
}

// ---------- create mode ----------
let createReady = false;
async function initCreate() {
  await loadStyles();
  // clone styles into the create-mode select
  const cs = $("#createStyle");
  if (!cs.options.length) cs.innerHTML = $("#styleSelect").innerHTML;
  const vs = $("#voiceSelect");
  if (!vs.options.length) {
    try {
      const voices = await (await fetch("/api/voices")).json();
      voices.forEach((v) => { const o = document.createElement("option"); o.value = v.id; o.textContent = v.name; vs.appendChild(o); });
    } catch { /* ignore */ }
  }
}

$("#bgSelect")?.addEventListener("change", () => {
  const v = $("#bgSelect").value;
  document.querySelectorAll(".bg-color-only").forEach((e) => e.style.display = v === "color" ? "" : "none");
  document.querySelectorAll(".bg-video-only").forEach((e) => e.style.display = v === "video" ? "" : "none");
  document.querySelectorAll(".bg-pexels-only").forEach((e) => e.style.display = v === "pexels" ? "" : "none");
});

$("#createBtn")?.addEventListener("click", async () => {
  const script = $("#scriptInput").value.trim();
  const topic = $("#createTopic").value.trim();
  if (!script && !topic) { alert("Write a script or a topic."); return; }
  const opts = {
    script, topic, voice: $("#voiceSelect").value,
    style_id: $("#createStyle").value, aspect_ratio: $("#createAspect").value,
    background: $("#bgSelect").value,
    background_color: $("#bgColorA").value.replace("#", ""),
    background_color2: $("#bgColorB").value.replace("#", ""),
    background_query: $("#bgQuery").value || "satisfying",
    burn_captions: $("#c_captions").checked, highlight_keywords: $("#c_keywords").checked,
    add_emojis: $("#c_emojis").checked, hook_title: $("#c_hook").checked,
    progress_bar: $("#c_bar").checked, auto_zoom: $("#c_zoom").checked,
    zoom_punch: $("#c_zoompunch").checked, color_grade: $("#c_grade").value,
    sfx: $("#c_sfx").value, cta_text: $("#c_cta").value || "",
    music_volume: parseFloat($("#createMusicVol").value) || 0,
  };
  const fd = new FormData();
  fd.append("options", JSON.stringify(opts));
  if ($("#bgFile").files[0]) fd.append("background", $("#bgFile").files[0]);
  if ($("#createMusic").files[0]) fd.append("music", $("#createMusic").files[0]);
  $("#createBtn").disabled = true;
  try {
    const r = await fetch("/api/create", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    currentJob = (await r.json()).job_id;
    $("#createCard").classList.add("hidden");
    $("#progressCard").classList.remove("hidden");
    trackProgress(currentJob);
  } catch (err) {
    alert("Failed: " + err.message);
  } finally {
    $("#createBtn").disabled = false;
  }
});

function showCreateResult(s) {
  $("#progressCard").classList.add("hidden");
  $("#createResult").classList.remove("hidden");
  if (s.output_url) {
    $("#createPreview").src = s.output_url;
    $("#createDownload").href = s.output_url;
  }
}
function titleFor(st) {
  return {
    downloading: "Downloading source…", transcribing: "Transcribing…",
    analyzing: "Finding the best moments…", ranking: "Refining picks…",
    ready: "Done!", queued: "Queued…",
  }[st] || "Working…";
}

// ---------- results ----------
async function loadStyles() {
  if (styles.length) return;
  styles = await (await fetch("/api/styles")).json();
  const sel = $("#styleSelect");
  const groups = {};
  styles.forEach((s) => { (groups[s.group] = groups[s.group] || []).push(s); });
  sel.innerHTML = "";
  Object.keys(groups).forEach((g) => {
    const og = document.createElement("optgroup"); og.label = g;
    groups[g].forEach((s) => {
      const o = document.createElement("option"); o.value = s.id; o.textContent = s.name; og.appendChild(o);
    });
    sel.appendChild(og);
  });
}

async function showResults(s) {
  await loadStyles();
  $("#progressCard").classList.add("hidden");
  $("#resultsSection").classList.remove("hidden");
  $("#clipCount").textContent = `· ${s.clips.length} found · ${s.language || ""}`;
  const list = $("#clipList");
  list.innerHTML = "";
  s.clips.forEach((c) => list.appendChild(clipRow(c)));
}

function scoreColor(v) {
  if (v >= 75) return "#31e36b";
  if (v >= 55) return "#f5d40a";
  return "#8b93a7";
}
function fmt(t) {
  const m = Math.floor(t / 60), sec = Math.floor(t % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function clipRow(c) {
  const el = document.createElement("div");
  el.className = "clip";
  const col = scoreColor(c.score.total);
  el.innerHTML = `
    <div class="score" style="color:${col};border-color:${col}">
      ${Math.round(c.score.total)}<small>SCORE</small>
    </div>
    <div class="clip-body">
      <div class="clip-title">${escapeHtml(c.title || "Clip")}
        <span class="tag">${c.duration}s</span>
        <span class="tag">${fmt(c.start)}–${fmt(c.end)}</span>
        <span class="tag">${c.score.source}</span>
      </div>
      <div class="clip-meta">${c.reason ? escapeHtml(c.reason) : hookLabel(c.score)}</div>
      <div class="clip-text">${escapeHtml(c.text)}</div>
      <div class="hashtags">${(c.hashtags || []).map((h) => `<span>${escapeHtml(h)}</span>`).join("")}</div>
      <button class="edit-link">✎ Edit / trim</button>
      <button class="edit-link cap-link">✎ Edit captions</button>
      <button class="preview-link" title="Watch the clip with live captions before rendering">▶ معاينة / Preview</button>
      <button class="frame-link" title="See the video and choose which person / where to frame">🎯 اختر الوجه / Frame</button>
      ${c.social_caption ? `<button class="copy-cap" title="Copy post caption">⧉ Copy caption</button>` : ""}
      <div class="preview-box"></div>
      <div class="frame-picker"></div>
      <div class="edit-panel">
        <input class="t-title" type="text" placeholder="Title / hook" value="${escapeHtml(c.title || "")}" />
        <input class="t-num t-start" type="number" step="0.1" value="${c.start}" title="start (s)" />
        <input class="t-num t-end" type="number" step="0.1" value="${c.end}" title="end (s)" />
      </div>
      <div class="cap-editor"></div>
    </div>
    <div class="clip-actions">
      <button class="btn primary render-btn">Render</button>
    </div>`;
  const panel = el.querySelector(".edit-panel");
  el.querySelector(".edit-link").addEventListener("click", () => panel.classList.toggle("open"));

  // in-browser transcript editing
  const capEditor = el.querySelector(".cap-editor");
  el.querySelector(".cap-link").addEventListener("click", async () => {
    if (capEditor.classList.contains("open")) { capEditor.classList.remove("open"); return; }
    capEditor.classList.add("open");
    if (capEditor.dataset.loaded) return;
    capEditor.innerHTML = "<span class='muted small'>Loading transcript…</span>";
    try {
      const data = await (await fetch(`/api/jobs/${currentJob}/clips/${c.id}/words`)).json();
      capEditor.innerHTML = "";
      const grid = document.createElement("div"); grid.className = "word-grid";
      const inputs = data.words.map((w) => {
        const inp = document.createElement("input");
        inp.type = "text"; inp.value = w.text; inp.className = "word-inp";
        inp.style.width = Math.max(3, w.text.length + 1) + "ch";
        inp.dataset.start = w.start; inp.dataset.end = w.end;
        inp.addEventListener("input", () => { inp.style.width = Math.max(3, inp.value.length + 1) + "ch"; });
        grid.appendChild(inp); return inp;
      });
      capEditor.appendChild(grid);
      const save = document.createElement("button");
      save.className = "btn ghost"; save.textContent = "Save captions"; save.style.marginTop = "8px";
      save.addEventListener("click", async () => {
        const words = inputs.map((i) => ({ start: +i.dataset.start, end: +i.dataset.end, text: i.value }));
        save.disabled = true; save.textContent = "Saving…";
        try {
          const res = await (await fetch(`/api/jobs/${currentJob}/clips/${c.id}/words`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ words }),
          })).json();
          c.text = res.text;
          el.querySelector(".clip-text").textContent = res.text;
          save.textContent = "✓ Saved";
        } catch { save.textContent = "Failed"; }
        setTimeout(() => { save.disabled = false; save.textContent = "Save captions"; }, 1400);
      });
      capEditor.appendChild(save);
      capEditor.dataset.loaded = "1";
    } catch { capEditor.innerHTML = "<span class='muted small'>Could not load transcript.</span>"; }
  });
  el.querySelector(".render-btn").addEventListener("click", (e) => {
    c._title = el.querySelector(".t-title").value;
    c._start = parseFloat(el.querySelector(".t-start").value);
    c._end = parseFloat(el.querySelector(".t-end").value);
    renderClip(c, e.target);
  });
  const cc = el.querySelector(".copy-cap");
  if (cc) cc.addEventListener("click", () => {
    navigator.clipboard.writeText((c.social_caption || "") + "\n\n" + (c.hashtags || []).join(" "));
    cc.textContent = "✓ Copied";
    setTimeout(() => (cc.textContent = "⧉ Copy caption"), 1500);
  });

  // visual frame picker: see the video, drag a 9:16 box onto the person you want
  const fp = el.querySelector(".frame-picker");
  el.querySelector(".frame-link").addEventListener("click", () => {
    if (fp.classList.contains("open")) { fp.classList.remove("open"); return; }
    fp.classList.add("open");
    if (fp.dataset.loaded) return;
    buildFramePicker(fp, c);
  });

  // in-browser preview with live captions (no render needed)
  const pv = el.querySelector(".preview-box");
  el.querySelector(".preview-link").addEventListener("click", () => {
    if (pv.classList.contains("open")) { pv.classList.remove("open"); const v = pv.querySelector("video"); if (v) v.pause(); return; }
    pv.classList.add("open");
    if (pv.dataset.loaded) return;
    buildPreview(pv, c);
  });

  return el;
}

// Play the clip's segment from the source video with a live caption overlay,
// so the user can judge a clip (and its captions) before committing to a render.
async function buildPreview(pv, c) {
  if (!currentJob) { pv.innerHTML = "<span class='muted small'>Analyze a video first.</span>"; return; }
  pv.innerHTML = "<span class='muted small'>⏳ Loading preview…</span>";
  const start = (c._start != null) ? c._start : c.start;
  const end = (c._end != null) ? c._end : c.end;

  // words for the live caption (fetch once, then cache on the clip)
  let words = c._words;
  if (!words) {
    try { words = (await (await fetch(`/api/jobs/${currentJob}/clips/${c.id}/words`)).json()).words; }
    catch { words = []; }
    c._words = words;
  }

  pv.innerHTML = "";
  const wrap = document.createElement("div"); wrap.className = "pv-wrap";
  const video = document.createElement("video");
  video.className = "pv-video"; video.controls = true; video.playsInline = true; video.preload = "auto";
  video.src = `/api/jobs/${currentJob}/source`;
  const caps = document.createElement("div"); caps.className = "pv-caps";
  wrap.appendChild(video); wrap.appendChild(caps);

  const bar = document.createElement("div"); bar.className = "pv-bar";
  const playBtn = document.createElement("button"); playBtn.className = "btn primary"; playBtn.textContent = "▶ شغّل المقطع";
  const info = document.createElement("span"); info.className = "muted small";
  info.textContent = `${fmt(start)} – ${fmt(end)} (${Math.round(end - start)}s)`;
  bar.appendChild(playBtn); bar.appendChild(info);

  pv.appendChild(wrap); pv.appendChild(bar);

  const seekStart = () => { try { video.currentTime = start; } catch {} };
  video.addEventListener("loadedmetadata", seekStart);
  playBtn.addEventListener("click", () => { seekStart(); video.play(); });

  // live caption: show a small window of words up to the current time
  const MAXW = 5;
  video.addEventListener("timeupdate", () => {
    const t = video.currentTime;
    if (t >= end) { video.pause(); seekStart(); caps.innerHTML = ""; return; }
    const said = words.filter((w) => w.start <= t + 0.02);
    const win = said.slice(-MAXW);
    caps.innerHTML = win.map((w, i) =>
      `<span class="${i === win.length - 1 ? "pv-active" : ""}">${escapeHtml(w.text)}</span>`
    ).join(" ");
  });

  pv.dataset.loaded = "1";
}

// Frame picker: shows a real frame from the clip; click/drag on the person to
// keep them when cropping 16:9 -> 9:16. Quick Left/Center/Right buttons always
// work (even if the preview image can't load), so there is always a way to pick.
function buildFramePicker(fp, c) {
  if (!currentJob) { fp.innerHTML = "<span class='muted small'>Analyze a video first.</span>"; return; }
  fp.innerHTML = "";

  const title = document.createElement("div");
  title.className = "muted small"; title.style.marginBottom = "6px";
  title.innerHTML = "🎯 <b>اضغط على الشخص الذي تريد إبقاءه</b> · click the person to keep";
  fp.appendChild(title);

  // always-visible quick buttons
  const quick = document.createElement("div"); quick.className = "fp-quick";
  [["◀ يسار", 0.0], ["● وسط", 0.5], ["يمين ▶", 1.0]].forEach(([label, val]) => {
    const b = document.createElement("button"); b.className = "btn ghost"; b.textContent = label;
    b.addEventListener("click", () => applyCrop(val));
    quick.appendChild(b);
  });
  fp.appendChild(quick);

  const wrap = document.createElement("div"); wrap.className = "fp-wrap"; wrap.style.display = "none";
  const box = document.createElement("div"); box.className = "fp-box";
  box.innerHTML = "<span class='fp-tag'>KEEP</span>";
  const imgEl = document.createElement("img"); imgEl.className = "fp-img";
  wrap.appendChild(imgEl); wrap.appendChild(box);
  fp.appendChild(wrap);

  const status = document.createElement("div"); status.className = "muted small"; status.style.marginTop = "6px";
  fp.appendChild(status);

  let cropX = (c._crop_x != null) ? c._crop_x : 0.5;
  let boxWFrac = 0.316, travel = 0.684;
  const place = () => { box.style.left = (cropX * travel * 100) + "%"; };

  function applyCrop(v) {
    cropX = Math.max(0, Math.min(1, v));
    c._crop_x = Math.round(cropX * 100) / 100;
    place();
    // this clip renders in Fill at this position (per-clip override in renderClip);
    // other clips keep the global layout, so we don't touch #opt_layout here.
    status.innerHTML = "✅ <b>محفوظ</b> — سيُطبّق عند Render · saved (" + Math.round(cropX * 100) + "%)";
  }
  place();

  status.textContent = "⏳ جاري تحميل صورة من الفيديو…";
  imgEl.onerror = () => { status.textContent = "تعذّر تحميل الصورة — استخدم أزرار يسار/وسط/يمين بالأعلى."; };
  imgEl.onload = () => {
    const aspect = imgEl.naturalWidth / imgEl.naturalHeight;
    boxWFrac = Math.min(1, (9 / 16) / aspect); travel = Math.max(0, 1 - boxWFrac);
    box.style.width = (boxWFrac * 100) + "%";
    wrap.style.display = "inline-block";
    place();
    status.textContent = "اضغط أو اسحب على الشخص · click or drag on the person";
  };
  imgEl.src = `/api/jobs/${currentJob}/clips/${c.id}/thumb?ts=${Date.now()}`;

  const setFromClientX = (clientX) => {
    const r = wrap.getBoundingClientRect();
    let leftFrac = (clientX - r.left) / r.width - boxWFrac / 2;
    leftFrac = Math.max(0, Math.min(travel, leftFrac));
    applyCrop(travel > 0 ? leftFrac / travel : 0.5);
  };
  let dragging = false;
  const down = (e) => { dragging = true; setFromClientX((e.touches ? e.touches[0] : e).clientX); e.preventDefault(); };
  const move = (e) => { if (dragging) setFromClientX((e.touches ? e.touches[0] : e).clientX); };
  const up = () => { dragging = false; };
  wrap.addEventListener("mousedown", down);
  window.addEventListener("mousemove", move);
  window.addEventListener("mouseup", up);
  wrap.addEventListener("touchstart", down, { passive: false });
  wrap.addEventListener("touchmove", move, { passive: false });
  wrap.addEventListener("touchend", up);

  fp.dataset.loaded = "1";
}
function hookLabel(sb) {
  const parts = [];
  if (sb.hook > 0.4) parts.push("strong hook");
  if (sb.emotion > 0.4) parts.push("emotional");
  if (sb.info > 0.4) parts.push("info-rich");
  if (sb.completeness > 0.8) parts.push("complete thought");
  return parts.join(" · ") || "clean cut";
}

function collectOptions() {
  return {
    style_id: $("#styleSelect").value,
    aspect_ratio: $("#aspectSelect").value,
    reframe: $("#opt_reframe").checked,
    burn_captions: $("#opt_captions").checked,
    highlight_keywords: $("#opt_keywords").checked,
    add_emojis: $("#opt_emojis").checked,
    hook_title: $("#opt_hook").checked,
    progress_bar: $("#opt_bar").checked,
    remove_fillers: $("#opt_fillers").checked,
    remove_silence: $("#opt_silence").checked,
    auto_zoom: $("#opt_zoom").checked,
    speaker_colors: $("#opt_speakers").checked,
    enhance_audio: $("#opt_enhance").checked,
    reframe_layout: $("#opt_layout").value,
    broll: $("#opt_broll").checked,
    music_volume: parseFloat($("#opt_musicvol").value) || 0,
    caption_position: $("#opt_cappos").value,
    caption_scale: parseFloat($("#opt_capscale").value) || 1,
    caption_offset: 0,
    crop_x: parseFloat($("#opt_cropx").value),
    color_grade: $("#opt_grade").value,
    zoom_punch: $("#opt_zoompunch").checked,
    sfx: $("#opt_sfx").value,
    cta_text: $("#opt_cta").value || "",
    gameplay: $("#opt_gameplay")?.checked || false,
    gameplay_split: parseFloat($("#opt_gamesplit")?.value) || 0.6,
    caption_reveal: $("#opt_reveal") ? $("#opt_reveal").checked : true,
    keyword_color: ($("#opt_kwcolor")?.value || "#31E981").replace("#", ""),
  };
}

// ---------- one-click templates ----------
const TEMPLATES = {
  beast:     { style: "beast",         grade: "punchy",    zoompunch: true,  sfx: "pop",    capscale: 1.1, cappos: "center", enhance: true,  emojis: true },
  podcast:   { style: "capcut_classic",grade: "none",      zoompunch: false, sfx: "none",   capscale: 1.0, cappos: "bottom", enhance: true,  emojis: true },
  hormozi:   { style: "hormozi_yellow",grade: "vibrant",   zoompunch: true,  sfx: "pop",    capscale: 1.05,cappos: "center", enhance: true,  emojis: true },
  gameplay:  { style: "beast",         grade: "punchy",    zoompunch: false, sfx: "none",   capscale: 1.0, cappos: "center", enhance: true,  emojis: true, gameplay: true },
  cinematic: { style: "clean_center",  grade: "cinematic", zoompunch: false, sfx: "whoosh", capscale: 1.0, cappos: "bottom", enhance: true,  emojis: false },
  minimal:   { style: "clean_white",   grade: "none",      zoompunch: false, sfx: "none",   capscale: 0.95,cappos: "bottom", enhance: false, emojis: false },
};
function setVal(id, v) { const el = $(id); if (el) { el.value = v; el.dispatchEvent(new Event("input")); } }
function setChk(id, v) { const el = $(id); if (el) el.checked = v; }
$("#templateSelect")?.addEventListener("change", (e) => {
  const t = TEMPLATES[e.target.value];
  if (!t) return;
  // pick the style if it exists in the dropdown
  const ss = $("#styleSelect");
  if (ss && [...ss.options].some((o) => o.value === t.style)) ss.value = t.style;
  setVal("#opt_grade", t.grade);
  setVal("#opt_sfx", t.sfx);
  setVal("#opt_capscale", t.capscale);
  setVal("#opt_cappos", t.cappos);
  setChk("#opt_zoompunch", t.zoompunch);
  setChk("#opt_enhance", t.enhance);
  setChk("#opt_emojis", t.emojis);
  if (t.gameplay !== undefined) setChk("#opt_gameplay", t.gameplay);
  const st = $("#batchStatus");
  if (st) { st.classList.remove("hidden"); st.textContent = `Template applied: ${e.target.selectedOptions[0].text}`; }
});

// caption-size label
$("#opt_capscale").addEventListener("input", (e) => {
  $("#capScaleVal").textContent = Math.round(parseFloat(e.target.value) * 100) + "%";
});

// frame-position label
$("#opt_cropx")?.addEventListener("input", (e) => {
  const v = parseFloat(e.target.value);
  const label = v < 0.34 ? "Left" : v > 0.66 ? "Right" : "Center";
  $("#cropXVal").textContent = label + " (" + Math.round(v * 100) + "%)";
});

// music upload (attaches to the current job)
$("#musicInput").addEventListener("change", async () => {
  const f = $("#musicInput").files[0];
  if (!f || !currentJob) return;
  const fd = new FormData(); fd.append("file", f);
  try {
    await fetch(`/api/jobs/${currentJob}/music`, { method: "POST", body: fd });
    if (parseFloat($("#opt_musicvol").value) === 0) $("#opt_musicvol").value = "0.3";
  } catch { /* ignore */ }
});

// gameplay split label
$("#opt_gamesplit")?.addEventListener("input", (e) => {
  const top = Math.round(parseFloat(e.target.value) * 100);
  $("#gameSplitVal").textContent = top + "% / " + (100 - top) + "%";
});

// gameplay video upload (attaches to the current job)
$("#gameplayInput")?.addEventListener("change", async () => {
  const f = $("#gameplayInput").files[0];
  if (!f) return;
  $("#gameplayName").textContent = "⏳ " + f.name;
  if (!currentJob) { $("#gameplayName").textContent = "Upload a video first, then add gameplay."; return; }
  const fd = new FormData(); fd.append("file", f);
  try {
    await fetch(`/api/jobs/${currentJob}/gameplay`, { method: "POST", body: fd });
    $("#opt_gameplay").checked = true;
    $("#gameplayName").textContent = "✅ " + f.name;
  } catch { $("#gameplayName").textContent = "⚠️ upload failed"; }
});

async function renderClip(c, btn) {
  btn.disabled = true; btn.textContent = "Rendering…";
  try {
    const overrides = {};
    if (c._title != null && c._title !== c.title) overrides.title_override = c._title;
    if (c._start != null && !isNaN(c._start)) overrides.start_override = c._start;
    if (c._end != null && !isNaN(c._end)) overrides.end_override = c._end;
    if (c._crop_x != null) { overrides.crop_x = c._crop_x; overrides.reframe_layout = "fill"; }
    const r = await fetch("/api/render", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, clip_id: c.id, ...collectOptions(), ...overrides }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    const data = await r.json();
    openModal(data.url);
  } catch (err) {
    alert("Render failed: " + err.message);
  } finally {
    btn.disabled = false; btn.textContent = "Render";
  }
}

// ---------- batch export ----------
$("#batchBtn").addEventListener("click", async () => {
  const btn = $("#batchBtn");
  const status = $("#batchStatus");
  btn.disabled = true; btn.textContent = "Rendering all…";
  status.classList.remove("hidden");
  status.textContent = "Starting…";
  try {
    const r = await fetch("/api/render_batch", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, clip_ids: [], ...collectOptions() }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    const { batch_id, total } = await r.json();
    // poll progress so exporting many clips shows a live count and never times out
    await new Promise((resolve) => {
      const tick = async () => {
        try {
          const s = await (await fetch(`/api/render_batch/${batch_id}`)).json();
          if (s.status === "running") {
            const failed = s.failed ? ` (${s.failed} skipped)` : "";
            status.textContent = `Rendering ${s.done}/${s.total}${failed}…`;
            setTimeout(tick, 1500);
          } else if (s.status === "ready") {
            const failed = s.failed ? ` · ${s.failed} skipped` : "";
            status.innerHTML = `✓ ${s.done - s.failed}/${total} clips ready${failed}. <a href="${s.url}" download>Download ZIP</a>`;
            const a = document.createElement("a"); a.href = s.url; a.download = ""; a.click();
            resolve();
          } else {
            status.textContent = "Batch failed: " + (s.error || "unknown error");
            resolve();
          }
        } catch (e) { setTimeout(tick, 2500); }   // transient error — keep polling
      };
      tick();
    });
  } catch (err) {
    status.textContent = "Batch failed: " + err.message;
  } finally {
    btn.disabled = false; btn.textContent = "Export all (ZIP)";
  }
});

// ---------- modal ----------
function openModal(url) {
  $("#preview").src = url;
  $("#downloadBtn").href = url;
  $("#modal").classList.remove("hidden");
}
$("#modalClose").addEventListener("click", () => {
  $("#modal").classList.add("hidden");
  $("#preview").pause();
});

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
}

// health check -> engine pill
fetch("/api/health").then((r) => r.json()).then((h) => {
  $("#enginePill").textContent = h.llm ? "local + model" : "local engine";
}).catch(() => {});
