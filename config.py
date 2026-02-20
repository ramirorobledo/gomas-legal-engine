"""
Centralized configuration for Gomas Legal Engine.
All settings are read from environment variables with sensible defaults.
"""
import os
from dotenv import load_dotenv

# Load .env from repo root
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_env_path)

def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)

# ─── Directories ─────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR     = _env("INPUT_DIR",     os.path.join(BASE_DIR, "input"))
PROCESSING_DIR = _env("PROCESSING_DIR", os.path.join(BASE_DIR, "processing"))
OCR_OUTPUT_DIR = _env("OCR_OUTPUT_DIR", os.path.join(BASE_DIR, "ocr_output"))
NORMALIZED_DIR = _env("NORMALIZED_DIR", os.path.join(BASE_DIR, "normalized"))
REVIEW_QUEUE_DIR = _env("REVIEW_QUEUE_DIR", os.path.join(BASE_DIR, "review_queue"))
DEAD_LETTER_DIR  = _env("DEAD_LETTER_DIR",  os.path.join(BASE_DIR, "review_queue", "dead_letter"))
INDICES_DIR   = _env("INDICES_DIR",   os.path.join(BASE_DIR, "indices"))
DB_DIR        = _env("DB_DIR",        os.path.join(BASE_DIR, "db"))
LOG_DIR       = _env("LOG_DIR",       os.path.join(BASE_DIR, "logs"))

# Ensure all critical dirs exist at import time
for _d in [INPUT_DIR, PROCESSING_DIR, OCR_OUTPUT_DIR, NORMALIZED_DIR,
           REVIEW_QUEUE_DIR, DEAD_LETTER_DIR, INDICES_DIR, DB_DIR, LOG_DIR]:
    os.makedirs(_d, exist_ok=True)

# ─── Database ─────────────────────────────────────────────────────────────────────────
DB_PATH = _env("DB_PATH", os.path.join(DB_DIR, "gomas_legal.db"))

# ─── API Server ───────────────────────────────────────────────────────────────────
API_HOST     = _env("API_HOST", "0.0.0.0")
API_PORT     = int(_env("API_PORT", "8000"))
MCP_HTTP_PORT = int(_env("MCP_HTTP_PORT", "8765"))

# Comma-separated list of allowed CORS origins
CORS_ORIGINS = [o.strip() for o in _env("CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]

# Optional: if set, all API requests must carry Authorization: Bearer <API_KEY>
API_KEY = _env("API_KEY", "")

# ─── LLM ──────────────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY", "")
# Strip inline comments  (e.g.  sk-ant-xxx  # my key)
if "#" in ANTHROPIC_API_KEY:
    ANTHROPIC_API_KEY = ANTHROPIC_API_KEY.split("#")[0].strip()

LLM_MODEL       = _env("LLM_MODEL", "claude-3-5-haiku-20241022")
LLM_MAX_TOKENS  = int(_env("LLM_MAX_TOKENS", "2048"))

# ─── OCR ──────────────────────────────────────────────────────────────────────────────
MISTRAL_API_KEY  = _env("MISTRAL_API_KEY", "")
OCR_MODEL        = _env("OCR_MODEL", "mistral-ocr-2512")
OCR_ENDPOINT     = _env("OCR_ENDPOINT", "https://api.mistral.ai/v1/ocr")

# Set to "true" to skip Mistral and use local PyMuPDF extraction
MOCK_OCR = _env("MOCK_OCR", "false").lower() == "true"

# ─── Pipeline ────────────────────────────────────────────────────────────────────
MAX_RETRIES      = int(_env("MAX_RETRIES", "3"))
# If "true", always index even when doc requires_revision (useful in dev)
FORCE_INDEXING   = _env("FORCE_INDEXING", "true").lower() == "true"

# ─── Rules ──────────────────────────────────────────────────────────────────────────
RULES_PATH = _env("RULES_PATH", os.path.join(BASE_DIR, "rules.yaml"))
