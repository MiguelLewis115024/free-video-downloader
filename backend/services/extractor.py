"""yt-dlp wrapper: parse video metadata and available formats."""
from __future__ import annotations

from typing import Any

import yt_dlp

from backend.config import VIP_MIN_HEIGHT
from backend.utils import (
    apply_cookies,
    has_ffmpeg,
    is_cookie_decrypt_error,
    normalize_url,
)


_BASE_OPTS: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": True,
}


def _format_filesize(size: int | None) -> str | None:
    if not size:
        return None
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def _format_duration(seconds: int | float | None) -> str | None:
    if not seconds:
        return None
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _resolution_label(fmt: dict[str, Any]) -> str:
    height = fmt.get("height")
    if height:
        if height >= 4320:
            return f"8K ({height}p)"
        if height >= 2160:
            return f"4K ({height}p)"
        if height >= 1440:
            return f"2K ({height}p)"
        return f"{height}p"
    if fmt.get("vcodec") == "none":
        abr = fmt.get("abr")
        return f"音频 {int(abr)}kbps" if abr else "音频"
    return fmt.get("resolution") or fmt.get("format_note") or "未知"


def _build_format(fmt: dict[str, Any]) -> dict[str, Any] | None:
    if not fmt.get("url"):
        return None

    has_audio = fmt.get("acodec") not in (None, "none")
    has_video = fmt.get("vcodec") not in (None, "none")
    height = fmt.get("height") or 0
    filesize = fmt.get("filesize") or fmt.get("filesize_approx")

    return {
        "format_id": fmt["format_id"],
        "ext": fmt.get("ext"),
        "resolution": _resolution_label(fmt),
        "height": height,
        "filesize": filesize,
        "filesize_human": _format_filesize(filesize),
        "url": fmt.get("url"),
        "has_audio": has_audio,
        "has_video": has_video,
        "needs_merge": has_video and not has_audio,
        "is_vip": height >= VIP_MIN_HEIGHT,
        "fps": fmt.get("fps"),
        "vcodec": fmt.get("vcodec"),
        "acodec": fmt.get("acodec"),
    }


def _dedupe_formats(formats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the best (largest filesize) entry per (kind, height/abr, ext)."""

    def key(f: dict[str, Any]) -> tuple:
        if f["has_video"]:
            return ("video", f["height"], f["ext"])
        return ("audio", f.get("fps") or 0, f["ext"])

    seen: dict[tuple, dict[str, Any]] = {}
    for f in formats:
        k = key(f)
        if k not in seen or (f["filesize"] or 0) > (seen[k]["filesize"] or 0):
            seen[k] = f
    return list(seen.values())


def _sort_formats(formats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        formats,
        key=lambda f: (
            0 if f["has_video"] else 1,
            -(f["height"] or 0),
            -(f["filesize"] or 0),
        ),
    )


def extract_info(url: str) -> dict[str, Any]:
    """Parse a URL and return normalized metadata + formats.

    Raises yt_dlp.utils.DownloadError on failure; callers should handle.
    """
    url = normalize_url(url)
    opts = apply_cookies(dict(_BASE_OPTS), url)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        # Auto-fallback: if the browser cookie store can't be decrypted
        # (Windows DPAPI / App-Bound Encryption), retry once without it.
        if "cookiesfrombrowser" in opts and is_cookie_decrypt_error(e):
            opts.pop("cookiesfrombrowser", None)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        else:
            raise

    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]

    raw_formats = info.get("formats") or []
    parsed_formats = [f for f in (_build_format(rf) for rf in raw_formats) if f]
    parsed_formats = _sort_formats(_dedupe_formats(parsed_formats))

    return {
        "title": info.get("title") or "未命名视频",
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "duration_human": _format_duration(info.get("duration")),
        "uploader": info.get("uploader") or info.get("channel"),
        "webpage_url": info.get("webpage_url") or url,
        "extractor": info.get("extractor_key") or info.get("extractor"),
        "formats": parsed_formats,
        "server_has_ffmpeg": has_ffmpeg(),
    }
