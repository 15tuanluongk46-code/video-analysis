from pathlib import Path

import pytest

from video_analyzer.analysis.media import MediaError, extract_audio, format_timestamp, probe


def test_probe_metadata(tiny_video: Path):
    info = probe(tiny_video)
    assert info.width == 320
    assert info.height == 240
    assert info.has_audio is True
    assert 1.5 <= info.duration <= 2.6
    assert 9 <= info.fps <= 11
    assert info.video_codec == "h264"
    assert info.size_bytes > 0


def test_probe_missing_file(tmp_path: Path):
    with pytest.raises(MediaError):
        probe(tmp_path / "khong-ton-tai.mp4")


def test_extract_audio(tiny_video: Path, tmp_path: Path):
    dest = extract_audio(tiny_video, tmp_path / "audio" / "audio.wav")
    assert dest.exists()
    assert dest.stat().st_size > 1000
    assert dest.read_bytes()[:4] == b"RIFF"


def test_format_timestamp():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(65) == "01:05"
    assert format_timestamp(112.533) == "01:53"
    assert format_timestamp(3661) == "01:01:01"
    assert format_timestamp(-5) == "00:00"
