"""HTTP API: parse, download (proxy), batch parse, stream file."""
from __future__ import annotations

import asyncio
from urllib.parse import quote
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import yt_dlp

from backend.config import BATCH_FREE_LIMIT
from backend.services import downloader, extractor
from backend.utils import detect_cookies_browser, has_ffmpeg, needs_browser_cookies


router = APIRouter()


_COOKIES_HOWTO = (
    "请走「cookies.txt」方案：\n"
    "1) 在 Edge/Chrome 商店安装扩展「Get cookies.txt LOCALLY」\n"
    "2) 打开目标站点（如 https://www.douyin.com）并滑动几条视频\n"
    "3) 点扩展图标 → Export → 保存为 cookies.txt\n"
    "4) 把文件放到项目目录 cookies/douyin.txt（或 cookies/cookies.txt 作为通用）\n"
    "5) 回到本页面重试即可。"
)


def _friendly_error(url: str, raw: str) -> str:
    """Translate noisy yt-dlp messages into actionable Chinese hints."""
    low = raw.lower()

    if "dpapi" in low or "app-bound" in low or "app bound" in low:
        return (
            "无法解密本机 Chrome/Edge 的 cookies（Windows DPAPI / App-Bound Encryption 限制，"
            "这是 yt-dlp 已知 issue #10927）。"
            + _COOKIES_HOWTO
        )

    if "fresh cookies" in low or "cookies are needed" in low or "login required" in low:
        browser = detect_cookies_browser()
        if needs_browser_cookies(url) and not browser:
            return (
                "该站点要求浏览器 cookies，但服务端未检测到可用的本地浏览器。"
                + _COOKIES_HOWTO
            )
        return (
            f"该站点需要新鲜的浏览器 cookies（已尝试自动从 {browser or '本机浏览器'} 读取仍失败）。"
            + _COOKIES_HOWTO
        )
    if "unsupported url" in low:
        return "该链接暂不支持，请确认是视频详情页（如 douyin.com/video/<id>）。"
    if "private video" in low or "members-only" in low:
        return "该视频为私密 / 会员专享，无法解析。"
    if "geo" in low and "restrict" in low:
        return "该视频存在地区限制，当前服务器 IP 无法访问。"
    return raw[:240]


class ParseRequest(BaseModel):
    url: str = Field(..., min_length=4, description="Video page URL")


class DownloadRequest(BaseModel):
    url: str = Field(..., min_length=4)
    format_id: str | None = None
    needs_merge: bool = False


class BatchRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1)


def _parse_one(url: str) -> dict[str, Any]:
    return extractor.extract_info(url)


@router.post("/parse")
async def parse(req: ParseRequest) -> dict[str, Any]:
    try:
        info = await asyncio.to_thread(_parse_one, req.url)
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(
            status_code=400,
            detail=f"无法解析该链接：{_friendly_error(req.url, str(e))}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器解析异常：{str(e)[:200]}")
    return {"ok": True, "data": info}


@router.post("/download")
async def download(req: DownloadRequest) -> dict[str, Any]:
    """Server-side proxy download. Returns a file_id usable with /api/file/{id}."""
    if req.needs_merge and not has_ffmpeg():
        raise HTTPException(
            status_code=400,
            detail=(
                "该清晰度需要合并音视频流，但服务器未安装 ffmpeg。"
                "请选择不带「需合并」标记的格式，或安装 ffmpeg 后重试。"
            ),
        )

    try:
        job = await asyncio.to_thread(
            downloader.download_to_tmp,
            req.url,
            req.format_id,
            req.needs_merge,
        )
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        low = msg.lower()
        if "ffmpeg is not installed" in low or ("ffmpeg" in low and "install" in low):
            raise HTTPException(
                status_code=400,
                detail="服务器未安装 ffmpeg，无法合并音视频。请选择不带「需合并」标记的格式。",
            )
        raise HTTPException(status_code=400, detail=f"下载失败：{_friendly_error(req.url, msg)}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器下载异常：{str(e)[:200]}")

    return {
        "ok": True,
        "file_id": job["file_id"],
        "filename": job["filename"],
        "size": job["size"],
    }


@router.post("/batch")
async def batch(req: BatchRequest) -> dict[str, Any]:
    urls = [u.strip() for u in req.urls if u and u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="请至少输入一个有效链接")

    over_limit = len(urls) > BATCH_FREE_LIMIT
    free_urls = urls[:BATCH_FREE_LIMIT]

    results: list[dict[str, Any]] = []
    for url in free_urls:
        try:
            info = await asyncio.to_thread(_parse_one, url)
            results.append({"ok": True, "url": url, "data": info})
        except Exception as e:
            results.append({"ok": False, "url": url, "error": str(e)[:200]})

    return {
        "ok": True,
        "results": results,
        "free_limit": BATCH_FREE_LIMIT,
        "over_limit": over_limit,
        "total_submitted": len(urls),
        "vip_required_count": max(0, len(urls) - BATCH_FREE_LIMIT),
    }


@router.get("/file/{file_id}")
async def get_file(file_id: str, background_tasks: BackgroundTasks):
    job = downloader.get_job(file_id)
    if not job:
        raise HTTPException(status_code=404, detail="文件不存在或已过期")

    background_tasks.add_task(downloader.cleanup_job, file_id)

    encoded = quote(job["filename"])
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        "Content-Length": str(job["size"]),
    }
    return StreamingResponse(
        downloader.iter_file(job["path"]),
        media_type="application/octet-stream",
        headers=headers,
    )
