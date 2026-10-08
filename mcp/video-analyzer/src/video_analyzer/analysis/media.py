"""FFmpeg/ffprobe: probe metadata, extract audio, format timestamps."""

from __future__ import annotations

import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from ..models import MediaInfo


class MediaError(Exception):
    """Lỗi xử lý media (file hỏng, thiếu ffmpeg, ffprobe thất bại)."""


def ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "ffmpeg"
    if fallback.is_file():
        return str(fallback)
    raise MediaError("Không tìm thấy ffmpeg trên máy")


def ffprobe_path() -> str:
    found = shutil.which("ffprobe")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "ffprobe"
    if fallback.is_file():
        return str(fallback)
    raise MediaError("Không tìm thấy ffprobe trên máy")


def _parse_fps(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return round(float(Fraction(value)), 3)
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe(path: str | Path) -> MediaInfo:
    """Đọc metadata của file media bằng ffprobe."""
    path = Path(path)
    if not path.exists():
        raise MediaError(f"File không tồn tại: {path}")
    cmd = [
        ffprobe_path(),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"ffprobe quá thời gian cho {path.name}") from exc
    if proc.returncode != 0:
        raise MediaError(f"ffprobe thất bại cho {path.name}: {proc.stderr.strip()[:300]}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError(f"ffprobe trả về JSON không hợp lệ cho {path.name}") from exc

    streams = data.get("streams", [])
    fmt = data.get("format", {})
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = 0.0
    for source in (fmt.get("duration"), (video or {}).get("duration")):
        try:
            duration = float(source)
            break
        except (TypeError, ValueError):
            continue

    size = 0
    try:
        size = int(fmt.get("size") or path.stat().st_size)
    except (TypeError, ValueError, OSError):
        size = path.stat().st_size if path.exists() else 0

    return MediaInfo(
        duration=round(duration, 3),
        width=int((video or {}).get("width") or 0),
        height=int((video or {}).get("height") or 0),
        fps=_parse_fps((video or {}).get("r_frame_rate")),
        has_audio=audio is not None,
        video_codec=(video or {}).get("codec_name") or "",
        audio_codec=(audio or {}).get("codec_name") or "",
        size_bytes=size,
    )


def extract_audio(
    path: str | Path,
    dest: str | Path,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    timeout: int = 600,
) -> Path:
    """Tách audio thành WAV mono 16kHz (đầu vào cho whisper)."""
    path = Path(path)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(path),
        "-vn",
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(dest),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Tách audio quá thời gian") from exc
    if proc.returncode != 0 or not dest.exists():
        raise MediaError(f"Tách audio thất bại: {proc.stderr.strip()[:300]}")
    return dest


def format_timestamp(seconds: float) -> str:
    """Đổi giây thành MM:SS hoặc HH:MM:SS."""
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
