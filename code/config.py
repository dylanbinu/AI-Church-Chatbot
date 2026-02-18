import os
from dotenv import load_dotenv

# Load environment variables once
load_dotenv()

# Check for API Key
if not os.environ.get("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY not found in environment. Please check your .env file.")

# --- DIRECTORY PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(BASE_DIR, "..")

# --- DATA PATHS ---
# 1. Check for DB in the 'code' folder (Cloud Deployment)
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")
if not os.path.exists(CHROMA_PATH):
    # 2. Fallback to Project Root (Local Dev)
    CHROMA_PATH = os.path.join(PROJECT_ROOT, "chroma_db")

CHURCHES_FILE = os.path.join(BASE_DIR, "churches.json")
DEFAULT_DATA_FILE = os.path.join(BASE_DIR, "scraped_data.jsonl") # Assume copied to code for cloud
if not os.path.exists(DEFAULT_DATA_FILE):
    DEFAULT_DATA_FILE = os.path.join(PROJECT_ROOT, "scraped_data.jsonl")

# --- MODEL CONFIGURATION ---
EMBEDDING_MODEL_NAME = "text-embedding-3-small"
LLM_MODEL_NAME = "gpt-4o-mini"
LLM_TEMPERATURE = 0.3

# --- RETRIEVAL CONFIGURATION ---
# High Value substrings boost relevance
HIGH_VALUE_SUBSTRINGS = [
    "service", "location", "campus", "visit", "time", "about", 
    "connect", "new", "give", "giving", "donate", "team", 
    "staff", "who-we-are", "leadership", "youth", "kid", 
    "child", "student", "christmas"
]

# Low Value substrings reduce relevance
LOW_VALUE_SUBSTRINGS = [
    "event", "pantry", "easter", "calendar", "blog", 
    "news", "message", "sermon"
]
