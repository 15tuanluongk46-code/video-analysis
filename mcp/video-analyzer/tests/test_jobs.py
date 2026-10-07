"""Tests for jobs.py (single-worker pipeline)."""
from __future__ import annotations

import json

import pytest

from video_analyzer import cache, jobs
from video_analyzer.models import (
    ErrorCode,
    FrameInfo,
    JobStatus,
    MediaInfo,
    TranscriptSegment,
)


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    root = tmp_path / "cache"
    monkeypatch.setenv("VIDEO_ANALYZER_CACHE", str(root))
    return root


def _patch_pipeline(monkeypatch, *, duration=2.0, has_audio=True, vision_raises=False):
    calls = {"acquire": 0}

    def fake_acquire(url, dest_dir, **kwargs):
        calls["acquire"] += 1
        path = dest_dir / "source.mp4"
        path.write_bytes(b"fake-video")
        return {"path": path, "final_url": url, "method": "direct", "size_bytes": 10}

    def fake_probe(path):
        return MediaInfo(
            duration=duration,
            width=320,
            height=240,
            fps=10.0,
            has_audio=has_audio,
            video_codec="h264",
            audio_codec="aac",
            size_bytes=10,
        )

    def fake_sample(video, out_dir, *, duration, profile="balanced", timeout=300):
        out_dir.mkdir(parents=True, exist_ok=True)
        frames = []
        for index, timestamp in enumerate([0.0, 1.0]):
            path = out_dir / f"frame_{index:04d}.jpg"
            path.write_bytes(b"jpg")
            frames.append(
                FrameInfo(index=index, timestamp=timestamp, path=path, scene_score=0.5)
            )
        return frames

    def fake_sheets(frames, out_dir, **kwargs):
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "contact_00.jpg"
        path.write_bytes(b"jpg")
        return [path]

    def fake_extract(video, dest, **kwargs):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"RIFF")
        return dest

    def fake_transcribe(audio, **kwargs):
        return [TranscriptSegment(0.0, 1.0, "xin chào"), TranscriptSegment(1.0, 2.0, "tạm biệt")]

    def fake_vision(sheets, *, frames=None, **kwargs):
        if vision_raises:
            raise jobs.VisionUnavailable("ollama down")
        return "Mô tả cảnh"

    monkeypatch.setattr(jobs, "acquire", fake_acquire)
    monkeypatch.setattr(jobs, "probe", fake_probe)
    monkeypatch.setattr(jobs, "sample_frames", fake_sample)
    monkeypatch.setattr(jobs, "contact_sheets", fake_sheets)
    monkeypatch.setattr(jobs, "extract_audio", fake_extract)
    monkeypatch.setattr(jobs, "transcribe", fake_transcribe)
    monkeypatch.setattr(jobs, "describe_contact_sheets", fake_vision)
    return calls


def _manager():
    return jobs.JobManager(auto_start=False)


def test_run_sync_completes_and_writes_evidence(tmp_path, monkeypatch):
    calls = _patch_pipeline(monkeypatch)
    manager = _manager()
    job = manager.submit("https://example.com/v.mp4")

    manager.run_sync(job)

    assert job.status == JobStatus.COMPLETED
    assert job.phase == "completed"
    assert job.progress == 100.0
    assert calls["acquire"] == 1

    manifest = cache.load_manifest(job.cache_id)
    assert manifest["status"] == "completed"
    assert manifest["media"]["duration"] == 2.0
    assert manifest["frames"][0]["path"] == "frames/frame_0000.jpg"
    assert manifest["contact_sheets"] == ["contact-sheets/contact_00.jpg"]
    assert manifest["transcript_file"] == "transcript.json"
    assert manifest["vision"]["available"] is True

    evidence = json.loads(cache.evidence_path(job.cache_id).read_text(encoding="utf-8"))
    assert evidence["analyzed_intervals"] == [[0.0, 2.0]]
    assert evidence["transcript"]["segment_count"] == 2
    assert evidence["transcript"]["speech_seconds"] == 2.0
    assert evidence["transcript"]["text"] == "xin chào tạm biệt"
    assert evidence["vision"]["text"] == "Mô tả cảnh"
    assert evidence["errors"] == []


def test_second_run_reuses_cache(monkeypatch):
    calls = _patch_pipeline(monkeypatch)
    manager = _manager()
    first = manager.submit("https://example.com/v.mp4")
    manager.run_sync(first)

    second = manager.submit("https://example.com/v.mp4")
    manager.run_sync(second)

    assert second.status == JobStatus.COMPLETED
    assert second.cache_id == first.cache_id
    assert calls["acquire"] == 1


def test_duration_limit_fails_job(monkeypatch):
    _patch_pipeline(monkeypatch, duration=700.0)
    manager = _manager()
    job = manager.submit("https://example.com/v.mp4", max_duration_seconds=600)

    manager.run_sync(job)

    assert job.status == JobStatus.FAILED
    assert job.error_code == ErrorCode.DURATION_LIMITED


def test_invalid_url_fails_job():
    manager = _manager()
    job = manager.submit("file:///etc/passwd")

    manager.run_sync(job)

    assert job.status == JobStatus.FAILED
    assert job.error_code == ErrorCode.UNSUPPORTED_URL


def test_vision_unavailable_still_completes(monkeypatch):
    _patch_pipeline(monkeypatch, vision_raises=True)
    manager = _manager()
    job = manager.submit("https://example.com/v.mp4")

    manager.run_sync(job)

    assert job.status == JobStatus.COMPLETED
    manifest = cache.load_manifest(job.cache_id)
    assert manifest["vision"]["available"] is False
    codes = [row["code"] for row in manifest["errors"]]
    assert ErrorCode.VISION_UNAVAILABLE in codes


def test_no_audio_records_error_and_completes(monkeypatch):
    _patch_pipeline(monkeypatch, has_audio=False)
    manager = _manager()
    job = manager.submit("https://example.com/v.mp4")

    manager.run_sync(job)

    assert job.status == JobStatus.COMPLETED
    manifest = cache.load_manifest(job.cache_id)
    codes = [row["code"] for row in manifest["errors"]]
    assert ErrorCode.NO_AUDIO in codes
    evidence = json.loads(cache.evidence_path(job.cache_id).read_text(encoding="utf-8"))
    assert evidence["transcript"]["segment_count"] == 0


def test_resolved_media_url_used_for_acquisition(monkeypatch):
    seen = {}

    def fake_acquire(url, dest_dir, **kwargs):
        seen["url"] = url
        path = dest_dir / "source.mp4"
        path.write_bytes(b"fake")
        return {"path": path, "final_url": url, "method": "direct", "size_bytes": 4}

    _patch_pipeline(monkeypatch)
    monkeypatch.setattr(jobs, "acquire", fake_acquire)
    manager = _manager()
    job = manager.submit(
        "https://x.com/u/status/1", resolved_media_url="https://cdn.example.com/v.mp4"
    )

    manager.run_sync(job)

    assert seen["url"] == "https://cdn.example.com/v.mp4"
    assert job.cache_id == cache.cache_id_for(
        "https://x.com/u/status/1", "https://cdn.example.com/v.mp4"
    )
