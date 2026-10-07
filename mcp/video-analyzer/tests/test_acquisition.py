from pathlib import Path

import httpx
import pytest
from yt_dlp.utils import DownloadError

from video_analyzer import acquisition
from video_analyzer.models import ErrorCode
from video_analyzer.security import SecurityError


def _transport(body: bytes, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers={"content-type": "video/mp4"})

    return httpx.MockTransport(handler)


def test_guess_media_kind():
    assert acquisition.guess_media_kind("https://a.com/v.mp4?tag=1") == "video"
    assert acquisition.guess_media_kind("https://a.com/master.m3u8?x=1") == "hls"
    assert acquisition.guess_media_kind("https://a.com/page/123") == "unknown"


def test_direct_download(tmp_path: Path):
    result = acquisition.acquire(
        "https://cdn.example.com/video.mp4",
        tmp_path,
        transport=_transport(b"x" * 2048),
    )
    assert result["method"] == "direct"
    assert result["size_bytes"] == 2048
    assert result["path"].exists()
    assert result["path"].stat().st_size == 2048


def test_direct_403_falls_back_to_ytdlp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def fake_ytdlp(url, dest_dir, *, max_bytes):
        dest = Path(dest_dir) / "source.mp4"
        dest.write_bytes(b"y" * 512)
        return dest

    monkeypatch.setattr(acquisition, "_ytdlp_download", fake_ytdlp)
    result = acquisition.acquire(
        "https://cdn.example.com/video.mp4",
        tmp_path,
        transport=_transport(b"denied", status=403),
    )
    assert result["method"] == "yt-dlp"
    assert result["path"].exists()


def test_ytdlp_needs_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def fake_ytdlp(url, dest_dir, *, max_bytes):
        raise DownloadError("Sign in to confirm you're not a bot")

    monkeypatch.setattr(acquisition, "_ytdlp_download", fake_ytdlp)
    with pytest.raises(SecurityError) as excinfo:
        acquisition.acquire("https://x.com/user/status/123", tmp_path)
    assert excinfo.value.code == ErrorCode.NEEDS_BROWSER


def test_ytdlp_drm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def fake_ytdlp(url, dest_dir, *, max_bytes):
        raise DownloadError("This video is DRM protected")

    monkeypatch.setattr(acquisition, "_ytdlp_download", fake_ytdlp)
    with pytest.raises(SecurityError) as excinfo:
        acquisition.acquire("https://x.com/user/status/123", tmp_path)
    assert excinfo.value.code == ErrorCode.DRM_OR_ENCRYPTED


def test_unknown_url_uses_ytdlp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def fake_ytdlp(url, dest_dir, *, max_bytes):
        dest = Path(dest_dir) / "source.mp4"
        dest.write_bytes(b"z" * 256)
        return dest

    monkeypatch.setattr(acquisition, "_ytdlp_download", fake_ytdlp)
    result = acquisition.acquire("https://example.com/watch/123", tmp_path)
    assert result["method"] == "yt-dlp"


def test_hls_uses_ytdlp_not_direct(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def exploding_transport() -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("không được tải trực tiếp HLS")

        return httpx.MockTransport(handler)

    def fake_ytdlp(url, dest_dir, *, max_bytes):
        dest = Path(dest_dir) / "source.mp4"
        dest.write_bytes(b"h" * 128)
        return dest

    monkeypatch.setattr(acquisition, "_ytdlp_download", fake_ytdlp)
    result = acquisition.acquire(
        "https://video.twimg.com/amplify_video/1/pl/x.m3u8?tag=29",
        tmp_path,
        transport=exploding_transport(),
    )
    assert result["method"] == "yt-dlp"


def test_media_too_large(tmp_path: Path):
    with pytest.raises(SecurityError) as excinfo:
        acquisition.acquire(
            "https://cdn.example.com/video.mp4",
            tmp_path,
            max_bytes=100,
            transport=_transport(b"x" * 500),
        )
    assert excinfo.value.code == ErrorCode.MEDIA_TOO_LARGE
    assert not (tmp_path / "source.mp4").exists()
