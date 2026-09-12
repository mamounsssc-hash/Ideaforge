// IdeaForge Clipper — front-end logic (vanilla JS, no build step).
const $ = (s) => document.querySelector(s);
const API = "";

let currentJob = null;
let styles = [];

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

async function start() {
  const activeTab = document.querySelector(".tab.active").dataset.tab;
  const language = $("#langSelect").value || null;
  $("#startBtn").disabled = true;
  try {
    let jobId;
    if (activeTab === "file") {
      if (!chosenFile) { alert("Choose a video file first."); return; }
      const fd = new FormData();
      fd.append("file", chosenFile);
      const url = "/api/upload" + (language ? `?language=${language}` : "");
      const r = await fetch(url, { method: "POST", body: fd });
      jobId = (await r.json()).job_id;
    } else {
      const u = $("#urlInput").value.trim();
      if (!u) { alert("Paste a video URL first."); return; }
      const r = await fetch("/api/url", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: u, language }),
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
  if (s.status === "ready") { showResults(s); }
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
    </div>
    <div class="clip-actions">
      <button class="btn primary">Render</button>
    </div>`;
  el.querySelector("button").addEventListener("click", (e) => renderClip(c, e.target));
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

async function renderClip(c, btn) {
  const styleId = $("#styleSelect").value;
  btn.disabled = true; btn.textContent = "Rendering…";
  try {
    const r = await fetch("/api/render", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, clip_id: c.id, style_id: styleId,
        reframe: true, burn_captions: true }),
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
