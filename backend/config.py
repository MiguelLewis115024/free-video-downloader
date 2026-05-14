"""Runtime configuration for the universal video downloader."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TMP_DIR = BASE_DIR / "tmp"
COOKIES_DIR = BASE_DIR / "cookies"

TMP_DIR.mkdir(exist_ok=True)
COOKIES_DIR.mkdir(exist_ok=True)

TMP_FILE_TTL_SECONDS = 60 * 60

BATCH_FREE_LIMIT = 3

VIP_MIN_HEIGHT = 2160

# Optional path to a single Netscape-format cookies.txt that yt-dlp can use.
# Override via the COOKIES_FILE env var; otherwise we look for cookies.txt in
# the project root or the cookies/ folder.
COOKIES_FILE_ENV = os.environ.get("COOKIES_FILE")
