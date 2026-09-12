"""Caption style catalog loader."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..models import StylePreset

_CATALOG = Path(__file__).resolve().parent / "catalog.json"


@lru_cache(maxsize=1)
def all_styles() -> list[StylePreset]:
    data = json.loads(_CATALOG.read_text(encoding="utf-8"))
    return [StylePreset(**d) for d in data]


@lru_cache(maxsize=1)
def _by_id() -> dict[str, StylePreset]:
    return {s.id: s for s in all_styles()}


def get_style(style_id: str) -> StylePreset:
    styles = _by_id()
    if style_id in styles:
        return styles[style_id]
    # graceful fallback to a safe default so rendering never fails on a bad id
    return styles.get("hormozi_yellow") or all_styles()[0]
