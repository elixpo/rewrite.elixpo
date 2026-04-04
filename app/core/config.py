"""Central configuration — loads from .env and provides defaults."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)


# --- API ---
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")
POLLINATIONS_BASE_URL = "https://gen.pollinations.ai/v1"
DEFAULT_MODEL = "kimi"

# --- LLM ---
LLM_TIMEOUT = 60
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY = 1.0  # seconds, exponential backoff

# --- Redis ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL = 3600  # 1 hour

# --- Embeddings ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
SIMILARITY_THRESHOLD = 0.85

# --- Detection thresholds ---
SCORE_GREEN = 20
SCORE_YELLOW = 60
SCORE_RED = 60  # above this = red

# --- Ensemble weights (full: LLM judge + linguistic + heuristic) ---
ENSEMBLE_WEIGHTS = {
    "llm_judge": 0.25,
    # Deep linguistic features
    "perplexity": 0.15,
    "coherence": 0.10,
    "n_gram_uniformity": 0.08,
    "readability": 0.05,
    "entropy": 0.05,
    "repetition": 0.04,
    # Classic heuristics
    "burstiness": 0.10,
    "vocabulary_markers": 0.07,
    "type_token_ratio": 0.04,
    "sentence_starters": 0.03,
    "paragraph_structure": 0.02,
    "punctuation_diversity": 0.02,
}

# --- Fallback weights (no LLM judge — linguistic + heuristic only) ---
HEURISTIC_WEIGHTS = {
    # Deep linguistic features
    "perplexity": 0.20,
    "coherence": 0.14,
    "n_gram_uniformity": 0.10,
    "readability": 0.06,
    "entropy": 0.06,
    "repetition": 0.05,
    # Classic heuristics
    "burstiness": 0.14,
    "vocabulary_markers": 0.10,
    "type_token_ratio": 0.05,
    "sentence_starters": 0.04,
    "paragraph_structure": 0.03,
    "punctuation_diversity": 0.03,
}

# --- Paraphrase ---
PARAPHRASE_TARGET_SCORE = 20  # rewrite segments above this
PARAPHRASE_MAX_RETRIES = 3
PARAPHRASE_INTENSITIES = {
    "light": 0.8,
    "medium": 1.0,
    "aggressive": 1.2,
}

# --- Segmentation ---
SEGMENT_TARGET_WORDS = 150
