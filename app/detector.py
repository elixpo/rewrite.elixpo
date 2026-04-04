"""Heuristic AI text detector.

Scores text on multiple signals that distinguish AI-generated from human writing.
Returns a 0-100 score where higher = more likely AI.
"""

import math
import re
from collections import Counter

import nltk

try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    nltk.download("punkt_tab", quiet=True)

from nltk.tokenize import sent_tokenize, word_tokenize

# --- AI vocabulary markers ---
# Words/phrases disproportionately used by LLMs
AI_MARKERS = [
    "delve", "crucial", "notably", "moreover", "furthermore",
    "it is important to note", "it is worth noting", "in conclusion",
    "comprehensive", "multifaceted", "utilize", "leveraging",
    "groundbreaking", "paradigm", "holistic", "synergy",
    "robust", "seamless", "cutting-edge", "landscape",
    "facilitate", "endeavor", "intricate", "pivotal",
    "streamline", "harness", "foster", "bolster",
    "underscores", "underpin", "overarching", "tapestry",
    "realm", "embark", "commendable", "testament",
    "meticulous", "navigating", "ever-evolving",
    "in today's world", "in the realm of", "it's important to",
    "plays a crucial role", "a myriad of", "shed light on",
    "in light of", "a testament to", "serves as a",
    "it should be noted", "this is particularly",
]

# Phrases that are strong AI signals (weighted higher)
AI_STRONG_MARKERS = [
    "as an ai", "as a language model", "i don't have personal",
    "it's worth mentioning", "in summary,", "to summarize,",
    "let me explain", "here's the thing",
]

# --- Sentence starters AI overuses ---
AI_STARTERS = [
    "additionally", "furthermore", "moreover", "however",
    "consequently", "nevertheless", "in addition",
    "it is", "this is", "there are", "there is",
    "one of the", "when it comes to",
]


def _sentence_lengths(sentences: list[str]) -> list[int]:
    """Get word count per sentence."""
    return [len(word_tokenize(s)) for s in sentences if s.strip()]


def score_burstiness(sentences: list[str]) -> float:
    """Score burstiness (sentence length variance). 0-100 where low = AI-like.

    AI text has uniform sentence lengths. Human text varies wildly.
    """
    lengths = _sentence_lengths(sentences)
    if len(lengths) < 3:
        return 50.0  # not enough data

    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 50.0

    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    cv = math.sqrt(variance) / mean  # coefficient of variation

    # Human text typically has CV > 0.5, AI text < 0.3
    # Map: CV 0.0 -> 100 (very AI), CV 0.6+ -> 0 (very human)
    ai_score = max(0, min(100, (1 - cv / 0.6) * 100))
    return ai_score


def score_vocabulary_markers(text: str) -> float:
    """Score based on AI vocabulary marker frequency. 0-100."""
    text_lower = text.lower()
    word_count = len(text_lower.split())
    if word_count == 0:
        return 0.0

    marker_hits = 0
    for marker in AI_MARKERS:
        count = text_lower.count(marker)
        marker_hits += count

    strong_hits = 0
    for marker in AI_STRONG_MARKERS:
        count = text_lower.count(marker)
        strong_hits += count

    if strong_hits > 0:
        return min(100, 70 + strong_hits * 15)

    # Normalize by text length (per 100 words)
    density = (marker_hits / word_count) * 100

    # 0 markers -> 0, 3+ per 100 words -> 100
    ai_score = max(0, min(100, density * 33))
    return ai_score


def score_type_token_ratio(words: list[str]) -> float:
    """Score based on lexical diversity. 0-100 where low diversity = AI-like.

    AI tends to reuse the same vocabulary more than humans.
    """
    if len(words) < 20:
        return 50.0

    # Use a sliding window TTR for longer texts (more stable)
    window = min(100, len(words))
    ttrs = []
    for i in range(0, len(words) - window + 1, window // 2):
        chunk = words[i : i + window]
        unique = len(set(w.lower() for w in chunk))
        ttrs.append(unique / len(chunk))

    avg_ttr = sum(ttrs) / len(ttrs)

    # Human text: TTR ~0.65-0.80, AI text: ~0.50-0.65
    # Map: TTR 0.50 -> 100 (AI), TTR 0.75+ -> 0 (human)
    ai_score = max(0, min(100, (0.75 - avg_ttr) / 0.25 * 100))
    return ai_score


def score_sentence_starter_variety(sentences: list[str]) -> float:
    """Score based on how varied sentence openings are. 0-100."""
    if len(sentences) < 5:
        return 50.0

    starters = []
    for s in sentences:
        words = s.strip().split()
        if words:
            starters.append(words[0].lower())

    # Check repetition of starters
    counter = Counter(starters)
    total = len(starters)
    unique_ratio = len(counter) / total

    # Check for AI-typical starters
    ai_starter_count = sum(
        1 for s in starters if any(s.startswith(a.split()[0]) for a in AI_STARTERS)
    )
    ai_starter_ratio = ai_starter_count / total

    # Combine: low variety + high AI starters = more AI-like
    variety_score = max(0, min(100, (1 - unique_ratio) * 150))
    starter_score = max(0, min(100, ai_starter_ratio * 200))

    return min(100, variety_score * 0.5 + starter_score * 0.5)


def score_paragraph_structure(text: str) -> float:
    """Score based on paragraph uniformity. AI tends to write even paragraphs."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) < 3:
        return 50.0

    lengths = [len(p.split()) for p in paragraphs]
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 50.0

    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    cv = math.sqrt(variance) / mean

    # Low CV (uniform paragraphs) = AI-like
    ai_score = max(0, min(100, (1 - cv / 0.5) * 100))
    return ai_score


def score_punctuation_diversity(text: str) -> float:
    """Score based on punctuation patterns. AI underuses dashes, semicolons, parentheses."""
    if len(text) < 100:
        return 50.0

    chars = len(text)
    # Count human-typical punctuation
    human_punct = sum(text.count(c) for c in [";", "—", "–", "-", "(", ")", ":", "!"])
    density = human_punct / chars * 100

    # Higher density = more human-like
    # AI text: ~0.5%, Human: ~1.5%+
    ai_score = max(0, min(100, (1.5 - density) / 1.5 * 100))
    return ai_score


def detect(text: str) -> dict:
    """Run all heuristic detectors and return a combined score.

    Returns:
        dict with 'score' (0-100), 'verdict', and per-feature breakdown.
    """
    sentences = sent_tokenize(text)
    words = word_tokenize(text)

    features = {
        "burstiness": score_burstiness(sentences),
        "vocabulary_markers": score_vocabulary_markers(text),
        "type_token_ratio": score_type_token_ratio(words),
        "sentence_starters": score_sentence_starter_variety(sentences),
        "paragraph_structure": score_paragraph_structure(text),
        "punctuation_diversity": score_punctuation_diversity(text),
    }

    # Weighted combination
    weights = {
        "burstiness": 0.22,
        "vocabulary_markers": 0.25,
        "type_token_ratio": 0.15,
        "sentence_starters": 0.15,
        "paragraph_structure": 0.10,
        "punctuation_diversity": 0.13,
    }

    total = sum(features[k] * weights[k] for k in features)

    if total >= 75:
        verdict = "Very likely AI-generated"
    elif total >= 55:
        verdict = "Likely AI-generated"
    elif total >= 40:
        verdict = "Mixed / Uncertain"
    elif total >= 25:
        verdict = "Likely human-written"
    else:
        verdict = "Very likely human-written"

    return {
        "score": round(total, 1),
        "verdict": verdict,
        "features": {k: round(v, 1) for k, v in features.items()},
    }
