# Plan: Video Analyzer MCP — triển khai

Ngày: 2026-09-21
Spec: `docs/superpowers/specs/2026-09-21-video-analyzer-design.md`

## Thứ tự TDD

1. **Scaffold + data contracts**: `pyproject.toml`, `uv sync`, `models.py` + schema tests.
2. **security.py**: validate scheme, chặn private IP, guard redirect + tests.
3. **cache.py**: TTL 24h, cap 5GB, evict expired → oldest + tests.
4. **acquisition.py**: direct media (httpx, theo dõi redirect) → yt-dlp → NEEDS_BROWSER + tests.
5. **analysis/media.py + frames.py**: ffprobe; scene detection + equal-sampling fallback; contact sheet + tests.
6. **analysis/transcript.py + vision.py**: faster-whisper (singleton), Ollama chat với ảnh + tests (mock).
7. **jobs.py**: 1 worker, phase transitions, persistence + tests.
8. **server.py**: 6 tool + tests (mock pipeline).
9. **Tích hợp OpenCode**: `opencode.jsonc`, `command/video.md`, `skills/video-analysis/SKILL.md`, `AGENTS.md`.
10. **E2E**: video Dreamina X (direct mp4 + trang X qua chrome-live fallback).
11. **Full test suite + verify** (uv run pytest).

## Lệnh

```bash
cd /home/sss/AI-Home/mcp/video-analyzer
uv sync
uv run pytest -q
```

## Điểm quyết định đã chốt

- Python riêng qua uv (không dùng chung opencode_env) → MCP command trỏ `.venv/bin/python`.
- ffmpeg/ffprobe: `shutil.which` + fallback `/home/sss/.local/bin`.
- Ollama: `http://localhost:11434/api/chat`, model `qwen2.5vl:7b`, `format=json`.
- Whisper: model `small`, chạy local, singleton.
- Job chạy nền trong process MCP (thread), client poll `video_job_status`.
