"""MCP server video-analyzer: phân tích video từ URL, trả evidence có timestamp."""
from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import cache
from .acquisition import guess_media_kind, probe_media_kind
from .jobs import JobManager
from .security import SecurityError, validate_url

mcp = FastMCP("video-analyzer")
_manager = JobManager()


def _find_fresh_by_source(url: str) -> tuple[str, dict] | None:
    for row in cache.list_entries():
        manifest = cache.load_manifest(row["cache_id"])
        if not manifest:
            continue
        if (
            manifest.get("source_url") == url
            and manifest.get("status") == "completed"
            and cache.is_fresh(manifest)
        ):
            return row["cache_id"], manifest
    return None


@mcp.tool()
def video_inspect(url: str) -> dict[str, Any]:
    """Kiểm tra URL video: đã có cache chưa, tải trực tiếp được không, hay cần Chrome.

    Trả về status: CACHED | READY | NEEDS_BROWSER | UNSUPPORTED | ERROR.
    """
    try:
        final = validate_url(url)
    except SecurityError as exc:
        return {"status": "UNSUPPORTED", "error_code": exc.code, "error": exc.message}

    cache_id = cache.cache_id_for(final)
    manifest = cache.get_fresh(cache_id, cache.TTL_HOURS)
    if manifest is not None:
        return {
            "status": "CACHED",
            "cache_id": cache_id,
            "url": final,
            "media": manifest.get("media"),
            "analyzed_intervals": manifest.get("analyzed_intervals", []),
        }
    found = _find_fresh_by_source(final)
    if found is not None:
        found_id, found_manifest = found
        return {
            "status": "CACHED",
            "cache_id": found_id,
            "url": final,
            "media": found_manifest.get("media"),
            "analyzed_intervals": found_manifest.get("analyzed_intervals", []),
        }

    kind = guess_media_kind(final)
    if kind == "unknown":
        kind = probe_media_kind(final)
    return {
        "status": "READY" if kind in ("video", "hls") else "NEEDS_BROWSER",
        "cache_id": cache_id,
        "url": final,
        "kind": kind,
    }


@mcp.tool()
def video_analyze(
    url: str,
    resolved_media_url: str | None = None,
    profile: str = "balanced",
    max_duration_seconds: float = 600,
) -> dict[str, Any]:
    """Đưa video vào hàng đợi phân tích; trả về job_id để theo dõi bằng video_job_status."""
    try:
        validate_url(url)
    except SecurityError as exc:
        return {"status": "ERROR", "error_code": exc.code, "error": exc.message}
    if resolved_media_url:
        try:
            validate_url(resolved_media_url)
        except SecurityError as exc:
            return {"status": "ERROR", "error_code": exc.code, "error": exc.message}

    job = _manager.submit(
        url,
        resolved_media_url=resolved_media_url,
        profile=profile,
        max_duration_seconds=max_duration_seconds,
    )
    return {
        "job_id": job.job_id,
        "cache_id": job.cache_id,
        "status": job.status,
        "phase": job.phase,
    }


@mcp.tool()
def video_job_status(job_id: str) -> dict[str, Any]:
    """Trạng thái job phân tích: phase, progress, lỗi (nếu có)."""
    job = _manager.get(job_id)
    if job is None:
        return {
            "error_code": "JOB_NOT_FOUND",
            "error": f"Không có job {job_id}",
            "job_id": job_id,
        }
    return job.to_dict()


@mcp.tool()
def video_get_evidence(
    cache_id: str,
    sections: list[str] | None = None,
    start_seconds: float | None = None,
    end_seconds: float | None = None,
) -> dict[str, Any]:
    """Đọc evidence đã phân tích; lọc theo section và khoảng thời gian (giây)."""
    path = cache.evidence_path(cache_id)
    if not path.exists():
        return {
            "error_code": "NOT_FOUND",
            "error": f"Không có cache {cache_id}",
            "cache_id": cache_id,
        }
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "error_code": "ERROR",
            "error": f"Đọc evidence thất bại: {exc}",
            "cache_id": cache_id,
        }

    entry = cache.entry_dir(cache_id)
    result = dict(evidence)
    for frame in result.get("frames") or []:
        frame_path = frame.get("path")
        if frame_path and not os.path.isabs(frame_path):
            frame["path"] = str(entry / frame_path)

    if sections:
        keep = set(sections) | {"cache_id", "source_url", "analyzed_intervals"}
        result = {key: value for key, value in result.items() if key in keep}

    if start_seconds is not None or end_seconds is not None:
        low = 0.0 if start_seconds is None else float(start_seconds)
        high = float("inf") if end_seconds is None else float(end_seconds)
        result["frames"] = [
            frame
            for frame in result.get("frames") or []
            if low <= float(frame.get("timestamp", 0.0)) <= high
        ]
        transcript = result.get("transcript") or {}
        if transcript:
            segments = [
                segment
                for segment in transcript.get("segments") or []
                if float(segment.get("end", 0.0)) >= low
                and float(segment.get("start", 0.0)) <= high
            ]
            result["transcript"] = {
                "segment_count": len(segments),
                "text": " ".join(segment.get("text", "") for segment in segments),
                "segments": segments,
            }
        result["window"] = {
            "start_seconds": low,
            "end_seconds": None if high == float("inf") else high,
        }
    return result


@mcp.tool()
def video_cache_info(cache_id: str | None = None) -> dict[str, Any]:
    """Thông tin cache: một entry cụ thể hoặc toàn bộ cache."""
    return cache.cache_info(cache_id)


@mcp.tool()
def video_cache_cleanup(max_age_hours: float = 24) -> dict[str, Any]:
    """Xóa các cache cũ hơn max_age_hours; trả về danh sách đã xóa."""
    return cache.cleanup(max_age_hours)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
