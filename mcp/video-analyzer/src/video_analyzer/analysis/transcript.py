"""Chuyển audio thành văn bản bằng faster-whisper (chạy local, không gửi ra ngoài)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from ..models import ErrorCode, TranscriptSegment
from ..security import SecurityError

DEFAULT_MODEL_SIZE = os.environ.get("VIDEO_ANALYZER_WHISPER_MODEL", "small")

MAX_WORD_GAP_SECONDS = 2.0
_MAX_NO_SPEECH = 0.6
_MIN_LOGPROB = -1.0

_model = None
_model_size: str | None = None


def _load_model(model_size: str):
    """Nạp và cache WhisperModel — chỉ import faster_whisper khi thực sự cần."""
    global _model, _model_size
    if _model is not None and _model_size == model_size:
        return _model
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise SecurityError(
            ErrorCode.TRANSCRIBE_FAILED,
            f"Không import được faster-whisper: {exc}",
        )
    try:
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    except Exception as exc:
        raise SecurityError(
            ErrorCode.TRANSCRIBE_FAILED,
            f"Không nạp được model whisper '{model_size}': {exc}",
        )
    _model_size = model_size
    return _model


def _segments_from_words(segment) -> list[tuple[float, float, str]]:
    """Tách một segment theo khoảng lặng giữa các từ — model hay gộp nhầm đoạn nhạc dài."""
    words = [w for w in (getattr(segment, "words", None) or []) if (w.word or "").strip()]
    if not words:
        return []
    groups: list[list] = [[words[0]]]
    for word in words[1:]:
        if float(word.start) - float(groups[-1][-1].end) > MAX_WORD_GAP_SECONDS:
            groups.append([word])
        else:
            groups[-1].append(word)
    pieces: list[tuple[float, float, str]] = []
    for group in groups:
        text = "".join(w.word for w in group).strip()
        if text:
            pieces.append((float(group[0].start), float(group[-1].end), text))
    return pieces


def transcribe(
    audio_path: str | Path,
    *,
    language: str | None = None,
    model_size: str | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> list[TranscriptSegment]:
    """Phiên âm file audio (WAV 16k mono) thành danh sách TranscriptSegment."""
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise SecurityError(
            ErrorCode.TRANSCRIBE_FAILED,
            f"Không thấy file audio: {audio_path}",
        )
    model = _load_model(model_size or DEFAULT_MODEL_SIZE)
    try:
        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            vad_filter=True,
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        total = float(getattr(info, "duration", 0.0) or 0.0)
        result: list[TranscriptSegment] = []
        for segment in segments:
            text = (segment.text or "").strip()
            if not text:
                continue
            if float(getattr(segment, "no_speech_prob", 0.0) or 0.0) > _MAX_NO_SPEECH:
                continue
            if float(getattr(segment, "avg_logprob", 0.0) or 0.0) < _MIN_LOGPROB:
                continue
            pieces = _segments_from_words(segment)
            if not pieces:
                pieces = [(float(segment.start), float(segment.end), text)]
            for start, end, piece_text in pieces:
                result.append(TranscriptSegment(start=start, end=end, text=piece_text))
            if on_progress is not None and total > 0:
                on_progress(min(float(segment.end) / total, 1.0))
        return result
    except SecurityError:
        raise
    except Exception as exc:
        raise SecurityError(ErrorCode.TRANSCRIBE_FAILED, f"Phiên âm thất bại: {exc}")
