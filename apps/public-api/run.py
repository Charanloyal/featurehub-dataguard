"""
Runner script for Public Gateway API
Supports direct execution: python apps/public-api/run.py [port]
"""

import sys
from pathlib import Path
import uvicorn

API_DIR = Path(__file__).resolve().parent
ROOT_DIR = API_DIR.parent.parent
for p in [str(API_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from main import app

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
