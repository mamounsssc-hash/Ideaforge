"""Optional LLM re-ranking — Layer 3.

Talks to ANY OpenAI-compatible server via a single base URL (OpenRouter,
Gemini, Groq, Ollama, LM Studio, …). Supports automatic model fallback:
if the primary model fails, the engine tries each fallback model in order.

CRITICAL DESIGN RULE: this layer is best-effort. Any failure — server down,
timeout, bad JSON, disabled — is swallowed and the caller keeps the heuristic
ranking. The pipeline never stops because the model stopped.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import httpx

from ..config import settings
from ..models import ClipCandidate

log = logging.getLogger("ideaforge.llm")


SYSTEM = (
    "You are an elite short-form editor who has made thousands of viral clips. "
    "You receive numbered transcript candidates cut from ONE long video. Judge each "
    "as a STANDALONE vertical short for TikTok / Reels / Shorts.\n\n"
    "A STRONG clip: (1) opens with a HOOK in its first sentence — a bold claim, a "
    "question, a number, or a curiosity gap; (2) is fully understandable on its own "
    "without the rest of the video; (3) delivers ONE clear idea with a real payoff or "
    "conclusion; (4) carries emotion, a story, a surprising insight, or a strong "
    "opinion; (5) does NOT start or end mid-thought.\n"
    "A WEAK clip: rambling, no hook, needs outside context, cut off, full of filler, "
    "or a slow setup with no payoff.\n\n"
    "Be HARSH and DECISIVE. Most candidates are NOT strong — score those below 40. "
    "Only genuinely scroll-stopping clips deserve 80+. Spread scores widely; do not "
    "cluster everything around 60-75.\n\n"
    "Reply with STRICT JSON only: a list of "
    '{"id": <int>, "score": <0-99 int>, "title": "<3-6 word hooky title>", '
    '"reason": "<one sentence: why it hooks or why it is weak>", '
    '"caption": "<social caption with 1-2 emojis>", "hashtags": ["#tag", ...]}. '
    "No text outside the JSON."
)


def available() -> bool:
    return settings.llm_enabled and bool(settings.llm_base_url.strip())


def _get_models() -> list[str]:
    """Return [primary, fallback1, fallback2, ...] model list."""
    models = [settings.llm_model]
    if settings.llm_fallback_models.strip():
        for m in settings.llm_fallback_models.split(","):
            m = m.strip()
            if m and m not in models:
                models.append(m)
    return models


def _build_prompt(cands: list[ClipCandidate]) -> str:
    lines = []
    for i, c in enumerate(cands):
        snippet = c.text[:600].replace("\n", " ")
        lines.append(f"[{i}] ({c.duration:.0f}s) {snippet}")
    return "Candidates:\n" + "\n".join(lines)


def _keyframe_data_url(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    b = path.read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(b).decode()


def _call_model(model: str, content, headers: dict, proxy: str | None) -> list:
    """Send one request to a specific model. Raises on any failure."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": content},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    resp = httpx.post(url, json=payload, headers=headers,
                      timeout=settings.llm_timeout, proxy=proxy)
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    return _extract_json(raw)


def rerank(
    cands: list[ClipCandidate],
    keyframes: dict[int, Path] | None = None,
    topic: str = "",
) -> list[ClipCandidate]:
    """Return candidates with LLM scores/titles merged in. On any error, return input unchanged."""
    if not available() or not cands:
        return cands

    try:
        content: list | str
        prompt = _build_prompt(cands)
        if topic.strip():
            prompt = (
                f"The user wants clips specifically about: \"{topic.strip()}\". "
                "Score clips that match this topic much higher.\n\n" + prompt
            )
        if settings.llm_vision and keyframes:
            parts: list[dict] = [{"type": "text", "text": prompt}]
            for i, _c in enumerate(cands):
                url = _keyframe_data_url(keyframes.get(i))
                if url:
                    parts.append({"type": "text", "text": f"Frame for [{i}]:"})
                    parts.append({"type": "image_url", "image_url": {"url": url}})
            content = parts
        else:
            content = prompt

        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        proxy = settings.llm_proxy.strip() or None

        # Try primary model, then each fallback in order
        models = _get_models()
        data = None
        for model in models:
            try:
                data = _call_model(model, content, headers, proxy)
                log.info("LLM model '%s' responded successfully.", model)
                break
            except Exception as e:
                log.warning("Model '%s' failed (%s: %s). Trying next...",
                            model, type(e).__name__, e)
                continue

        if data is None:
            log.warning("All %d models failed. Falling back to heuristics.", len(models))
            return cands

        by_id = {int(o["id"]): o for o in data if "id" in o}
        for i, c in enumerate(cands):
            o = by_id.get(i)
            if not o:
                continue
            llm_score = float(max(0, min(99, o.get("score", c.score.total))))
            c.score.total = round(0.8 * llm_score + 0.2 * c.score.total, 1)
            c.score.source = "hybrid"
            if o.get("title"):
                c.title = str(o["title"])[:80]
            if o.get("reason"):
                c.reason = str(o["reason"])[:200]
            if o.get("caption"):
                c.social_caption = str(o["caption"])[:280]
            if isinstance(o.get("hashtags"), list) and o["hashtags"]:
                c.hashtags = [str(h)[:40] for h in o["hashtags"][:8]]
        log.info("LLM rerank applied to %d candidates", len(by_id))
        return cands
    except Exception as e:  # noqa: BLE001 — deliberate: never let the model break the run
        log.warning("LLM rerank skipped (%s: %s). Falling back to heuristics.", type(e).__name__, e)
        return cands


def _extract_json(raw: str) -> list:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]
    return json.loads(raw)
