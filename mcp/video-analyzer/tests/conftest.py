"""Fixture dùng chung: video test nhỏ tạo bằng ffmpeg (skip nếu thiếu encoder)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FFMPEG = shutil.which("ffmpeg") or "/home/sss/.local/bin/ffmpeg"


def _run(cmd: list[str]) -> bool:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


@pytest.fixture(scope="session")
def ffmpeg_bin() -> str:
    if not Path(FFMPEG).exists():
        pytest.skip("ffmpeg không có trên máy")
    return FFMPEG


@pytest.fixture(scope="session")
def tiny_video(tmp_path_factory: pytest.TempPathFactory, ffmpeg_bin: str) -> Path:
    """Video 2s, 320x240, 10fps, có audio."""
    dest = tmp_path_factory.mktemp("media") / "tiny.mp4"
    ok = _run(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=10:duration=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(dest),
        ]
    )
    if not ok:
        pytest.skip("không tạo được video test (thiếu encoder libx264)")
    return dest


@pytest.fixture(scope="session")
def cut_video(tmp_path_factory: pytest.TempPathFactory, ffmpeg_bin: str) -> Path:
    """Video 4s có 1 cảnh cắt rõ ở giây thứ 2 (testsrc2 -> red), không audio."""
    dest = tmp_path_factory.mktemp("media") / "cut.mp4"
    ok = _run(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=10:duration=2",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:size=320x240:rate=10:duration=2",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ]
    )
    if not ok:
        pytest.skip("không tạo được video test (thiếu encoder libx264)")
    return dest
