"""Tests for vision.py (Ollama wrapper)."""
from __future__ import annotations

import json

import httpx
import pytest

from video_analyzer.analysis import vision as vision_mod
from video_analyzer.models import ErrorCode


def _img(tmp_path, name="frame.jpg"):
    path = tmp_path / name
    path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")
    return path


def test_describe_images_success(tmp_path):
    img = _img(tmp_path)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "  Có một con mèo  "}})

    text = vision_mod.describe_images(
        [img], prompt="mô tả", transport=httpx.MockTransport(handler)
    )

    assert text == "Có một con mèo"
    assert seen["url"].endswith("/api/chat")
    assert seen["payload"]["model"] == vision_mod.DEFAULT_MODEL
    assert seen["payload"]["stream"] is False
    assert len(seen["payload"]["messages"][0]["images"]) == 1


def test_describe_images_connection_error(tmp_path):
    img = _img(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(vision_mod.VisionUnavailable) as exc:
        vision_mod.describe_images([img], transport=httpx.MockTransport(handler))
    assert exc.value.code == ErrorCode.VISION_UNAVAILABLE


def test_describe_images_empty_response(tmp_path):
    img = _img(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "   "}})

    with pytest.raises(vision_mod.VisionUnavailable):
        vision_mod.describe_images([img], transport=httpx.MockTransport(handler))


def test_describe_images_missing_file(tmp_path):
    with pytest.raises(vision_mod.VisionUnavailable):
        vision_mod.describe_images([tmp_path / "nope.jpg"])


def test_describe_images_no_input():
    with pytest.raises(vision_mod.VisionUnavailable):
        vision_mod.describe_images([])


def test_describe_contact_sheets_includes_timestamps(tmp_path):
    sheet = _img(tmp_path, "contact_00.jpg")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    class _Frame:
        def __init__(self, index, timestamp):
            self.index = index
            self.timestamp = timestamp

    text = vision_mod.describe_contact_sheets(
        [sheet],
        frames=[_Frame(0, 0.0), _Frame(1, 1.25)],
        transport=httpx.MockTransport(handler),
    )

    assert text == "ok"
    prompt = seen["payload"]["messages"][0]["content"]
    assert "Khung 0: 0.00s" in prompt
    assert "Khung 1: 1.25s" in prompt


def test_describe_images_sends_num_ctx(tmp_path):
    img = _img(tmp_path)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    vision_mod.describe_images([img], transport=httpx.MockTransport(handler))

    assert seen["payload"]["options"]["num_ctx"] == vision_mod.DEFAULT_NUM_CTX
    assert seen["payload"]["keep_alive"] == "5m"


def test_describe_images_surfaces_http_error_body(tmp_path):
    img = _img(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="model khong ho tro anh")

    with pytest.raises(vision_mod.VisionUnavailable) as exc:
        vision_mod.describe_images([img], transport=httpx.MockTransport(handler))
    message = str(exc.value)
    assert "HTTP 400" in message
    assert "model khong ho tro anh" in message


def test_describe_images_splits_on_context_error(tmp_path):
    first = _img(tmp_path, "a.jpg")
    second = _img(tmp_path, "b.jpg")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        images = json.loads(request.content)["messages"][0]["images"]
        calls.append(len(images))
        if len(images) > 1:
            body = (
                '{"error":"request (7492 tokens) exceeds the available context '
                'size (4096 tokens), try increasing it"}'
            )
            return httpx.Response(400, text=body)
        return httpx.Response(200, json={"message": {"content": f"ok-{len(images)}"}})

    text = vision_mod.describe_images(
        [first, second], transport=httpx.MockTransport(handler)
    )

    assert calls == [2, 1, 1]
    assert text == "ok-1\n\nok-1"


def test_ollama_available_false_on_error(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(vision_mod.httpx, "get", boom)
    assert vision_mod.ollama_available() is False


def test_ollama_available_true(monkeypatch):
    monkeypatch.setattr(
        vision_mod.httpx, "get", lambda *a, **k: httpx.Response(200, json={})
    )
    assert vision_mod.ollama_available() is True
