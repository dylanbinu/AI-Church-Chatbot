"""
Central configuration for the multi-tenant church chatbot.

Data lives under RUNTIME_DIR (local: .runtime/, Lambda: /tmp).
Per-church bundles are loaded from S3 as {church_id}.zip.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Writable cache for tiktoken before any langchain/openai imports
os.environ.setdefault("TIKTOKEN_CACHE_DIR", "/tmp" if os.environ.get("AWS_LAMBDA_FUNCTION_NAME") else str(Path.home() / ".cache" / "tiktoken"))

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

RUNTIME_DIR = Path("/tmp") if IS_LAMBDA else (PROJECT_ROOT / ".runtime")
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

CHURCHES_FILE = BASE_DIR / "churches.json"

# Models
EMBEDDING_MODEL_NAME = "text-embedding-3-small"
LLM_MODEL_NAME = "gpt-4o-mini"
LLM_TEMPERATURE = 0.3
LLM_TIMEOUT_SECONDS = 30
LLM_MAX_RETRIES = 1

# S3 / tenancy
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME") or None
DEFAULT_CHURCH_ID = os.environ.get("CHURCH_ID", "heritage")
CHAT_FUNCTION_NAME = os.environ.get("CHAT_FUNCTION_NAME") or None
DATA_VERSION = os.environ.get("DATA_VERSION", "0")

# Auth / CORS
API_KEYS = [k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip()]
ALLOWED_ORIGINS_ENV = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]

# Logging / server
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
PORT = int(os.environ.get("PORT", "8004"))

# Updater gates
MAX_PAGES = int(os.environ.get("MAX_PAGES", "400"))
MIN_PAGES = int(os.environ.get("MIN_PAGES", "25"))
REGRESSION_RATIO = float(os.environ.get("REGRESSION_RATIO", "0.7"))


def church_runtime_dir(church_id: str) -> Path:
    path = RUNTIME_DIR / church_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def chroma_path(church_id: str) -> Path:
    return church_runtime_dir(church_id) / "chroma_db"


def data_file(church_id: str) -> Path:
    return church_runtime_dir(church_id) / "scraped_data.jsonl"


def manifest_path(church_id: str) -> Path:
    return church_runtime_dir(church_id) / "manifest.json"


def require_openai_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not found. Set it in the environment or .env file.")
    return key
