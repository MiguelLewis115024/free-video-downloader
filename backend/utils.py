"""Shared utilities."""
from __future__ import annotations

import os
import re
import shutil
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from backend.config import BASE_DIR, COOKIES_DIR, COOKIES_FILE_ENV


_BIN_NAME = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"


def normalize_url(url: str) -> str:
    """Rewrite list-page / modal-style URLs to a yt-dlp friendly form.

    Some sites (notably douyin.com) expose individual videos via query
    parameters on a user/list page, e.g.
    ``https://www.douyin.com/user/<sec_uid>?modal_id=<video_id>``.
    yt-dlp does not recognise these as video URLs. Rewrite known patterns
    to their canonical single-video form before extraction.
    """
    if not url:
        return url
    url = url.strip()
    try:
        parsed = urlparse(url)
    except ValueError:
        return url

    host = (parsed.netloc or "").lower()
    qs = parse_qs(parsed.query)

    # douyin: user/follow/discover/etc. page with ?modal_id=<video_id>
    if "douyin.com" in host:
        modal_id = (qs.get("modal_id") or [None])[0]
        if modal_id and modal_id.isdigit():
            return f"https://www.douyin.com/video/{modal_id}"

    # bilibili: keep only the BV/av id segment to drop tracking params
    if "bilibili.com" in host:
        m = re.search(r"/(BV[0-9A-Za-z]+|av\d+)", parsed.path)
        if m:
            return f"https://www.bilibili.com/video/{m.group(1)}"

    return url


def _check(candidate: Path) -> str | None:
    if candidate.is_file():
        return str(candidate)
    return None


@lru_cache(maxsize=1)
def find_ffmpeg() -> str | None:
    """Locate ffmpeg, falling back to common env vars and known locations.

    Returns the absolute path to ffmpeg executable, or None if not found.
    Search order: PATH -> FFMPEG_HOME / FFMPEG_PATH / FFMPEG_BIN env vars.
    """
    found = shutil.which("ffmpeg")
    if found:
        return found

    for var in ("FFMPEG_HOME", "FFMPEG_PATH", "FFMPEG_BIN"):
        raw = os.environ.get(var)
        if not raw:
            continue
        base = Path(os.path.expandvars(raw))
        for c in (base / _BIN_NAME, base / "bin" / _BIN_NAME, base):
            result = _check(c)
            if result:
                return result

    return None


def has_ffmpeg() -> bool:
    """Return True if ffmpeg is available (PATH or known env vars)."""
    return find_ffmpeg() is not None


def ffmpeg_location() -> str | None:
    """Return the directory containing ffmpeg, suitable for yt-dlp's
    `ffmpeg_location` option. None if ffmpeg can't be found.
    """
    path = find_ffmpeg()
    return str(Path(path).parent) if path else None


def _browser_profile_paths() -> dict[str, Path]:
    home = Path.home()
    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
        roaming = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
        return {
            "edge": local / "Microsoft/Edge/User Data",
            "chrome": local / "Google/Chrome/User Data",
            "brave": local / "BraveSoftware/Brave-Browser/User Data",
            "chromium": local / "Chromium/User Data",
            "firefox": roaming / "Mozilla/Firefox/Profiles",
            "opera": roaming / "Opera Software/Opera Stable",
            "vivaldi": local / "Vivaldi/User Data",
        }
    if os.name == "posix":
        return {
            "chrome": home / ".config/google-chrome",
            "chromium": home / ".config/chromium",
            "edge": home / ".config/microsoft-edge",
            "brave": home / ".config/BraveSoftware/Brave-Browser",
            "firefox": home / ".mozilla/firefox",
            "opera": home / ".config/opera",
            "vivaldi": home / ".config/vivaldi",
        }
    return {}


@lru_cache(maxsize=1)
def detect_cookies_browser() -> str | None:
    """Pick a browser whose cookie store exists locally, for yt-dlp.

    Honour ``COOKIES_FROM_BROWSER`` env var (comma-separated priority list),
    falling back to a sensible default order. Returns the browser name
    suitable for yt-dlp's ``cookiesfrombrowser`` option, or None.
    """
    default_order = "edge,chrome,firefox,brave,chromium,opera,vivaldi"
    raw = os.environ.get("COOKIES_FROM_BROWSER", default_order)
    if raw.strip().lower() in {"none", "off", "0", "false"}:
        return None
    profiles = _browser_profile_paths()
    for name in (c.strip().lower() for c in raw.split(",") if c.strip()):
        p = profiles.get(name)
        if p and p.exists():
            return name
    return None


# Sites whose yt-dlp extractors **must** have a browser session, otherwise
# every request fails. For these we attempt to auto-attach browser cookies
# even when no cookies.txt is supplied.
# Sites where cookies are only optional (e.g. for higher resolution) are
# intentionally excluded so we don't break public-content downloads when
# the local browser cookie store can't be decrypted (Windows DPAPI etc.).
COOKIE_REQUIRED_HOSTS: tuple[str, ...] = (
    "douyin.com",
    "iesdouyin.com",
    "tiktok.com",
    "xiaohongshu.com",
    "xhslink.com",
    "instagram.com",
)


def is_cookie_decrypt_error(exc: BaseException) -> bool:
    """Detect yt-dlp errors that mean we failed to read the browser cookie
    store (Windows DPAPI / App-Bound Encryption / locked profile / etc.).
    """
    msg = str(exc).lower()
    return any(
        kw in msg
        for kw in (
            "dpapi",
            "app-bound",
            "app bound",
            "could not decrypt",
            "failed to decrypt",
            "permission denied",
            "could not copy chrome cookie",
        )
    )


def needs_browser_cookies(url: str) -> bool:
    """Heuristic: should we attach browser cookies for this URL?"""
    try:
        host = (urlparse(url).netloc or "").lower()
    except ValueError:
        return False
    return any(h in host for h in COOKIE_REQUIRED_HOSTS)


_HOST_HINTS = {
    "douyin.com": "douyin",
    "iesdouyin.com": "douyin",
    "tiktok.com": "tiktok",
    "xiaohongshu.com": "xiaohongshu",
    "xhslink.com": "xiaohongshu",
    "bilibili.com": "bilibili",
    "instagram.com": "instagram",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
}


def _hint_for(url: str) -> str | None:
    try:
        host = (urlparse(url).netloc or "").lower()
    except ValueError:
        return None
    for h, hint in _HOST_HINTS.items():
        if h in host:
            return hint
    return None


def cookies_file_for(url: str) -> str | None:
    """Locate a Netscape-format cookies.txt that yt-dlp can use for this URL.

    Search order:
      1. ``COOKIES_FILE`` env var (used as-is)
      2. ``cookies/<site>.txt`` — site-specific file, e.g. ``cookies/douyin.txt``
      3. ``cookies/cookies.txt`` — generic shared file
      4. ``<project_root>/cookies.txt`` — legacy fallback location
    Returns the absolute path string, or None.
    """
    if COOKIES_FILE_ENV:
        p = Path(os.path.expandvars(COOKIES_FILE_ENV)).expanduser()
        if p.is_file():
            return str(p)

    hint = _hint_for(url)
    candidates: list[Path] = []
    if hint:
        candidates.append(COOKIES_DIR / f"{hint}.txt")
    candidates.append(COOKIES_DIR / "cookies.txt")
    candidates.append(BASE_DIR / "cookies.txt")
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def apply_cookies(opts: dict, url: str) -> dict:
    """Inject cookies options into yt-dlp opts.

    Priority: a manual ``cookies.txt`` file beats the browser cookie store,
    because on Windows + Chrome/Edge 127+ the browser store is encrypted
    with App-Bound Encryption (DPAPI) and cannot be decrypted by yt-dlp.
    """
    cookie_file = cookies_file_for(url)
    if cookie_file:
        opts["cookiefile"] = cookie_file
        return opts

    if not needs_browser_cookies(url):
        return opts

    browser = detect_cookies_browser()
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    return opts
