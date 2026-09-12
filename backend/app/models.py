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

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 2)


class RenderRequest(BaseModel):
    job_id: str
    clip_id: str
    style_id: str = "hormozi_yellow"
    reframe: bool = True
    burn_captions: bool = True


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
