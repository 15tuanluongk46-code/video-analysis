"""Chọn key frame theo scene detection + fallback lấy mẫu đều, ghép contact sheet."""

from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

from ..models import FrameInfo
from .media import MediaError, ffmpeg_path

SCENE_THRESHOLD = 0.3
MIN_GAP_SECONDS = 0.4

PROFILES = {
    "balanced": {"min_frames": 12, "max_frames": 24, "per_sheet": 6, "cols": 3, "width": 640},
    "fast": {"min_frames": 6, "max_frames": 10, "per_sheet": 4, "cols": 2, "width": 512},
    "detailed": {"min_frames": 24, "max_frames": 48, "per_sheet": 6, "cols": 3, "width": 640},
}


def profile_settings(profile: str) -> dict:
    return PROFILES.get(profile, PROFILES["balanced"])


def _detect_scenes(video: Path, *, threshold: float = SCENE_THRESHOLD, timeout: int = 300) -> list[tuple[float, float]]:
    """Trả về [(timestamp, scene_score)] từ ffmpeg scene detection."""
    cmd = [
        ffmpeg_path(),
        "-hide_banner",
        "-nostats",
        "-i",
        str(video),
        "-vf",
        f"select='gt(scene,{threshold})',metadata=print:file=-",
        "-an",
        "-f",
        "null",
        "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return []
    found: list[tuple[float, float]] = []
    pending_time: float | None = None
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("frame:"):
            match = re.search(r"pts_time:([0-9.]+)", line)
            pending_time = float(match.group(1)) if match else None
        elif "lavfi.scene_score=" in line and pending_time is not None:
            try:
                score = float(line.rsplit("=", 1)[-1])
            except ValueError:
                score = 0.0
            found.append((pending_time, score))
            pending_time = None
    return found


def _target_count(duration: float, settings: dict) -> int:
    min_frames = settings["min_frames"]
    max_frames = settings["max_frames"]
    if duration <= 0:
        return min_frames
    if duration < 10:
        return max(4, min(max_frames, int(duration * 1.5) + 1))
    want = int(duration / 5) + 1
    return max(min_frames, min(max_frames, want))


def _equal_times(duration: float, count: int) -> list[float]:
    if count <= 0 or duration <= 0:
        return []
    if count == 1:
        return [duration / 2]
    margin = min(1.0, duration * 0.02)
    span = max(0.0, duration - 2 * margin)
    step = span / (count - 1)
    return [round(margin + i * step, 3) for i in range(count)]


def _merge_times(scene: list[tuple[float, float]], equal: list[float], min_gap: float = MIN_GAP_SECONDS) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for time, score in sorted(scene):
        if merged and time - merged[-1][0] < min_gap:
            if score > merged[-1][1]:
                merged[-1] = (time, score)
            continue
        merged.append((time, score))
    for time in equal:
        if any(abs(time - existing) < min_gap for existing, _ in merged):
            continue
        merged.append((time, 0.0))
    merged.sort()
    return merged


def _thin(times: list[tuple[float, float]], max_frames: int) -> list[tuple[float, float]]:
    if len(times) <= max_frames:
        return times
    if max_frames <= 1:
        return times[:1]
    step = (len(times) - 1) / (max_frames - 1)
    picked = {round(i * step) for i in range(max_frames)}
    return [times[i] for i in sorted(picked)]


def sample_frames(
    video: str | Path,
    out_dir: str | Path,
    *,
    duration: float,
    profile: str = "balanced",
    timeout: int = 300,
) -> list[FrameInfo]:
    """Chọn key frames và trích thành JPEG. Trả về danh sách FrameInfo."""
    video = Path(video)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    settings = profile_settings(profile)

    scene = _detect_scenes(video, timeout=timeout)
    equal = _equal_times(duration, _target_count(duration, settings))
    times = _thin(_merge_times(scene, equal), settings["max_frames"])

    frames: list[FrameInfo] = []
    for index, (timestamp, score) in enumerate(times, start=1):
        dest = out_dir / f"frame_{index:04d}.jpg"
        cmd = [
            ffmpeg_path(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(dest),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            continue
        if proc.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
            continue
        frames.append(
            FrameInfo(
                index=len(frames) + 1,
                timestamp=round(timestamp, 3),
                path=str(dest),
                scene_score=round(score, 4),
            )
        )
    if not frames:
        raise MediaError("Không trích được frame nào từ video")
    return frames


def contact_sheets(
    frames: list[FrameInfo],
    out_dir: str | Path,
    *,
    per_sheet: int | None = None,
    cols: int | None = None,
    width: int | None = None,
) -> list[Path]:
    """Ghép frame thành các contact sheet có nhãn timestamp (JPEG)."""
    from PIL import Image, ImageDraw, ImageFont

    settings = profile_settings("balanced")
    per_sheet = per_sheet or settings["per_sheet"]
    cols = cols or settings["cols"]
    width = width or settings["width"]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sheets: list[Path] = []
    font = ImageFont.load_default()
    for sheet_index, start in enumerate(range(0, len(frames), per_sheet), start=1):
        chunk = frames[start : start + per_sheet]
        thumbs = []
        for frame in chunk:
            try:
                image = Image.open(frame.path).convert("RGB")
            except OSError:
                continue
            ratio = width / image.width
            thumbs.append((image.resize((width, max(1, int(image.height * ratio)))), frame))
        if not thumbs:
            continue
        cell_height = max(image.height for image, _ in thumbs)
        rows = math.ceil(len(thumbs) / cols)
        label_height = 18
        canvas = Image.new("RGB", (cols * width, rows * (cell_height + label_height)), (16, 16, 16))
        draw = ImageDraw.Draw(canvas)
        for cell, (image, frame) in enumerate(thumbs):
            row, col = divmod(cell, cols)
            x = col * width
            y = row * (cell_height + label_height)
            canvas.paste(image, (x, y))
            label = f"{frame.index}  {frame.timestamp:.2f}s"
            draw.rectangle([x, y + cell_height, x + width, y + cell_height + label_height], fill=(16, 16, 16))
            draw.text((x + 4, y + cell_height + 3), label, fill=(240, 240, 240), font=font)
        dest = out_dir / f"contact_{sheet_index:02d}.jpg"
        canvas.save(dest, "JPEG", quality=82)
        sheets.append(dest)
    return sheets
