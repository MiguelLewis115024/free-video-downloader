"""Server-side proxy download: yt-dlp + temp file management + cleanup."""
from __future__ import annotations

import asyncio
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

import yt_dlp

from backend.config import TMP_DIR, TMP_FILE_TTL_SECONDS
from backend.utils import (
    apply_cookies,
    ffmpeg_location,
    is_cookie_decrypt_error,
    normalize_url,
)


_JOBS: dict[str, dict[str, Any]] = {}


def _job_dir(file_id: str) -> Path:
    return TMP_DIR / file_id


def _build_format_selector(format_id: str | None, needs_merge: bool) -> str:
    if not format_id:
        return "bestvideo*+bestaudio/best"
    if needs_merge:
        return f"{format_id}+bestaudio/best"
    return format_id


def download_to_tmp(url: str, format_id: str | None, needs_merge: bool) -> dict[str, Any]:
    """Run yt-dlp to download the chosen format to ``tmp/<file_id>/`` synchronously.

    Returns a job dict containing file_id, file path, original filename, mime type.
    """
    url = normalize_url(url)
    file_id = uuid.uuid4().hex
    out_dir = _job_dir(file_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": str(out_dir / "%(title).80s.%(ext)s"),
        "format": _build_format_selector(format_id, needs_merge),
        "merge_output_format": "mp4",
        "restrictfilenames": True,
    }
    ffmpeg_dir = ffmpeg_location()
    if ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir
    apply_cookies(opts, url)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            final_path = Path(ydl.prepare_filename(info))
    except yt_dlp.utils.DownloadError as e:
        if "cookiesfrombrowser" in opts and is_cookie_decrypt_error(e):
            opts.pop("cookiesfrombrowser", None)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                final_path = Path(ydl.prepare_filename(info))
        else:
            raise

    if not final_path.exists():
        candidates = list(out_dir.glob("*"))
        if candidates:
            final_path = max(candidates, key=lambda p: p.stat().st_size)

    if not final_path.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
        raise FileNotFoundError("yt-dlp 未生成可读文件")

    job = {
        "file_id": file_id,
        "path": str(final_path),
        "filename": final_path.name,
        "size": final_path.stat().st_size,
        "created_at": time.time(),
    }
    _JOBS[file_id] = job
    return job


def get_job(file_id: str) -> dict[str, Any] | None:
    return _JOBS.get(file_id)


def cleanup_job(file_id: str) -> None:
    """Remove the downloaded file and its temp directory."""
    _JOBS.pop(file_id, None)
    job_dir = _job_dir(file_id)
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)


def cleanup_stale_jobs(ttl_seconds: int = TMP_FILE_TTL_SECONDS) -> int:
    """Sweep temp directory and remove anything older than the TTL."""
    if not TMP_DIR.exists():
        return 0
    now = time.time()
    removed = 0
    for sub in TMP_DIR.iterdir():
        try:
            age = now - sub.stat().st_mtime
        except OSError:
            continue
        if age > ttl_seconds:
            shutil.rmtree(sub, ignore_errors=True)
            _JOBS.pop(sub.name, None)
            removed += 1
    return removed


async def periodic_cleanup(interval_seconds: int = 600) -> None:
    """Background task: periodically prune expired temp files."""
    while True:
        try:
            cleanup_stale_jobs()
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)


def iter_file(path: str, chunk_size: int = 1024 * 64):
    """Generator for StreamingResponse."""
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk
