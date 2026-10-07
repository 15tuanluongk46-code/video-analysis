"""Phân tích hình ảnh bằng Ollama vision (qwen2.5vl) chạy local."""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Iterable

import httpx

from ..models import ErrorCode
from ..security import SecurityError

OLLAMA_URL = os.environ.get("VIDEO_ANALYZER_OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("VIDEO_ANALYZER_VISION_MODEL", "qwen2.5vl:7b")
DEFAULT_NUM_CTX = int(os.environ.get("VIDEO_ANALYZER_VISION_NUM_CTX", "8192"))

DEFAULT_PROMPT = (
    "Đây là các contact sheet trích từ một video; mỗi khung có nhãn số thứ tự và "
    "mốc thời gian (giây). Hãy mô tả ngắn gọn theo từng khung: bối cảnh, chủ thể, "
    "hành động, chữ xuất hiện trên màn hình, và đặc điểm kỹ thuật hình ảnh (góc máy, "
    "chuyển động, ánh sáng, màu sắc). Trả lời bằng tiếng Việt, kèm mốc thời gian."
)


class VisionUnavailable(SecurityError):
    """Ollama vision không dùng được (tắt, thiếu model, lỗi mạng...)."""

    def __init__(self, message: str):
        super().__init__(ErrorCode.VISION_UNAVAILABLE, message)


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def ollama_available(*, timeout: float = 5.0) -> bool:
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def _message_of(exc: BaseException) -> str:
    return getattr(exc, "message", None) or str(exc)


def _chat(
    images: list[str],
    content: str,
    *,
    model: str | None,
    timeout: float,
    transport: httpx.BaseTransport | None,
) -> str:
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [{"role": "user", "content": content, "images": images}],
        "stream": False,
        "keep_alive": "5m",
        "options": {"num_ctx": DEFAULT_NUM_CTX},
    }
    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            resp = client.post(f"{OLLAMA_URL}/api/chat", json=payload)
    except Exception as exc:
        raise VisionUnavailable(f"Ollama vision thất bại: {exc}")
    if resp.status_code >= 400:
        raise VisionUnavailable(
            f"Ollama vision HTTP {resp.status_code}: {resp.text[:300]}"
        )
    try:
        data = resp.json()
    except Exception as exc:
        raise VisionUnavailable(f"Ollama trả về JSON không hợp lệ: {exc}")
    text = ((data.get("message") or {}).get("content") or "").strip()
    if not text:
        raise VisionUnavailable("Ollama trả về nội dung rỗng")
    return text


def _is_context_error(exc: VisionUnavailable) -> bool:
    message = _message_of(exc).lower()
    return "exceeds" in message and "context" in message


def _describe_chunk(
    images: list[str],
    content: str,
    *,
    model: str | None,
    timeout: float,
    transport: httpx.BaseTransport | None,
) -> str:
    try:
        return _chat(images, content, model=model, timeout=timeout, transport=transport)
    except VisionUnavailable as exc:
        if len(images) > 1 and _is_context_error(exc):
            mid = len(images) // 2
            head = _describe_chunk(
                images[:mid], content, model=model, timeout=timeout, transport=transport
            )
            tail = _describe_chunk(
                images[mid:], content, model=model, timeout=timeout, transport=transport
            )
            return f"{head}\n\n{tail}"
        raise


def describe_images(
    image_paths: Iterable[str | Path],
    *,
    prompt: str | None = None,
    model: str | None = None,
    timeout: float = 300.0,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Gửi một loạt ảnh cho Ollama vision, trả về mô tả dạng text.

    Tự tách nhỏ danh sách ảnh khi vượt context của Ollama.
    """
    paths = [Path(p) for p in image_paths]
    if not paths:
        raise VisionUnavailable("Không có ảnh để phân tích")
    images: list[str] = []
    for path in paths:
        if not path.exists():
            raise VisionUnavailable(f"Không thấy ảnh: {path}")
        images.append(_b64(path))
    return _describe_chunk(
        images,
        prompt or DEFAULT_PROMPT,
        model=model,
        timeout=timeout,
        transport=transport,
    )


def describe_contact_sheets(
    sheets: Iterable[str | Path],
    *,
    frames: Iterable | None = None,
    prompt: str | None = None,
    timeout: float = 300.0,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Mô tả các contact sheet, kèm danh sách mốc thời gian của frame nếu có."""
    base_prompt = prompt or DEFAULT_PROMPT
    if frames:
        lines = [
            f"- Khung {frame.index}: {frame.timestamp:.2f}s"
            for frame in list(frames)[:24]
        ]
        base_prompt = f"{base_prompt}\n\nDanh sách khung tham chiếu:\n" + "\n".join(lines)
    return describe_images(sheets, prompt=base_prompt, timeout=timeout, transport=transport)
