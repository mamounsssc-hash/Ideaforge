# IdeaForge Clipper

A **free, fully local** alternative to Opus Clip / Crayo. Drop in a long video (file
or URL) and it finds the best moments, reframes them to vertical 9:16 while tracking
the speaker, and burns in professional animated captions — with **40+ styles**.

No paid APIs. No cloud. Your video never leaves your machine.

---

## Why this design

Commercial tools (Opus Clip, Crayo) and the open references (`supoclip`, `autoclip`)
all lean on **paid transcription** (AssemblyAI) and/or a **cloud LLM**. This project
replaces every paid piece with a local, free equivalent and adds a robustness layer
so it **never stalls and never cuts mid-sentence**:

### Clip selection = 3 layers with automatic fallback

| Layer | What it does | Needs a model? |
|------|--------------|----------------|
| **1. Clean boundaries** | `faster-whisper` word timestamps → cuts only on sentence ends / silence | No |
| **2. Heuristic scoring** | Ranks every candidate by hook, emotion, info, completeness, pacing → 0–99 score | No |
| **3. Smart re-rank (optional)** | Qwen3-VL / Hermes / any Ollama model re-orders the top picks and writes titles | Optional |

If the model is off, slow, or errors, the pipeline **silently drops to Layer 2** and
keeps going. You always get clean, ranked clips — the model is an upgrade, never a
dependency.

---

## Features

- **Input:** file upload or URL (YouTube / TikTok / X / … via `yt-dlp`).
- **Local transcription** with word-level timestamps (`faster-whisper`).
- **Highlight detection** with a transparent 0–99 virality-style score.
- **Speaker-tracking auto-reframe** (MediaPipe / OpenCV), with graceful
  center-crop and blurred-letterbox fallbacks.
- **Multiple aspect ratios:** 9:16, 4:5, 1:1, 16:9.
- **71 animated caption styles** (Hormozi, CapCut, Beast, Submagic-like, Gold, Neon,
  Fire, Cyber, Retro, and more) — word-by-word highlight, pop / bounce / fade,
  custom colors & fonts.
- **Persistent keyword highlighting** — important words stay colored, not just the
  spoken one.
- **Auto-emoji insertion** — a relevant emoji dropped next to punchy keywords.
- **Hook title banner** — the AI title rendered as a top overlay.
- **Silence removal** — internal dead-air is cut and captions are retimed to match.
- **Auto zoom / punch-in** — a subtle push-in for energy.
- **Speaker color-coding** — captions tinted per (approx) speaker turn.
- **Watermark / handle** — burn `@yourhandle` into a corner.
- **Background music** — mix a track under the clip at an adjustable volume.
- **Per-clip trim & title edit** — nudge start/end and rewrite the hook before render.
- **Caption placement controls** — position + size overrides without editing the style.
- **Progress bar** overlay along the bottom.
- **Filler removal** — “um / uh” dropped from captions.
- **Social copy** — per-clip post caption + hashtags (heuristic, LLM-upgradable),
  one-click copy.
- **Batch export** — render every clip in a chosen style and download one ZIP.
- **Optional B-roll** — keyword-driven Pexels cutaways (free API key, safe no-op
  without one).
- **Add your own styles** by editing one JSON file — no code.
- **Optional Qwen3-VL vision re-ranking** — sends a keyframe per clip so a visual
  model can judge on-screen action, not just the transcript.

Every feature above is a toggle in the results view, applied per-render and to the
batch export.

**Transcription models:** only the two best are used and pre-downloaded —
`large-v3` (highest accuracy, default) and `medium` (lighter / faster). Anything
else set in config falls back to `large-v3`.

---

## Quick start

### Requirements
- Python 3.10+
- **ffmpeg** (must be on PATH) — `brew install ffmpeg` / `sudo apt install ffmpeg` /
  `winget install Gyan.FFmpeg`

### macOS / Linux
```bash
./scripts/setup.sh        # creates .venv, installs deps
./scripts/fetch_fonts.sh  # optional: nicer caption fonts
./scripts/run.sh          # http://127.0.0.1:8000
```

### Windows (PowerShell)
```powershell
.\scripts\setup.ps1
.\scripts\run.ps1         # opens http://127.0.0.1:8000
```

Then open the page, drop a video (or paste a URL), pick a caption style, and hit
**Render** on any clip.

---

## Connecting your local models (Qwen3-VL / Hermes)

Copy `.env.example` to `backend/.env` and set:

```ini
IDEAFORGE_LLM_ENABLED=true
IDEAFORGE_LLM_BASE_URL=http://localhost:11434/v1   # Ollama / LM Studio / Qwen3-VL server
IDEAFORGE_LLM_MODEL=qwen2.5:7b
IDEAFORGE_LLM_VISION=true                          # only for a Qwen3-VL vision server
```

Any **OpenAI-compatible** endpoint works. Turn it off any time — the app keeps working
on heuristics.

---

## Architecture

```
backend/app/
  main.py                 FastAPI: upload / url / status / styles / render / files
  jobs.py                 in-memory job store + progress
  config.py  models.py    settings & shared types
  pipeline/
    download.py           yt-dlp + ffprobe
    transcribe.py         faster-whisper (word timestamps)   [Layer 1]
    segment.py            sentence/silence boundaries + candidates
    score.py              heuristic 0–99 scoring + dedupe     [Layer 2]
    llm.py                optional OpenAI-compatible re-rank + social copy [Layer 3]
    keywords.py           keyword extraction, auto-emoji, hashtags
    tighten.py            internal silence removal + caption retiming
    speakers.py           approximate speaker turns for color-coding
    reframe.py            face tracking → target-ratio crop path
    captions.py           style → animated ASS (highlight, emoji, hook, speakers…)
    broll.py              optional Pexels B-roll cutaways
    render.py             ffmpeg chain: tighten → reframe/zoom/captions/watermark/bar → B-roll → music
    orchestrator.py       runs the whole flow, updates progress
  styles/catalog.json     71 caption styles (edit to add more)
frontend/                 vanilla JS single-page UI
scripts/                  setup / run / fonts (bash + PowerShell)
```

## Adding a caption style

Append an object to `backend/app/styles/catalog.json`:

```json
{
  "id": "my_style", "name": "My Style", "group": "Custom",
  "font": "Anton", "font_size": 90, "bold": true, "uppercase": true,
  "primary_color": "FFFFFF", "highlight_color": "00E5FF",
  "outline_color": "000000", "outline": 6, "shadow": 3, "back_color": null,
  "position": "center", "margin_v": 0,
  "mode": "karaoke", "animation": "pop", "max_words": 3, "letter_spacing": 1
}
```

- `mode`: `karaoke` (phrase with active word highlighted) · `word_pop` (one big word) · `line` (plain).
- `animation`: `pop` · `bounce` · `fade` · `none`.

## Roadmap ideas
- True speaker diarization (pyannote) to replace the pause-based approximation.
- In-browser transcript editing to fix ASR mistakes before render.
- Split-screen layouts for two-speaker interviews.
- Package the localhost app as a Windows `.exe` with Tauri.

## License
MIT — do anything, keep it free.
