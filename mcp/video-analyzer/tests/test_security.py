import httpx
import pytest

from video_analyzer import security
from video_analyzer.models import ErrorCode


def test_rejects_non_http_schemes():
    for url in ("file:///etc/passwd", "ftp://example.com/a.mp4", "data:text/plain,hi"):
        with pytest.raises(security.SecurityError) as exc:
            security.validate_url(url)
        assert exc.value.code == ErrorCode.UNSUPPORTED_URL


def test_rejects_private_hosts():
    for url in (
        "http://localhost/a.mp4",
        "http://127.0.0.1/a.mp4",
        "http://10.1.2.3/a.mp4",
        "http://192.168.1.1/a.mp4",
        "http://172.16.0.9/a.mp4",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/a.mp4",
    ):
        with pytest.raises(security.SecurityError):
            security.validate_url(url)


def test_accepts_public_urls():
    assert security.validate_url("https://video.twimg.com/a/b.mp4") == "https://video.twimg.com/a/b.mp4"
    assert security.is_public_host("8.8.8.8")
    assert not security.is_public_host("192.168.0.1")


def test_open_stream_validates_redirect_hops():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "public.example":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        return httpx.Response(200, content=b"ok")

    transport = httpx.MockTransport(handler)
    with pytest.raises(security.SecurityError):
        with security.open_stream("https://public.example/a.mp4", transport=transport):
            pass


def test_open_stream_follows_safe_redirect():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(301, headers={"location": "https://cdn.example/real.mp4"})
        return httpx.Response(200, content=b"hello")

    transport = httpx.MockTransport(handler)
    with security.open_stream("https://cdn.example/start", transport=transport) as (resp, final_url):
        assert final_url == "https://cdn.example/real.mp4"
        assert resp.read() == b"hello"


def test_download_to_enforces_max_bytes(tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 100))
    dest = tmp_path / "media.bin"
    with pytest.raises(security.SecurityError) as exc:
        security.download_to(
            "https://cdn.example/big.mp4", dest, max_bytes=10, transport=transport
        )
    assert exc.value.code == ErrorCode.MEDIA_TOO_LARGE
    assert not dest.exists()


def test_download_to_writes_file(tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"abc"))
    dest = tmp_path / "media.bin"
    final_url, size = security.download_to(
        "https://cdn.example/v.mp4", dest, max_bytes=100, transport=transport
    )
    assert size == 3
    assert dest.read_bytes() == b"abc"
    assert final_url == "https://cdn.example/v.mp4"
