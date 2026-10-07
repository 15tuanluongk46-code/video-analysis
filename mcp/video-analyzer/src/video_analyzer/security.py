"""URL validation and SSRF guards."""
from __future__ import annotations

import ipaddress
import socket
from contextlib import contextmanager
from pathlib import Path

import httpx

from .models import ErrorCode

ALLOWED_SCHEMES = ("http", "https")
REDIRECT_CODES = (301, 302, 303, 307, 308)
MAX_REDIRECTS = 5
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


class SecurityError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return not ip.is_global


def is_public_host(host: str) -> bool:
    if not host:
        return False
    host = host.strip("[]")
    try:
        ip = ipaddress.ip_address(host)
        return not _blocked_ip(ip)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _blocked_ip(ip):
            return False
    return True


def validate_url(url: str) -> str:
    if not url or not isinstance(url, str):
        raise SecurityError(ErrorCode.UNSUPPORTED_URL, "URL trống hoặc không hợp lệ")
    try:
        parsed = httpx.URL(url)
    except Exception as exc:
        raise SecurityError(ErrorCode.UNSUPPORTED_URL, f"URL không parse được: {exc}") from exc
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise SecurityError(
            ErrorCode.UNSUPPORTED_URL, f"Chỉ hỗ trợ http/https, nhận được: {parsed.scheme!r}"
        )
    host = parsed.host
    if not host:
        raise SecurityError(ErrorCode.UNSUPPORTED_URL, "URL thiếu host")
    if not is_public_host(host):
        raise SecurityError(ErrorCode.UNSUPPORTED_URL, f"Host nội bộ bị chặn: {host}")
    return str(parsed)


@contextmanager
def open_stream(
    url: str,
    *,
    headers: dict | None = None,
    timeout: float = 30.0,
    max_redirects: int = MAX_REDIRECTS,
    transport: httpx.BaseTransport | None = None,
):
    validate_url(url)
    merged = {"User-Agent": USER_AGENT}
    if headers:
        merged.update(headers)
    client = httpx.Client(
        follow_redirects=False, timeout=timeout, headers=merged, transport=transport
    )
    resp = None
    try:
        current = url
        for _ in range(max_redirects + 1):
            request = client.build_request("GET", current)
            resp = client.send(request, stream=True)
            if resp.status_code in REDIRECT_CODES:
                location = resp.headers.get("location")
                resp.close()
                resp = None
                if not location:
                    raise SecurityError(
                        ErrorCode.DOWNLOAD_FAILED, "Redirect thiếu Location header"
                    )
                current = str(httpx.URL(current).join(location))
                validate_url(current)
                continue
            break
        else:
            raise SecurityError(ErrorCode.DOWNLOAD_FAILED, "Quá nhiều redirect")
        if resp is None:
            raise SecurityError(ErrorCode.DOWNLOAD_FAILED, "Không mở được kết nối")
        yield resp, current
    finally:
        if resp is not None:
            resp.close()
        client.close()


def download_to(
    url: str,
    dest: Path,
    *,
    max_bytes: int,
    headers: dict | None = None,
    timeout: float = 60.0,
    transport: httpx.BaseTransport | None = None,
    progress=None,
) -> tuple[str, int]:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open_stream(
        url, headers=headers, timeout=timeout, transport=transport
    ) as (resp, final_url):
        if resp.status_code >= 400:
            raise SecurityError(
                ErrorCode.ACCESS_DENIED,
                f"HTTP {resp.status_code} khi tải media: {final_url}",
            )
        with open(dest, "wb") as handle:
            for chunk in resp.iter_bytes(chunk_size=1 << 16):
                written += len(chunk)
                if written > max_bytes:
                    handle.close()
                    dest.unlink(missing_ok=True)
                    raise SecurityError(
                        ErrorCode.MEDIA_TOO_LARGE,
                        f"Media vượt giới hạn {max_bytes} bytes",
                    )
                handle.write(chunk)
                if progress is not None:
                    progress(written, resp.headers.get("content-length"))
    return final_url, written
