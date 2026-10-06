import sys
from pathlib import Path

# Ensure `code/` is on sys.path when running pytest from repo root
CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
