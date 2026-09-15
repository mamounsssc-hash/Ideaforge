"""Animated caption generator -> ASS subtitle file (burned in by ffmpeg/libass).

Free, fast, GPU-free, and expressive enough for CapCut / Hormozi / Submagic-style
looks: word-level karaoke highlight, persistent keyword highlight, auto-emoji,
filler removal, a top hook banner, pop/bounce/fade animation, outline, shadow,
box background, custom fonts, positioning, and any aspect ratio.

A "style" is pure data (StylePreset / styles/catalog.json), so adding a new look
is a config edit — no code.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..config import settings
from ..models import StylePreset, Word
from . import keywords as kw
from . import speakers as spk

FILLERS = {"um", "uh", "erm", "mm", "hmm", "uhh", "umm", "ah", "eh"}


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


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", word.lower())


def _active_anim(style: StylePreset) -> str:
    # Smooth, premium word emphasis. The scale eases UP to 100% (never a hard jump)
    # so the currently-spoken word grows in gently instead of snapping/jittering.
    if style.animation == "pop":
        return r"\fscx86\fscy86\t(0,140,\fscx100\fscy100)"
    if style.animation == "bounce":
        # a soft settle (small overshoot, then ease back) — no violent 112% snap.
        return r"\fscx82\fscy82\t(0,120,\fscx106\fscy106)\t(120,220,\fscx100\fscy100)"
    return ""


def _line_prefix(style: StylePreset) -> str:
    if style.animation == "fade":
        return r"{\fad(90,70)}"
    if style.animation == "pop" and style.mode == "word_pop":
        return r"{\fad(40,0)}"
    return ""


def _display(word: str, style: StylePreset) -> str:
    w = word.strip().replace("{", "(").replace("}", ")")
    return w.upper() if style.uppercase else w


def build_ass(
    words: list[Word],
    clip_start: float,
    clip_end: float,
    style: StylePreset,
    play_w: int | None = None,
    play_h: int | None = None,
    keyword_set: set[str] | None = None,
    add_emojis: bool = False,
    remove_fillers: bool = True,
    hook_text: str | None = None,
    max_emojis: int = 4,
    position_override: str = "auto",
    scale: float = 1.0,
    offset: int = 0,
    speaker_colors: bool = False,
    cta_text: str | None = None,
    progressive: bool = True,
    emoji_font: str = "",
    keyword_color: str = "",
) -> str:
    pw = play_w or settings.target_width
    ph = play_h or settings.target_height
    primary = _ass_color(style.primary_color)
    highlight = _ass_color(style.highlight_color)
    # A distinct, fixed colour for "important" (keyword) words, separate from the
    # active (currently-spoken) word colour. Defaults to the style highlight.
    kwcol = _ass_color(keyword_color) if keyword_color else highlight
    outline = _ass_color(style.outline_color)
    back = _ass_color(style.back_color) if style.back_color else _ass_color("000000", "80")
    border_style = 3 if style.back_color else 1
    bold = -1 if style.bold else 0
    position = style.position if position_override in ("auto", "") else position_override
    align = _alignment(position)
    font_size = max(20, int(round(style.font_size * max(0.4, scale))))
    margin_v = max(0, style.margin_v + int(offset))
    kwset = keyword_set or set()

    # Filter filler words up-front so they never appear.
    if remove_fillers:
        words = [w for w in words if _norm(w.text) not in FILLERS]

    # Per-word highlight colors (speaker coloring) if requested.
    hi_colors: list[str] | None = None
    if speaker_colors and words:
        # prefer real diarization labels when present, else the pause heuristic
        if any(getattr(w, "speaker", -1) >= 0 for w in words):
            sp = [max(0, getattr(w, "speaker", 0)) for w in words]
        else:
            sp = spk.assign(words)
        hi_colors = [_ass_color(spk.color_for(s)) for s in sp]

    # Pre-compute emoji insertions (cap + no repeats) mapped by word identity index.
    emoji_at: dict[int, str] = {}
    if add_emojis:
        used: set[str] = set()
        for i, w in enumerate(words):
            if len(emoji_at) >= max_emojis:
                break
            e = kw.emoji_for(w.text)
            if e and e not in used:
                emoji_at[i] = e
                used.add(e)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {pw}
PlayResY: {ph}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{style.font},{font_size},{primary},{primary},{outline},{back},{bold},0,0,0,100,100,{style.letter_spacing},0,{border_style},{style.outline},{style.shadow},{align},90,90,{margin_v},1
Style: Hook,{style.font},{int(font_size * 0.72)},{_ass_color('FFFFFF')},{_ass_color('FFFFFF')},{_ass_color('000000')},{_ass_color('000000','60')},-1,0,0,0,100,100,1,0,3,4,2,8,80,80,140,1
Style: CTA,{style.font},{int(font_size * 0.8)},{highlight},{highlight},{_ass_color('000000')},{_ass_color('000000','40')},-1,0,0,0,100,100,1,0,1,5,2,2,80,80,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: list[str] = []
    anim = _active_anim(style)
    line_prefix = _line_prefix(style)

    clip_dur = clip_end - clip_start

    # optional top hook banner spanning the whole clip
    if hook_text:
        htxt = hook_text.strip().replace("{", "(").replace("}", ")").upper()
        events.append(
            f"Dialogue: 1,{_fmt_time(0)},{_fmt_time(clip_dur)},Hook,,0,0,0,,"
            + "{\\fad(120,80)}" + htxt
        )

    # optional end CTA card (retention loop-back)
    if cta_text and cta_text.strip():
        ctxt = cta_text.strip().replace("{", "(").replace("}", ")").upper()
        cta_start = max(0.0, clip_dur - 1.8)
        events.append(
            f"Dialogue: 2,{_fmt_time(cta_start)},{_fmt_time(clip_dur)},CTA,,0,0,0,,"
            + r"{\fad(150,0)\fscx60\fscy60\t(0,140,\fscx100\fscy100)}" + ctxt
        )

    # Wrap emoji in a colour-emoji font (e.g. Segoe UI Emoji on Windows) so libass
    # renders them in colour instead of monochrome, then switch back to the caption
    # font. Colour output still depends on the ffmpeg/libass build supporting it.
    ef = emoji_font.strip()

    def _emoji_str(e: str) -> str:
        if ef:
            return " {\\fn" + ef + "}" + e + "{\\fn" + style.font + "}"
        return " " + e

    def token_for(idx: int, w: Word, active: bool) -> str:
        base = _display(w.text, style)
        emoji = _emoji_str(emoji_at[idx]) if idx in emoji_at else ""
        is_kw = _norm(w.text) in kwset
        hi = hi_colors[idx] if (hi_colors and idx < len(hi_colors)) else highlight
        if active:
            # the word being spoken RIGHT NOW: highlight colour + pop animation.
            return "{\\c" + hi + anim + "}" + base + "{\\c" + primary + r"\fscx100\fscy100}" + emoji
        if is_kw:
            # an "important" word: its own FIXED colour, always on. We colour it
            # only (no resize) — statically blowing up a single word inside a line
            # reflows the other words and jumps off the baseline, which looks bad.
            # Colour alone makes key words pop the way Submagic / Opus captions do.
            return "{\\c" + kwcol + "}" + base + "{\\c" + primary + "}" + emoji
        return base + emoji

    for group_idx, group in enumerate(_chunk(words, style.max_words)):
        if not group:
            continue
        g_start = group[0].start
        g_end = group[-1].end
        # indices of these words within the full list (for emoji lookup)
        base_i = group_idx * style.max_words

        if style.mode == "line":
            parts = [token_for(base_i + j, w, active=False) for j, w in enumerate(group)]
            text = line_prefix + " ".join(parts)
            events.append(_dialogue(g_start - clip_start, g_end - clip_start, text))
            continue

        for i, w in enumerate(group):
            start = w.start
            end = group[i + 1].start if i + 1 < len(group) else g_end
            # progressive: reveal words as they are spoken (never show unsaid words);
            # otherwise show the whole phrase and just recolor the active word.
            visible = group[: i + 1] if progressive else group
            parts = [token_for(base_i + j, gw, active=(j == i)) for j, gw in enumerate(visible)]
            text = line_prefix + " ".join(parts)
            events.append(_dialogue(start - clip_start, end - clip_start, text))

    return header + "\n".join(events) + "\n"


def _dialogue(start: float, end: float, text: str) -> str:
    return f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Main,,0,0,0,,{text}"


def write_ass(path: Path, words: list[Word], clip_start: float, clip_end: float,
              style: StylePreset, **kw) -> Path:
    path.write_text(build_ass(words, clip_start, clip_end, style, **kw), encoding="utf-8")
    return path
