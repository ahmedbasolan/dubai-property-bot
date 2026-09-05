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

# LLM defaults (Groq — free tier, fast inference)
DEFAULT_MODEL = "openai/gpt-oss-120b"
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 4000

# UI
MIN_BUDGET = 300_000
MAX_BUDGET = 15_000_000

# Recommendation icons
REC_ICONS = {"INVEST": "🟢", "HOLD": "🟡", "AVOID": "🔴"}
