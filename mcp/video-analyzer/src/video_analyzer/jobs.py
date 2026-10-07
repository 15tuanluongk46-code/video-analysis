"""Hàng đợi job phân tích video: một worker, trạng thái lưu vào cache."""
from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path

from . import cache
from .acquisition import acquire
from .analysis.frames import contact_sheets, sample_frames
from .analysis.media import MediaError, extract_audio, probe
from .analysis.transcript import transcribe
from .analysis.vision import VisionUnavailable, describe_contact_sheets
from .models import DEFAULT_REPORT_SECTIONS, ErrorCode, Job, JobStatus
from .security import SecurityError, validate_url

PROGRESS = {
    "queued": 0.0,
    "acquire": 5.0,
    "probe": 20.0,
    "sample": 35.0,
    "transcribe": 55.0,
    "vision": 75.0,
    "package": 90.0,
    "completed": 100.0,
}


class JobManager:
    """Quản lý job phân tích: submit → hàng đợi → một worker chạy tuần tự."""

    def __init__(self, *, auto_start: bool = True):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._worker: threading.Thread | None = None
        if auto_start:
            self.start()

    def start(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(
            target=self._worker_loop, name="video-analyzer-worker", daemon=True
        )
        self._worker.start()

    def submit(
        self,
        url: str,
        *,
        resolved_media_url: str | None = None,
        profile: str = "balanced",
        max_duration_seconds: float = 600,
    ) -> Job:
        now = time.time()
        job = Job(
            job_id=uuid.uuid4().hex,
            url=url,
            resolved_media_url=resolved_media_url,
            profile=profile,
            max_duration_seconds=max_duration_seconds,
            created_at=now,
            updated_at=now,
        )
        job.cache_id = cache.cache_id_for(url, resolved_media_url)
        with self._lock:
            self._jobs[job.job_id] = job
        self._queue.put(job.job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def _worker_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                job = self.get(job_id)
                if job is not None:
                    self.run_sync(job)
            finally:
                self._queue.task_done()

    def _set_phase(self, job: Job, phase: str, *, status: JobStatus | None = None) -> None:
        job.phase = phase
        job.progress = PROGRESS.get(phase, job.progress)
        job.updated_at = time.time()
        if status is not None:
            job.status = status
        elif job.status == JobStatus.QUEUED:
            job.status = JobStatus.RUNNING

    def _fail(self, job: Job, code: str, message: str) -> Job:
        job.status = JobStatus.FAILED
        job.error_code = code
        job.error = message
        job.updated_at = time.time()
        return job

    def run_sync(self, job: Job) -> Job:
        """Chạy trọn pipeline cho một job (dùng cho cả worker lẫn test)."""
        try:
            validate_url(job.url)
        except SecurityError as exc:
            return self._fail(job, exc.code, exc.message)

        cache_id = job.cache_id or cache.cache_id_for(job.url, job.resolved_media_url)
        job.cache_id = cache_id

        if cache.get_fresh(cache_id, cache.TTL_HOURS) is not None:
            self._set_phase(job, "completed", status=JobStatus.COMPLETED)
            return job

        cache.enforce_limits(cache.MAX_BYTES, cache.TTL_HOURS)
        entry = cache.entry_dir(cache_id)
        entry.mkdir(parents=True, exist_ok=True)
        manifest = cache.create_entry(cache_id, job.url, job.resolved_media_url)

        try:
            self._set_phase(job, "acquire")
            target = job.resolved_media_url or job.url
            info = acquire(target, entry)
            manifest["source_path"] = os.path.relpath(str(info["path"]), entry)
            cache.save_manifest(cache_id, manifest)

            self._set_phase(job, "probe")
            try:
                media = probe(info["path"])
            except MediaError as exc:
                raise SecurityError(ErrorCode.DOWNLOAD_FAILED, f"ffprobe thất bại: {exc}")
            if media.duration > job.max_duration_seconds:
                raise SecurityError(
                    ErrorCode.DURATION_LIMITED,
                    f"Video dài {media.duration:.0f}s vượt giới hạn "
                    f"{job.max_duration_seconds:.0f}s",
                )
            manifest["media"] = media.to_dict()
            cache.save_manifest(cache_id, manifest)

            self._set_phase(job, "sample")
            frames = sample_frames(
                info["path"],
                entry / "frames",
                duration=media.duration,
                profile=job.profile,
            )
            sheets = contact_sheets(frames, entry / "contact-sheets")
            manifest["frames"] = [
                {
                    "index": frame.index,
                    "timestamp": frame.timestamp,
                    "path": os.path.relpath(str(frame.path), entry),
                    "scene_score": frame.scene_score,
                }
                for frame in frames
            ]
            manifest["contact_sheets"] = [
                os.path.relpath(str(sheet), entry) for sheet in sheets
            ]
            cache.save_manifest(cache_id, manifest)

            self._set_phase(job, "transcribe")
            segments = []
            if media.has_audio:
                try:
                    audio = extract_audio(info["path"], entry / "audio" / "audio.wav")
                    segments = transcribe(audio)
                    transcript_file = entry / "transcript.json"
                    transcript_file.write_text(
                        json.dumps(
                            [segment.to_dict() for segment in segments],
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    manifest["transcript_file"] = os.path.relpath(
                        str(transcript_file), entry
                    )
                except SecurityError as exc:
                    manifest["errors"].append(
                        {"phase": "transcribe", "code": exc.code, "message": exc.message}
                    )
            else:
                manifest["errors"].append(
                    {
                        "phase": "transcribe",
                        "code": ErrorCode.NO_AUDIO,
                        "message": "Video không có audio",
                    }
                )
            cache.save_manifest(cache_id, manifest)

            self._set_phase(job, "vision")
            try:
                vision_text = describe_contact_sheets(sheets, frames=frames)
                manifest["vision"] = {"available": True, "text": vision_text}
            except VisionUnavailable as exc:
                manifest["vision"] = {"available": False, "reason": exc.message}
                manifest["errors"].append(
                    {"phase": "vision", "code": exc.code, "message": exc.message}
                )
            cache.save_manifest(cache_id, manifest)

            self._set_phase(job, "package")
            evidence = {
                "cache_id": cache_id,
                "source_url": job.url,
                "resolved_media_url": job.resolved_media_url,
                "analyzed_at": time.time(),
                "media": media.to_dict(),
                "analyzed_intervals": [[0.0, media.duration]],
                "frames": manifest["frames"],
                "contact_sheets": manifest["contact_sheets"],
                "transcript": {
                    "segment_count": len(segments),
                    "speech_seconds": round(
                        sum(segment.end - segment.start for segment in segments), 2
                    ),
                    "text": " ".join(segment.text for segment in segments),
                    "segments": [segment.to_dict() for segment in segments],
                },
                "vision": manifest["vision"],
                "errors": manifest["errors"],
                "report_sections": list(DEFAULT_REPORT_SECTIONS),
            }
            cache.evidence_path(cache_id).write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            manifest["status"] = "completed"
            manifest["analyzed_intervals"] = evidence["analyzed_intervals"]
            cache.save_manifest(cache_id, manifest)

            self._set_phase(job, "completed", status=JobStatus.COMPLETED)
            return job
        except SecurityError as exc:
            manifest["status"] = "failed"
            manifest["errors"].append(
                {"phase": job.phase, "code": exc.code, "message": exc.message}
            )
            cache.save_manifest(cache_id, manifest)
            return self._fail(job, exc.code, exc.message)
        except Exception as exc:
            manifest["status"] = "failed"
            manifest["errors"].append(
                {"phase": job.phase, "code": ErrorCode.INTERRUPTED, "message": str(exc)}
            )
            cache.save_manifest(cache_id, manifest)
            return self._fail(job, ErrorCode.INTERRUPTED, str(exc))
