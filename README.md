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
- **Speaker-tracking auto-reframe** to 9:16 (MediaPipe / OpenCV), with graceful
  center-crop and blurred-letterbox fallbacks.
- **40+ animated caption styles** (Hormozi, CapCut, Beast, Submagic-like, Gold, Neon,
  Fire, and more) — word-by-word highlight, pop / bounce / fade, custom colors & fonts.
- **Add your own styles** by editing one JSON file — no code.
- **Optional Qwen3-VL vision re-ranking** — sends a keyframe per clip so a visual
  model can judge on-screen action, not just the transcript.

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
    llm.py                optional OpenAI-compatible re-rank   [Layer 3]
    reframe.py            face tracking → 9:16 crop path
    captions.py           style → animated ASS subtitles
    render.py             ffmpeg: cut + reframe + burn captions
    orchestrator.py       runs the whole flow, updates progress
  styles/catalog.json     40+ caption styles (edit to add more)
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
- B-roll & auto emoji insertion (Crayo-style).
- Multi-speaker color coding via diarization.
- Batch export of all clips.
- Package the localhost app as a Windows `.exe` with Tauri.

## License
MIT — do anything, keep it free.
