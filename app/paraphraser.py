"""LLM-based paraphraser designed to bypass AI detection.

Uses Pollinations API with carefully engineered prompts that target
the specific signals detectors look for: burstiness, perplexity,
vocabulary markers, and sentence structure patterns.
"""

from app.llm import chat
from app.detector import detect, AI_MARKERS

SYSTEM_PROMPT = """You are a human academic researcher rewriting your own draft. Your goal is to make the text sound authentically human-written. Follow these rules strictly:

SENTENCE STRUCTURE:
- Vary sentence length DRAMATICALLY. Mix very short sentences (3-6 words) with long complex ones (30+ words).
- Never write more than two sentences of similar length in a row.
- Some sentences should be fragments or start with "And" or "But".

WORD CHOICE:
- Use specific, concrete words instead of vague academic filler.
- NEVER use these words: delve, crucial, notably, moreover, furthermore, comprehensive, multifaceted, utilize, leveraging, groundbreaking, paradigm, holistic, synergy, robust, seamless, cutting-edge, landscape, facilitate, endeavor, intricate, pivotal, streamline, harness, foster, bolster, underscores, underpin, overarching, tapestry, realm, embark, commendable, testament, meticulous, navigating, ever-evolving.
- NEVER use these phrases: "it is important to note", "it is worth noting", "in conclusion", "in today's world", "in the realm of", "plays a crucial role", "a myriad of", "shed light on", "a testament to", "serves as a".
- Use contractions sometimes (it's, don't, can't, we've).
- Choose slightly unexpected synonyms — not the most obvious word.

VOICE AND TONE:
- Write in first person occasionally ("I argue", "we found", "my reading of").
- Include hedging language ("probably", "it seems", "arguably", "to some extent").
- Add self-corrections or qualifications ("though this might overstate things", "admittedly").
- Transitions should feel natural, not formulaic. Sometimes just start a new thought.

STRUCTURE:
- Don't start consecutive sentences with the same word.
- Vary paragraph lengths — some short (1-2 sentences), some long.
- Occasionally use parenthetical asides (like this) or dashes — for emphasis.
- Use semicolons or colons where a comma-splice might naturally occur.

CRITICAL RULES:
- Preserve ALL factual content, data, citations, and technical terms exactly.
- Do not add information that isn't in the original.
- Do not add meta-commentary about the rewriting process.
- Output ONLY the rewritten text. No headers, labels, or explanations."""

AGGRESSIVE_ADDENDUM = """
ADDITIONAL RULES FOR AGGRESSIVE REWRITE:
- Restructure paragraphs completely — merge some, split others.
- Flip at least 30% of sentences between active and passive voice.
- Insert 2-3 rhetorical questions throughout the text.
- Add more colloquial touches ("frankly", "the thing is", "look").
- Break some academic conventions deliberately — this should read like a smart person's blog post, not a polished paper.
- Use analogies or metaphors where appropriate.
"""


def _build_messages(text: str, intensity: str = "medium") -> list[dict]:
    """Build the message list for the paraphraser."""
    system = SYSTEM_PROMPT
    if intensity == "aggressive":
        system += AGGRESSIVE_ADDENDUM

    if intensity == "light":
        user_msg = (
            "Lightly rephrase this text. Keep the structure mostly intact but "
            "vary word choices and sentence lengths to sound more natural:\n\n"
            f"{text}"
        )
    elif intensity == "aggressive":
        user_msg = (
            "Completely rewrite this text from scratch. Same facts, totally "
            "different structure, voice, and flow:\n\n"
            f"{text}"
        )
    else:
        user_msg = (
            "Rewrite this text to sound naturally human-written. Change structure, "
            "word choices, and sentence patterns while preserving all meaning:\n\n"
            f"{text}"
        )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def _post_process(text: str) -> str:
    """Quick pass to catch any remaining AI marker words."""
    result = text
    # Simple substitution for common markers that slip through
    replacements = {
        "delve": "explore",
        "crucial": "key",
        "moreover": "also",
        "furthermore": "and",
        "utilize": "use",
        "leveraging": "using",
        "comprehensive": "thorough",
        "facilitate": "help",
        "robust": "strong",
        "seamless": "smooth",
        "groundbreaking": "new",
        "paradigm": "model",
        "pivotal": "central",
        "intricate": "complex",
        "multifaceted": "varied",
        "endeavor": "effort",
        "streamline": "simplify",
        "harness": "use",
        "foster": "encourage",
        "bolster": "support",
        "meticulous": "careful",
        "commendable": "impressive",
        "tapestry": "mix",
        "realm": "area",
        "embark": "start",
        "holistic": "overall",
    }

    for old, new in replacements.items():
        # Case-insensitive replacement preserving first-letter case
        import re
        def _replace(match):
            word = match.group(0)
            if word[0].isupper():
                return new.capitalize()
            return new
        result = re.sub(rf'\b{old}\b', _replace, result, flags=re.IGNORECASE)

    return result


def paraphrase(
    text: str,
    intensity: str = "medium",
    model: str = "openai",
    max_retries: int = 2,
) -> dict:
    """Paraphrase text to bypass AI detection.

    Args:
        text: The input text to paraphrase.
        intensity: "light", "medium", or "aggressive".
        model: Pollinations model ID to use.
        max_retries: Max re-rewrite attempts if detection score stays high.

    Returns:
        dict with 'rewritten', 'original_score', 'final_score', 'attempts'.
    """
    # Score the original
    original_result = detect(text)
    original_score = original_result["score"]

    messages = _build_messages(text, intensity)

    # Temperature varies by intensity
    temp_map = {"light": 0.8, "medium": 1.0, "aggressive": 1.2}
    temperature = temp_map.get(intensity, 1.0)

    best_text = text
    best_score = original_score
    attempts = 0

    for attempt in range(1, max_retries + 1):
        attempts = attempt
        rewritten = chat(
            messages=messages,
            model=model,
            temperature=temperature,
            seed=-1,
        )

        # Post-process to catch remaining markers
        rewritten = _post_process(rewritten)

        # Score the output
        result = detect(rewritten)
        score = result["score"]

        if score < best_score:
            best_text = rewritten
            best_score = score

        # Good enough — stop
        if score < 35:
            break

        # If still high, increase temperature and retry with the output as new input
        temperature = min(1.5, temperature + 0.2)
        messages = _build_messages(rewritten, intensity)

    final_result = detect(best_text)

    return {
        "rewritten": best_text,
        "original_score": round(original_score, 1),
        "final_score": round(final_result["score"], 1),
        "final_verdict": final_result["verdict"],
        "final_features": final_result["features"],
        "attempts": attempts,
    }
