"""Animated caption generator -> ASS subtitle file (burned in by ffmpeg/libass).

Free, fast, GPU-free, and expressive enough for CapCut / Hormozi / Submagic-style
looks: word-level karaoke highlight, active-word color, pop/bounce/fade animation,
outline, shadow, box background, custom fonts, positioning.

A "style" is pure data (StylePreset / styles/catalog.json), so adding a new look
is a config edit — no code. This is what gives us 36+ styles and easy growth.
"""
from __future__ import annotations

from pathlib import Path

from ..config import settings
from ..models import StylePreset, Word


def _ass_color(rrggbb: str, alpha: str = "00") -> str:
    """RRGGBB -> ASS &HAABBGGRR (BGR order, alpha 00 = opaque)."""
    rrggbb = rrggbb.lstrip("#")
    r, g, b = rrggbb[0:2], rrggbb[2:4], rrggbb[4:6]
    return f"&H{alpha}{b}{g}{r}"


def _alignment(position: str) -> int:
    return {"top": 8, "center": 5, "bottom": 2}.get(position, 2)


def _chunk(words: list[Word], size: int) -> list[list[Word]]:
    size = max(1, size)
    return [words[i : i + size] for i in range(0, len(words), size)]


def _fmt_time(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    if cs == 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _active_prefix(style: StylePreset) -> tuple[str, str]:
    """Return (open, close) override tags applied around the active word."""
    hi = _ass_color(style.highlight_color)
    pri = _ass_color(style.primary_color)
    anim = ""
    if style.animation == "pop":
        anim = r"\fscx72\fscy72\t(0,110,\fscx100\fscy100)"
    elif style.animation == "bounce":
        anim = r"\fscx60\fscy60\t(0,90,\fscx112\fscy112)\t(90,170,\fscx100\fscy100)"
    elif style.animation == "fade":
        anim = ""  # handled at line level via \fad
    open_tag = "{\\c" + hi + anim + "}"
    close_tag = "{\\c" + pri + r"\fscx100\fscy100}"
    return open_tag, close_tag


def _line_prefix(style: StylePreset) -> str:
    if style.animation == "fade":
        return r"{\fad(90,70)}"
    if style.animation == "pop" and style.mode == "word_pop":
        return r"{\fad(40,0)}"
    return ""


def _txt(word: str, style: StylePreset) -> str:
    w = word.strip().replace("{", "(").replace("}", ")")
    return w.upper() if style.uppercase else w


def build_ass(words: list[Word], clip_start: float, clip_end: float, style: StylePreset) -> str:
    """Return an ASS document string for the clip's words zero-based to clip_start."""
    pw, ph = settings.target_width, settings.target_height
    primary = _ass_color(style.primary_color)
    outline = _ass_color(style.outline_color)
    back = _ass_color(style.back_color) if style.back_color else _ass_color("000000", "80")
    border_style = 3 if style.back_color else 1     # 3 = opaque box, 1 = outline+shadow
    bold = -1 if style.bold else 0
    align = _alignment(style.position)
    spacing = style.letter_spacing

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {pw}
PlayResY: {ph}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{style.font},{style.font_size},{primary},{primary},{outline},{back},{bold},0,0,0,100,100,{spacing},0,{border_style},{style.outline},{style.shadow},{align},60,60,{style.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: list[str] = []
    open_tag, close_tag = _active_prefix(style)
    line_prefix = _line_prefix(style)

    for group in _chunk(words, style.max_words):
        if not group:
            continue
        g_start = group[0].start
        g_end = group[-1].end
        if style.mode == "line":
            # whole group shown together, no per-word highlight
            text = line_prefix + " ".join(_txt(w.text, style) for w in group)
            events.append(_dialogue(g_start - clip_start, g_end - clip_start, text))
            continue

        # karaoke / word_pop: one event per active word, whole group visible.
        for i, w in enumerate(group):
            start = w.start
            end = group[i + 1].start if i + 1 < len(group) else g_end
            pieces = []
            for j, gw in enumerate(group):
                token = _txt(gw.text, style)
                if j == i:
                    pieces.append(open_tag + token + close_tag)
                else:
                    pieces.append(token)
            text = line_prefix + " ".join(pieces)
            events.append(_dialogue(start - clip_start, end - clip_start, text))

    return header + "\n".join(events) + "\n"


def _dialogue(start: float, end: float, text: str) -> str:
    return f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Main,,0,0,0,,{text}"


def write_ass(path: Path, words: list[Word], clip_start: float, clip_end: float, style: StylePreset) -> Path:
    path.write_text(build_ass(words, clip_start, clip_end, style), encoding="utf-8")
    return path
