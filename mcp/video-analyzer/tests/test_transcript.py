"""Tests for transcript.py (faster-whisper wrapper)."""
from __future__ import annotations

import pytest

from video_analyzer.analysis import transcript as transcript_mod
from video_analyzer.models import ErrorCode
from video_analyzer.security import SecurityError


class _Word:
    def __init__(self, start: float, end: float, word: str):
        self.start = start
        self.end = end
        self.word = word


class _FakeSegment:
    def __init__(
        self,
        start: float,
        end: float,
        text: str,
        words=None,
        no_speech_prob: float = 0.0,
        avg_logprob: float = 0.0,
    ):
        self.start = start
        self.end = end
        self.text = text
        self.words = words
        self.no_speech_prob = no_speech_prob
        self.avg_logprob = avg_logprob


class _FakeInfo:
    duration = 2.0


class _FakeModel:
    def __init__(self, segments=None):
        self.calls = []
        self._segments = segments

    def transcribe(
        self,
        path,
        language=None,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=True,
    ):
        self.calls.append(
            {
                "path": path,
                "language": language,
                "vad_filter": vad_filter,
                "word_timestamps": word_timestamps,
                "condition_on_previous_text": condition_on_previous_text,
            }
        )
        segments = self._segments
        if segments is None:
            segments = [
                _FakeSegment(0.0, 1.0, " Xin chào "),
                _FakeSegment(1.0, 1.4, "   "),
                _FakeSegment(1.5, 2.0, "thế giới"),
            ]
        return segments, _FakeInfo()


def test_transcribe_maps_segments(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF0000")
    fake = _FakeModel()
    monkeypatch.setattr(transcript_mod, "_load_model", lambda size: fake)

    segments = transcript_mod.transcribe(audio)

    assert [(s.start, s.end, s.text) for s in segments] == [
        (0.0, 1.0, "Xin chào"),
        (1.5, 2.0, "thế giới"),
    ]
    assert fake.calls[0]["path"] == str(audio)
    assert fake.calls[0]["vad_filter"] is True
    assert fake.calls[0]["word_timestamps"] is True
    assert fake.calls[0]["condition_on_previous_text"] is False


def test_transcribe_reports_progress(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF0000")
    monkeypatch.setattr(transcript_mod, "_load_model", lambda size: _FakeModel())
    seen: list[float] = []

    transcript_mod.transcribe(audio, on_progress=seen.append)

    assert seen == [0.5, 1.0]


def test_transcribe_missing_file(tmp_path):
    with pytest.raises(SecurityError) as exc:
        transcript_mod.transcribe(tmp_path / "nope.wav")
    assert exc.value.code == ErrorCode.TRANSCRIBE_FAILED


def test_transcribe_model_load_failure(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF0000")

    def boom(size):
        raise SecurityError(ErrorCode.TRANSCRIBE_FAILED, "no model")

    monkeypatch.setattr(transcript_mod, "_load_model", boom)
    with pytest.raises(SecurityError) as exc:
        transcript_mod.transcribe(audio)
    assert exc.value.code == ErrorCode.TRANSCRIBE_FAILED


def test_transcribe_engine_failure(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF0000")

    class _Broken:
        def transcribe(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(transcript_mod, "_load_model", lambda size: _Broken())
    with pytest.raises(SecurityError) as exc:
        transcript_mod.transcribe(audio)
    assert exc.value.code == ErrorCode.TRANSCRIBE_FAILED


def test_transcribe_splits_segments_on_word_gap(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF0000")
    words = [
        _Word(11.31, 11.75, " Good"),
        _Word(11.75, 11.95, " news"),
        _Word(11.95, 12.65, " don't"),
        _Word(101.36, 101.50, " tell"),
        _Word(101.50, 101.76, " everyone"),
    ]
    fake = _FakeModel(
        [
            _FakeSegment(
                11.31,
                101.76,
                " Good news don't tell everyone",
                words=words,
                avg_logprob=-0.25,
                no_speech_prob=0.05,
            )
        ]
    )
    monkeypatch.setattr(transcript_mod, "_load_model", lambda size: fake)

    segments = transcript_mod.transcribe(audio)

    assert [(s.start, s.end, s.text) for s in segments] == [
        (11.31, 12.65, "Good news don't"),
        (101.36, 101.76, "tell everyone"),
    ]


def test_transcribe_drops_unreliable_segments(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF0000")
    fake = _FakeModel(
        [
            _FakeSegment(0.0, 2.0, " Haha", no_speech_prob=0.65),
            _FakeSegment(2.0, 4.0, " something", avg_logprob=-1.5),
            _FakeSegment(4.0, 5.0, " real speech"),
        ]
    )
    monkeypatch.setattr(transcript_mod, "_load_model", lambda size: fake)

    segments = transcript_mod.transcribe(audio)

    assert [(s.start, s.end, s.text) for s in segments] == [(4.0, 5.0, "real speech")]


def test_transcribe_keeps_segment_without_words(tmp_path, monkeypatch):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF0000")
    fake = _FakeModel([_FakeSegment(3.0, 4.5, " no words here")])
    monkeypatch.setattr(transcript_mod, "_load_model", lambda size: fake)

    segments = transcript_mod.transcribe(audio)

    assert [(s.start, s.end, s.text) for s in segments] == [(3.0, 4.5, "no words here")]
