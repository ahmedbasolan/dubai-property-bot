"""Shared configuration for Dubai Property Bot."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"
DB_PATH = PROJECT_ROOT / "data" / "dubai_properties.duckdb"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Financial constants (Dubai market standard)
MANAGEMENT_FEE_RATE = 0.08  # 8% of annual rent
VACANCY_RATE = 0.05  # ~2-3 weeks/year

# LLM defaults
LLM_TEMPERATURE = 0.3
# Groq's free tier counts the prompt *and* max_tokens against its 8k tokens per
# minute limit, so a 4k ceiling turned a 6k-token context into a 413. Answers
# here run a few hundred tokens; 1,500 leaves room for the context and the
# request-budget guard in rag.generate_answer trims this further if needed.
LLM_MAX_TOKENS = 1500

# UI
MIN_BUDGET = 300_000
MAX_BUDGET = 15_000_000

# Recommendation icons
REC_ICONS = {"INVEST": "🟢", "HOLD": "🟡", "AVOID": "🔴"}
