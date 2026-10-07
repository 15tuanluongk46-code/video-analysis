"""Tải media: direct media URL -> resolver X/Twitter -> yt-dlp -> NEEDS_BROWSER (fallback Chrome)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ErrorCode
from .security import SecurityError, download_to

MAX_DOWNLOAD_BYTES = 750 * 1024 * 1024

VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi")
HLS_EXTENSIONS = (".m3u8", ".mpd")

_NEEDS_BROWSER_HINTS = (
    "sign in",
    "log in",
    "login",
    "cookies",
    "bot",
    "confirm your age",
    "age-restricted",
    "private video",
    "unsupported url",
    "requires authentication",
)
_DRM_HINTS = ("drm", "encrypted", "protected")


class _NoFileDownloaded(Exception):
    pass


def guess_media_kind(url: str) -> str:
    """'video' | 'hls' | 'unknown' dựa trên đuôi URL (bỏ query string)."""
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    if path.endswith(HLS_EXTENSIONS):
        return "hls"
    if path.endswith(VIDEO_EXTENSIONS):
        return "video"
    return "unknown"


_TWEET_URL_RE = re.compile(
    r"^https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/([A-Za-z0-9_]+)/status(?:es)?/(\d+)"
)


def _tweet_ids(url: str) -> tuple[str, str] | None:
    """(handle, tweet_id) nếu URL là tweet X/Twitter, ngược lại None."""
    match = _TWEET_URL_RE.match(url)
    return (match.group(1), match.group(2)) if match else None


def resolve_twitter_media(url: str, *, timeout: float = 6.0) -> str | None:
    """Tweet URL -> direct media URL qua API công khai (vxtwitter/fxtwitter).

    Không cần đăng nhập/Chrome. Trả None nếu không resolve được.
    """
    ids = _tweet_ids(url)
    if not ids:
        return None
    handle, tweet_id = ids
    from urllib.request import Request, urlopen

    endpoints = (
        (f"https://api.vxtwitter.com/{handle}/status/{tweet_id}", "curl/8.5.0"),
        (f"https://api.fxtwitter.com/{handle}/status/{tweet_id}", "Mozilla/5.0"),
    )
    for endpoint, user_agent in endpoints:
        try:
            req = Request(endpoint, headers={"User-Agent": user_agent})
            with urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception:
            continue
        media_urls = data.get("mediaURLs") or []
        if media_urls:
            return str(media_urls[0])
        media = data.get("media")
        if not isinstance(media, dict):
            media = (data.get("tweet") or {}).get("media") or {}
        videos = media.get("videos") or []
        if videos and videos[0].get("url"):
            return str(videos[0]["url"])
    return None


def _ytdlp_probe(url: str) -> bool:
    """yt-dlp có extract được URL không (chỉ metadata, không tải file)."""
    try:
        import yt_dlp

        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "socket_timeout": 8,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        return bool(info)
    except Exception:
        return False


def probe_media_kind(url: str) -> str:
    """Đoán loại media; URL không rõ đuôi thì probe thật trước khi kết luận.

    Dùng cho video_inspect: tránh false-positive NEEDS_BROWSER với X/Twitter,
    TikTok, Instagram, Facebook... khi yt-dlp tự extract được.
    """
    kind = guess_media_kind(url)
    if kind != "unknown":
        return kind
    if _tweet_ids(url):
        resolved = resolve_twitter_media(url)
        if resolved and guess_media_kind(resolved) == "video":
            return "video"
    if _ytdlp_probe(url):
        return "video"
    return "unknown"


def _classify_ytdlp_error(exc: Exception) -> ErrorCode:
    message = str(exc).lower()
    if any(hint in message for hint in _DRM_HINTS):
        return ErrorCode.DRM_OR_ENCRYPTED
    if any(hint in message for hint in _NEEDS_BROWSER_HINTS):
        return ErrorCode.NEEDS_BROWSER
    return ErrorCode.DOWNLOAD_FAILED


def _ytdlp_download(url: str, dest_dir: Path, *, max_bytes: int = MAX_DOWNLOAD_BYTES) -> Path:
    """Tải bằng yt-dlp (1 video, không playlist). Trả về file đã tải."""
    import yt_dlp

    dest_dir.mkdir(parents=True, exist_ok=True)
    options = {
        "outtmpl": str(dest_dir / "source.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4/mkv",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": max_bytes,
        "retries": 2,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True) or {}

    for candidate in sorted(dest_dir.glob("source.*")):
        if candidate.suffix.lower() in (".part", ".ytdl", ".temp"):
            continue
        if candidate.stat().st_size > 0:
            return candidate
    declared = info.get("filesize") or info.get("filesize_approx") or 0
    if declared and declared > max_bytes:
        raise _NoFileDownloaded("vượt giới hạn dung lượng")
    raise _NoFileDownloaded("không tìm thấy file sau khi tải")


def acquire(
    url: str,
    dest_dir: str | Path,
    *,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    transport=None,
    progress=None,
) -> dict:
    """Tải 1 video về dest_dir. Trả về {path, final_url, method, size_bytes}.

    Thứ tự: direct media URL -> resolver X/Twitter -> yt-dlp -> SecurityError(NEEDS_BROWSER).
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    kind = guess_media_kind(url)

    if kind == "unknown" and _tweet_ids(url):
        resolved = resolve_twitter_media(url)
        if resolved and guess_media_kind(resolved) == "video":
            dest = dest_dir / "source.mp4"
            try:
                final_url, written = download_to(
                    resolved, dest, max_bytes=max_bytes, transport=transport, progress=progress
                )
                return {
                    "path": dest,
                    "final_url": final_url,
                    "method": "resolver",
                    "size_bytes": written,
                }
            except SecurityError as exc:
                if exc.code in (ErrorCode.MEDIA_TOO_LARGE, ErrorCode.UNSUPPORTED_URL):
                    raise

    if kind == "video":
        suffix = Path(url.split("?", 1)[0]).suffix.lower() or ".mp4"
        dest = dest_dir / f"source{suffix}"
        try:
            final_url, written = download_to(
                url, dest, max_bytes=max_bytes, transport=transport, progress=progress
            )
            return {"path": dest, "final_url": final_url, "method": "direct", "size_bytes": written}
        except SecurityError as exc:
            if exc.code in (ErrorCode.MEDIA_TOO_LARGE, ErrorCode.UNSUPPORTED_URL):
                raise
            direct_error = exc
    else:
        direct_error = None

    try:
        path = _ytdlp_download(url, dest_dir, max_bytes=max_bytes)
        return {"path": path, "final_url": url, "method": "yt-dlp", "size_bytes": path.stat().st_size}
    except _NoFileDownloaded as exc:
        raise SecurityError(
            ErrorCode.MEDIA_TOO_LARGE,
            f"Media vượt giới hạn {max_bytes // (1024 * 1024)}MB hoặc không tải được: {url}",
        ) from exc
    except Exception as exc:  # yt_dlp.utils.DownloadError và lỗi mạng
        code = _classify_ytdlp_error(exc)
        detail = re.sub(r"\s+", " ", str(exc))[:300]
        if code == ErrorCode.NEEDS_BROWSER:
            raise SecurityError(
                ErrorCode.NEEDS_BROWSER,
                f"Cần Chrome để lấy media URL (đăng nhập/bot-check): {detail}",
            ) from exc
        if direct_error is not None and code == ErrorCode.DOWNLOAD_FAILED:
            detail = f"direct: {direct_error.message}; yt-dlp: {detail}"
        raise SecurityError(code, f"Tải media thất bại: {detail}") from exc
