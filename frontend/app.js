// IdeaForge Clipper — front-end logic (vanilla JS, no build step).
const $ = (s) => document.querySelector(s);
const API = "";

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
      ${c.social_caption ? `<button class="copy-cap" title="Copy post caption">⧉ Copy caption</button>` : ""}
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
  return el;
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
    color_grade: $("#opt_grade").value,
    zoom_punch: $("#opt_zoompunch").checked,
    sfx: $("#opt_sfx").value,
    cta_text: $("#opt_cta").value || "",
  };
}

// caption-size label
$("#opt_capscale").addEventListener("input", (e) => {
  $("#capScaleVal").textContent = Math.round(parseFloat(e.target.value) * 100) + "%";
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

async function renderClip(c, btn) {
  btn.disabled = true; btn.textContent = "Rendering…";
  try {
    const overrides = {};
    if (c._title != null && c._title !== c.title) overrides.title_override = c._title;
    if (c._start != null && !isNaN(c._start)) overrides.start_override = c._start;
    if (c._end != null && !isNaN(c._end)) overrides.end_override = c._end;
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
  status.textContent = "Rendering every clip in this style — this can take a while…";
  try {
    const r = await fetch("/api/render_batch", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, clip_ids: [], ...collectOptions() }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    const data = await r.json();
    status.innerHTML = `✓ ${data.count} clips rendered. <a href="${data.url}" download>Download ZIP</a>`;
    const a = document.createElement("a"); a.href = data.url; a.download = ""; a.click();
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
