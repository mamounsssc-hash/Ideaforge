"""Shared data models used across the pipeline and the API."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class Word(BaseModel):
    start: float
    end: float
    text: str
    prob: float = 1.0


class Segment(BaseModel):
    """A raw transcript segment (sentence-ish) with its words."""
    start: float
    end: float
    text: str
    words: list[Word] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    hook: float = 0.0
    emotion: float = 0.0
    info: float = 0.0
    completeness: float = 0.0
    pacing: float = 0.0
    total: float = 0.0          # 0..99 virality-style score
    source: Literal["heuristic", "llm", "hybrid"] = "heuristic"


class ClipCandidate(BaseModel):
    id: str
    start: float
    end: float
    text: str
    words: list[Word] = Field(default_factory=list)
    title: str = ""
    score: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    reason: str = ""
    keywords: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    social_caption: str = ""

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 2)


# aspect ratio -> (width, height)
ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}
AspectRatio = Literal["9:16", "4:5", "1:1", "16:9"]


def ratio_dims(ratio: str) -> tuple[int, int]:
    return ASPECT_RATIOS.get(ratio, ASPECT_RATIOS["9:16"])


class RenderOptions(BaseModel):
    style_id: str = "hormozi_yellow"
    aspect_ratio: AspectRatio = "9:16"
    reframe: bool = True
    burn_captions: bool = True
    add_emojis: bool = True
    highlight_keywords: bool = True
    hook_title: bool = True          # render the clip title as a top banner
    progress_bar: bool = True
    remove_fillers: bool = True
    remove_silence: bool = False     # drop internal dead-air, retime captions
    auto_zoom: bool = False          # subtle slow punch-in
    speaker_colors: bool = False     # color captions per (approx) speaker turn
    broll: bool = False              # optional Pexels B-roll overlay
    watermark_text: str = ""         # e.g. "@yourhandle" burned in a corner
    music_volume: float = 0.0        # 0 = off; else mix job's music at this gain
    # caption placement overrides (do not require editing the style)
    caption_position: Literal["auto", "top", "center", "bottom"] = "auto"
    caption_scale: float = 1.0       # multiply the style font size (0.6–1.6)
    caption_offset: int = 0          # extra vertical margin in pixels


class RenderRequest(RenderOptions):
    job_id: str
    clip_id: str
    # per-clip edits made in the UI before rendering
    start_override: float | None = None
    end_override: float | None = None
    title_override: str | None = None


class BatchRenderRequest(RenderOptions):
    job_id: str
    clip_ids: list[str] = Field(default_factory=list)   # empty => all clips


class StylePreset(BaseModel):
    id: str
    name: str
    group: str = "General"
    # rendering knobs consumed by captions.py
    font: str = "Arial"
    font_size: int = 84
    bold: bool = True
    uppercase: bool = False
    primary_color: str = "FFFFFF"       # RRGGBB
    highlight_color: str = "F5D40A"     # active word color
    outline_color: str = "000000"
    outline: int = 4
    shadow: int = 2
    back_color: str | None = None       # box background, RRGGBB or None
    position: Literal["top", "center", "bottom"] = "center"
    margin_v: int = 260
    mode: Literal["karaoke", "word_pop", "line"] = "karaoke"
    animation: Literal["none", "pop", "fade", "bounce"] = "pop"
    max_words: int = 4                  # words visible per caption event
    letter_spacing: int = 0
