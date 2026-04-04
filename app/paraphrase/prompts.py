"""Prompt templates for paraphrasing — detection-aware, strict academic register."""

SYSTEM_PROMPT = """You are rewriting academic text so that it reads as authentically human-written. You must understand HOW AI-generated text is detected in order to avoid those patterns.

AI TEXT IS DETECTED BY THESE STATISTICAL PROPERTIES:

1. UNIFORM SENTENCE LENGTH — AI writes sentences of roughly equal length (15-22 words each). Humans do not. A human paragraph might contain: a 4-word sentence, then a 38-word sentence with two clauses, then a 9-word one, then a 27-word one. You MUST produce this kind of variance. Count your words. If two consecutive sentences are within 5 words of each other in length, rewrite one of them.

2. PREDICTABLE WORD SEQUENCES — AI text flows too smoothly. Each word follows logically and predictably from the last. Human text has more surprising word choices, unusual collocations, and occasional awkwardness. Do not always pick the most natural next word. Sometimes use a less common synonym, an unexpected sentence construction, or an interrupting clause.

3. REPETITIVE STRUCTURE — AI reuses the same sentence templates. "The X of Y has Z" appears multiple times. "This approach enables..." appears twice. Humans vary their syntactic structures much more. Every sentence in your output must have a DIFFERENT grammatical structure from the one before it.

4. FORMULAIC TRANSITIONS — AI connects every idea with explicit transition words. Humans often just start a new thought. Not every paragraph needs "However" or "Additionally". Sometimes a period is enough. A new idea can begin without announcement.

5. UNIFORM PARAGRAPH SIZE — AI writes paragraphs of similar length. Humans write some 2-sentence paragraphs and some 7-sentence paragraphs. Vary your paragraph lengths.

6. LACK OF VOICE — AI writes in an impersonal, generalized way. Human researchers have opinions, hedges, qualifications, and personality. Use first person ("we observe", "our findings"). Add genuine qualifications ("this may not hold for", "one caveat is"). Show intellectual honesty.

RULES:
- Maintain strict academic register. This is a research paper, not a blog.
- Preserve ALL factual content, data, numbers, citations, and technical terms exactly.
- Do not add information not in the original. Do not remove information from the original.
- Keep output within 20% of the input word count.
- Do not add commentary about the rewriting. Output ONLY the rewritten text."""

INTENSITY_ADDENDA = {
    "light": """
Rephrase sentences and vary word choices. Keep the same paragraph structure and idea ordering. This is a light edit, not a rewrite.""",

    "medium": """
Restructure sentences substantially. Change the order of clauses within sentences. Vary the grammatical patterns. Combine some sentences, split others. Change active to passive and vice versa in places. This should read like a different author wrote it about the same findings.""",

    "aggressive": """
Rebuild every sentence from the ground up. Same facts, completely different expression. Reorder how ideas are presented within each paragraph. Use the full range of punctuation — semicolons, em-dashes, colons, parenthetical asides. Mix very short declarative sentences with long multi-clause constructions. Vary paragraph lengths dramatically. This must be undetectable as AI-written while maintaining full academic rigor.""",
}

DOMAIN_ADDENDA = {
    "cs": """
DOMAIN: Computer Science — Preserve all code, algorithms, complexity notations, and system names exactly. Technical precision is paramount.""",

    "medicine": """
DOMAIN: Medicine — Preserve ALL drug names, dosages, p-values, confidence intervals, and clinical terminology exactly.""",

    "law": """
DOMAIN: Law — Preserve ALL case citations, statute references, and legal terminology exactly.""",

    "humanities": """
DOMAIN: Humanities — Preserve ALL direct quotes, author names, and page references exactly.""",

    "general": "",
}


def build_messages(
    text: str,
    intensity: str = "medium",
    domain: str = "general",
    context: str = "",
    feedback: str = "",
) -> list[dict]:
    """Build the message list for the paraphraser.

    Args:
        text: Text to paraphrase.
        intensity: "light", "medium", or "aggressive".
        domain: Domain for prompt specialization.
        context: Optional surrounding context for coherence.
        feedback: Optional detection feedback from previous attempt.
    """
    system = SYSTEM_PROMPT

    addendum = INTENSITY_ADDENDA.get(intensity, INTENSITY_ADDENDA["medium"])
    system += "\n" + addendum

    domain_addendum = DOMAIN_ADDENDA.get(domain, "")
    if domain_addendum:
        system += "\n" + domain_addendum

    if intensity == "light":
        user_msg = "Rephrase this text while keeping the structure mostly intact:\n\n"
    elif intensity == "aggressive":
        user_msg = "Rewrite this text completely — same facts, different expression throughout:\n\n"
    else:
        user_msg = "Rewrite this text to sound naturally written by a human researcher:\n\n"

    if context:
        user_msg += f"[SURROUNDING CONTEXT — do NOT rewrite this, use for coherence only]\n{context}\n\n[TEXT TO REWRITE]\n"

    user_msg += text

    if feedback:
        user_msg += f"\n\n[DETECTION FEEDBACK — your previous rewrite was still detected. Fix these specific issues]\n{feedback}"

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def build_detection_feedback(text: str, features: dict) -> str:
    """Build specific, actionable feedback from detection results.

    Tells the LLM exactly what the detector caught and how to fix it.
    """
    from nltk.tokenize import sent_tokenize, word_tokenize
    lines = []

    # Sentence length analysis
    sentences = sent_tokenize(text)
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) >= 3:
        avg_len = sum(lengths) / len(lengths)
        import math
        variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
        cv = math.sqrt(variance) / avg_len if avg_len > 0 else 0

        lines.append(f"SENTENCE LENGTHS: Your sentences are {', '.join(str(l) for l in lengths[:10])} words long.")
        if cv < 0.4:
            lines.append(f"  Problem: Too uniform (CV={cv:.2f}). Humans have CV>0.5. Mix in 3-6 word sentences and 30+ word sentences.")

    # Burstiness
    if features.get("burstiness", 0) > 30:
        lines.append(f"BURSTINESS: {features['burstiness']:.0f}% (too uniform). Your sentence lengths are too similar. Add very short and very long sentences.")

    # Vocabulary
    if features.get("vocabulary_markers", 0) > 20:
        lines.append(f"AI VOCABULARY: {features['vocabulary_markers']:.0f}%. You are using words that AI text detectors flag. Replace formal filler words with specific, concrete alternatives.")

    # N-gram uniformity
    if features.get("n_gram_uniformity", 0) > 50:
        lines.append(f"N-GRAM UNIFORMITY: {features['n_gram_uniformity']:.0f}%. Your word sequences are too predictable. Use more unexpected word pairings and less common phrasings.")

    # Repetition
    if features.get("repetition", 0) > 25:
        # Find repeated starters
        starters = [s.split()[0].lower() for s in sentences if s.split()]
        from collections import Counter
        starter_counts = Counter(starters).most_common(3)
        repeated = [f'"{w}" ({c}x)' for w, c in starter_counts if c > 1]
        if repeated:
            lines.append(f"REPEATED STARTERS: {', '.join(repeated)}. Each sentence must start differently.")

    # Paragraph structure
    if features.get("paragraph_structure", 0) > 30:
        lines.append(f"PARAGRAPH STRUCTURE: {features['paragraph_structure']:.0f}%. Your paragraphs are too uniform in length. Vary them.")

    # Punctuation
    if features.get("punctuation_diversity", 0) > 40:
        lines.append(f"PUNCTUATION: {features['punctuation_diversity']:.0f}%. Use more varied punctuation — semicolons, dashes, parentheses, colons.")

    if not lines:
        lines.append("The text still reads as AI-generated. Restructure sentences more dramatically. Vary lengths. Use unexpected phrasing.")

    return "\n".join(lines)
