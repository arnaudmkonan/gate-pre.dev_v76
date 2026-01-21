#!/usr/bin/env python3
"""Run the FastAPI server with proper environment setup."""

import os
import sys
from pathlib import Path

# Set working directory
os.chdir(str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv(".env", override=True)

# Now import and run uvicorn
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload to avoid multiprocessing issues
        log_level="info",
    )
