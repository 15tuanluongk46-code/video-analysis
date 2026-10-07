"""Data contracts for video-analyzer."""
from __future__ import annotations

from dataclasses import asdict, dataclass


class ErrorCode:
    UNSUPPORTED_URL = "UNSUPPORTED_URL"
    NEEDS_BROWSER = "NEEDS_BROWSER"
    ACCESS_DENIED = "ACCESS_DENIED"
    DRM_OR_ENCRYPTED = "DRM_OR_ENCRYPTED"
    DURATION_LIMITED = "DURATION_LIMITED"
    MEDIA_TOO_LARGE = "MEDIA_TOO_LARGE"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    NO_AUDIO = "NO_AUDIO"
    TRANSCRIBE_FAILED = "TRANSCRIBE_FAILED"
    VISION_UNAVAILABLE = "VISION_UNAVAILABLE"
    INTERRUPTED = "INTERRUPTED"


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


PHASES = (
    "queued",
    "acquire",
    "probe",
    "sample",
    "transcribe",
    "vision",
    "package",
    "completed",
)

DEFAULT_REPORT_SECTIONS = (
    "summary",
    "timeline",
    "speech",
    "on_screen_text",
    "cinematography",
    "notable_details",
    "coverage",
)


@dataclass
class MediaInfo:
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    video_codec: str = ""
    audio_codec: str = ""
    size_bytes: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MediaInfo":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class FrameInfo:
    index: int
    timestamp: float
    path: str
    scene_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FrameInfo":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptSegment":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Job:
    job_id: str
    url: str
    resolved_media_url: str | None = None
    profile: str = "balanced"
    max_duration_seconds: int = 600
    status: str = JobStatus.QUEUED
    phase: str = "queued"
    progress: float = 0.0
    cache_id: str | None = None
    error: str | None = None
    error_code: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
