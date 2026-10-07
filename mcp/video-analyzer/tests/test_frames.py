from pathlib import Path

from video_analyzer.analysis.frames import (
    _equal_times,
    _merge_times,
    _thin,
    contact_sheets,
    sample_frames,
)


def test_sample_frames_on_cut_video(cut_video: Path, tmp_path: Path):
    frames = sample_frames(cut_video, tmp_path / "frames", duration=4.0, profile="balanced")
    assert len(frames) >= 4
    assert all(Path(f.path).exists() for f in frames)
    timestamps = [f.timestamp for f in frames]
    assert timestamps == sorted(timestamps)
    assert all(0 <= t <= 4.2 for t in timestamps)
    assert any(f.scene_score > 0.0 for f in frames)


def test_contact_sheets(cut_video: Path, tmp_path: Path):
    frames = sample_frames(cut_video, tmp_path / "frames", duration=4.0, profile="balanced")
    sheets = contact_sheets(frames, tmp_path / "sheets")
    assert sheets
    assert all(s.exists() and s.stat().st_size > 0 for s in sheets)
    assert sheets[0].name.startswith("contact_")


def test_equal_times_bounds():
    times = _equal_times(100.0, 5)
    assert len(times) == 5
    assert times == sorted(times)
    assert 0 <= times[0] <= 5
    assert 95 <= times[-1] <= 100


def test_merge_times_dedups_close_scene_and_equal():
    merged = _merge_times([(2.0, 0.5), (2.1, 0.9)], [2.05, 10.0])
    assert len(merged) == 2
    assert merged[0] == (2.1, 0.9)
    assert merged[1][0] == 10.0


def test_thin_keeps_first_and_last():
    times = [(float(i), 0.0) for i in range(100)]
    thinned = _thin(times, 10)
    assert len(thinned) == 10
    assert thinned[0] == times[0]
    assert thinned[-1] == times[-1]
