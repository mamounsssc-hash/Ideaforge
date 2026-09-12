"""Optional LLM re-ranking — Layer 3.

Talks to ANY OpenAI-compatible local server: Ollama, LM Studio, or a Qwen3-VL
server (set IDEAFORGE_LLM_VISION=true to send keyframes for visual judgement).
Hermes desktop / Qwen3-VL both fit here.

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
    "You are a viral short-form video editor. You are given numbered transcript "
    "candidates from a long video. For each, judge how well it would perform as a "
    "standalone vertical short. Reply with STRICT JSON only: a list of objects "
    '{"id": <int>, "score": <0-99 int>, "title": "<hooky 3-6 word title>", '
    '"reason": "<one short sentence>", "caption": "<a social post caption with 1-2 '
    'emojis>", "hashtags": ["#tag", ...]}. Higher score = stronger hook, emotion, '
    "payoff, and completeness. Do not include any text outside the JSON."
)


def available() -> bool:
    return settings.llm_enabled and bool(settings.llm_base_url.strip())


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

        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": content},
            ],
            "temperature": 0.3,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        resp = httpx.post(url, json=payload, headers=headers, timeout=settings.llm_timeout)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        data = _extract_json(raw)

        by_id = {int(o["id"]): o for o in data if "id" in o}
        for i, c in enumerate(cands):
            o = by_id.get(i)
            if not o:
                continue
            llm_score = float(max(0, min(99, o.get("score", c.score.total))))
            # Blend: trust the model but keep heuristics as a floor/anchor (hybrid).
            c.score.total = round(0.65 * llm_score + 0.35 * c.score.total, 1)
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
    # strip code fences if present
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]
    return json.loads(raw)
