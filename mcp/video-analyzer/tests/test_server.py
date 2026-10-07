"""Tests for server.py (MCP tools)."""
from __future__ import annotations

import json

import pytest

from video_analyzer import cache, server
from video_analyzer.models import Job, JobStatus


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    root = tmp_path / "cache"
    monkeypatch.setenv("VIDEO_ANALYZER_CACHE", str(root))
    return root


class _FakeManager:
    def __init__(self):
        self.submitted = []

    def submit(
        self,
        url,
        *,
        resolved_media_url=None,
        profile="balanced",
        max_duration_seconds=600,
    ):
        self.submitted.append(
            {
                "url": url,
                "resolved": resolved_media_url,
                "profile": profile,
                "max": max_duration_seconds,
            }
        )
        return Job(
            job_id="job123",
            url=url,
            resolved_media_url=resolved_media_url,
            profile=profile,
            max_duration_seconds=max_duration_seconds,
            cache_id="cid123",
        )

    def get(self, job_id):
        if job_id == "job123":
            return Job(
                job_id="job123",
                url="https://example.com/v.mp4",
                status=JobStatus.RUNNING,
                phase="sample",
                progress=35.0,
                cache_id="cid123",
            )
        return None


@pytest.fixture()
def fake_manager(monkeypatch):
    manager = _FakeManager()
    monkeypatch.setattr(server, "_manager", manager)
    return manager


def test_video_inspect_ready(fake_manager):
    out = server.video_inspect("https://example.com/video.mp4")
    assert out["status"] == "READY"
    assert out["kind"] == "video"
    assert out["cache_id"]


def test_video_inspect_needs_browser(fake_manager):
    out = server.video_inspect("https://example.com/watch/page")
    assert out["status"] == "NEEDS_BROWSER"
    assert out["kind"] == "unknown"


def test_video_inspect_bad_url(fake_manager):
    out = server.video_inspect("file:///etc/passwd")
    assert out["status"] == "UNSUPPORTED"
    assert out["error_code"] == "UNSUPPORTED_URL"


def test_video_inspect_cached(fake_manager):
    cache_id = cache.cache_id_for("https://example.com/video.mp4")
    manifest = cache.create_entry(cache_id, "https://example.com/video.mp4")
    manifest["status"] = "completed"
    manifest["media"] = {"duration": 2.0}
    cache.save_manifest(cache_id, manifest)

    out = server.video_inspect("https://example.com/video.mp4")

    assert out["status"] == "CACHED"
    assert out["cache_id"] == cache_id
    assert out["media"]["duration"] == 2.0


def test_video_inspect_cached_by_resolved_url(fake_manager):
    source = "https://x.com/u/status/1"
    cache_id = cache.cache_id_for(source, "https://cdn.example.com/v.mp4")
    manifest = cache.create_entry(cache_id, source, "https://cdn.example.com/v.mp4")
    manifest["status"] = "completed"
    cache.save_manifest(cache_id, manifest)

    out = server.video_inspect(source)

    assert out["status"] == "CACHED"
    assert out["cache_id"] == cache_id


def test_video_analyze_submits(fake_manager):
    out = server.video_analyze(
        "https://example.com/video.mp4",
        resolved_media_url="https://cdn.example.com/v.mp4",
        profile="fast",
        max_duration_seconds=120,
    )

    assert out["job_id"] == "job123"
    assert out["cache_id"] == "cid123"
    assert fake_manager.submitted[0]["resolved"] == "https://cdn.example.com/v.mp4"
    assert fake_manager.submitted[0]["profile"] == "fast"
    assert fake_manager.submitted[0]["max"] == 120


def test_video_analyze_bad_url(fake_manager):
    out = server.video_analyze("notaurl")
    assert out["status"] == "ERROR"
    assert out["error_code"] == "UNSUPPORTED_URL"
    assert fake_manager.submitted == []


def test_video_analyze_bad_resolved_url(fake_manager):
    out = server.video_analyze("https://example.com/v.mp4", resolved_media_url="http://127.0.0.1/x.mp4")
    assert out["status"] == "ERROR"
    assert out["error_code"] == "UNSUPPORTED_URL"
    assert fake_manager.submitted == []


def test_video_job_status(fake_manager):
    out = server.video_job_status("job123")
    assert out["job_id"] == "job123"
    assert out["phase"] == "sample"
    assert out["progress"] == 35.0


def test_video_job_status_missing(fake_manager):
    out = server.video_job_status("nope")
    assert out["error_code"] == "JOB_NOT_FOUND"


def _write_evidence(cache_id: str) -> None:
    cache.evidence_path(cache_id).parent.mkdir(parents=True, exist_ok=True)
    evidence = {
        "cache_id": cache_id,
        "source_url": "https://example.com/v.mp4",
        "resolved_media_url": None,
        "media": {"duration": 2.0},
        "analyzed_intervals": [[0.0, 2.0]],
        "frames": [
            {"index": 0, "timestamp": 0.0, "path": "frames/frame_0000.jpg"},
            {"index": 1, "timestamp": 1.5, "path": "frames/frame_0001.jpg"},
        ],
        "contact_sheets": ["contact-sheets/contact_00.jpg"],
        "transcript": {
            "segment_count": 1,
            "text": "hi",
            "segments": [{"start": 0.0, "end": 1.0, "text": "hi"}],
        },
        "vision": {"available": True, "text": "cảnh"},
        "errors": [],
        "report_sections": ["summary"],
    }
    cache.evidence_path(cache_id).write_text(
        json.dumps(evidence, ensure_ascii=False), encoding="utf-8"
    )


def test_video_get_evidence_resolves_frame_paths(fake_manager):
    _write_evidence("cid1")
    out = server.video_get_evidence("cid1")

    entry = cache.entry_dir("cid1")
    assert out["cache_id"] == "cid1"
    assert out["frames"][0]["path"] == str(entry / "frames" / "frame_0000.jpg")


def test_video_get_evidence_section_filter(fake_manager):
    _write_evidence("cid1")
    out = server.video_get_evidence("cid1", sections=["transcript"])

    assert out["cache_id"] == "cid1"
    assert "transcript" in out
    assert "vision" not in out


def test_video_get_evidence_time_filter(fake_manager):
    _write_evidence("cid1")
    out = server.video_get_evidence("cid1", start_seconds=1.1, end_seconds=2.0)

    assert [frame["index"] for frame in out["frames"]] == [1]
    assert out["transcript"]["segment_count"] == 0
    assert out["window"] == {"start_seconds": 1.1, "end_seconds": 2.0}


def test_video_get_evidence_missing(fake_manager):
    out = server.video_get_evidence("nope")
    assert out["error_code"] == "NOT_FOUND"


def test_video_cache_info_and_cleanup(fake_manager):
    cache_id = cache.cache_id_for("https://example.com/video.mp4")
    manifest = cache.create_entry(cache_id, "https://example.com/video.mp4")
    manifest["status"] = "completed"
    cache.save_manifest(cache_id, manifest)

    info = server.video_cache_info()
    assert info["total_bytes"] >= 0
    assert any(row["cache_id"] == cache_id for row in info["entries"])

    one = server.video_cache_info(cache_id)
    assert one["found"] is True

    cleaned = server.video_cache_cleanup(0)
    assert cleaned["removed_count"] == 1
