"""Keyword extraction, auto-emoji mapping, and hashtag generation.

All local & free — no model needed. Used to:
  * highlight important words persistently in captions (Opus/Submagic style),
  * drop a relevant emoji next to punchy keywords (Crayo/CapCut style),
  * generate social hashtags for the post.
An optional LLM can override the hashtags/caption later; this is the floor.
"""
from __future__ import annotations

import re
from collections import Counter

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "to", "of", "in",
    "on", "for", "with", "at", "by", "from", "is", "are", "was", "were", "be",
    "been", "being", "am", "i", "you", "he", "she", "it", "we", "they", "me",
    "him", "her", "us", "them", "my", "your", "his", "its", "our", "their",
    "this", "that", "these", "those", "there", "here", "what", "who", "which",
    "when", "where", "why", "how", "not", "no", "yes", "do", "does", "did",
    "have", "has", "had", "will", "would", "can", "could", "should", "just",
    "like", "get", "got", "up", "out", "about", "into", "than", "too", "very",
    "gonna", "wanna", "really", "actually", "okay", "ok", "um", "uh", "yeah",
}

# Keyword -> emoji. Kept broad but curated so insertions feel intentional.
EMOJI_MAP: dict[str, str] = {
    "money": "💰", "cash": "💵", "dollar": "💵", "dollars": "💵", "rich": "🤑",
    "profit": "📈", "growth": "📈", "increase": "📈", "revenue": "💰",
    "business": "💼", "startup": "🚀", "success": "🏆", "win": "🏆", "winner": "🏆",
    "goal": "🎯", "goals": "🎯", "target": "🎯", "focus": "🎯",
    "time": "⏰", "fast": "⚡", "faster": "⚡", "speed": "⚡", "quick": "⚡",
    "fire": "🔥", "hot": "🔥", "viral": "🔥", "best": "🔥", "amazing": "🤩",
    "love": "❤️", "heart": "❤️", "happy": "😄", "smile": "😄",
    "sad": "😢", "cry": "😭", "angry": "😡", "mad": "😡",
    "crazy": "🤯", "insane": "🤯", "mind": "🧠", "brain": "🧠", "smart": "🧠",
    "think": "🤔", "idea": "💡", "ideas": "💡", "learn": "📚", "study": "📚",
    "book": "📖", "read": "📖", "school": "🎓", "student": "🎓",
    "work": "💪", "hard": "💪", "strong": "💪", "power": "💪", "energy": "⚡",
    "eyes": "👀", "look": "👀", "see": "👀", "watch": "👀",
    "stop": "✋", "wait": "✋", "warning": "⚠️", "danger": "⚠️", "careful": "⚠️",
    "secret": "🤫", "hidden": "🤫", "truth": "💯", "real": "💯", "facts": "💯",
    "phone": "📱", "app": "📱", "video": "🎬", "camera": "📷", "music": "🎵",
    "food": "🍔", "eat": "🍔", "coffee": "☕", "sleep": "😴", "tired": "😴",
    "world": "🌍", "earth": "🌍", "travel": "✈️", "car": "🚗", "home": "🏠",
    "gym": "🏋️", "health": "🏥", "run": "🏃", "game": "🎮", "gaming": "🎮",
    "boom": "💥", "explode": "💥", "shock": "😱", "wow": "😮", "omg": "😱",
    "clock": "⏰", "year": "📅", "day": "📅", "party": "🎉", "celebrate": "🎉",
    "check": "✅", "done": "✅", "yes": "✅", "no": "❌", "wrong": "❌",
    "gold": "🥇", "diamond": "💎", "king": "👑", "queen": "👑", "boss": "😎",
    "sun": "☀️", "star": "⭐", "night": "🌙", "rain": "🌧️", "cold": "🥶",
}

NUM_RE = re.compile(r"\b\d[\d,.]*\b")
WORD_RE = re.compile(r"[A-Za-z']+")


def _clean(word: str) -> str:
    return word.strip().strip(".,!?;:\"'()").lower()


def extract_keywords(text: str, top_n: int = 6) -> list[str]:
    """Return salient lowercase keywords (content words, weighted by frequency + emphasis)."""
    tokens = WORD_RE.findall(text.lower())
    counts = Counter()
    for tok in tokens:
        if len(tok) < 3 or tok in STOPWORDS:
            continue
        counts[tok] += 1
    # Boost words that carry an emoji mapping or appear capitalized in source.
    scored = {}
    caps = {m.group(0).lower() for m in re.finditer(r"\b[A-Z][a-z]{2,}\b", text)}
    for w, c in counts.items():
        s = c
        if w in EMOJI_MAP:
            s += 1.5
        if w in caps:
            s += 0.5
        scored[w] = s
    ranked = sorted(scored, key=lambda w: scored[w], reverse=True)
    return ranked[:top_n]


def emoji_for(word: str) -> str | None:
    return EMOJI_MAP.get(_clean(word))


def hashtags(text: str, extra: list[str] | None = None, limit: int = 6) -> list[str]:
    kws = extract_keywords(text, top_n=limit + 2)
    tags = []
    for kw in kws:
        tag = "#" + re.sub(r"[^a-z0-9]", "", kw)
        if len(tag) > 2 and tag not in tags:
            tags.append(tag)
    for e in (extra or []):
        t = "#" + re.sub(r"[^a-z0-9]", "", e.lower())
        if t not in tags:
            tags.append(t)
    generic = ["#shorts", "#viral", "#fyp"]
    for g in generic:
        if g not in tags and len(tags) < limit:
            tags.append(g)
    return tags[:limit]


def social_caption(title: str, text: str) -> str:
    """A simple, decent post caption when no LLM is used."""
    hook = title.strip() or " ".join(text.split()[:8])
    return hook.rstrip(".") + " 👇"
