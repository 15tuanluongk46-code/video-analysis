# Design: Video Analyzer MCP

Ngày: 2026-09-21
Trạng thái: Đã duyệt — đang triển khai

## Mục tiêu

Cho phép user gửi URL video kèm câu hỏi và nhận câu trả lời dựa trên nội dung thật của video (có timestamp).
Nếu chỉ có URL, không có câu hỏi → xuất báo cáo đầy đủ theo mục mặc định.
Hỏi tiếp trong 24h → tái sử dụng cache, không phân tích lại.
Nguyên tắc: không đoán nội dung thiếu — phải nói rõ phần nào không truy cập/phân tích được.

Ví dụ:
- `/video <URL> Video này đang quảng cáo tính năng gì?`
- `/video <URL> Viết lại prompt tạo video giống cảnh từ 00:25`
- `/video <URL> Tóm tắt lời thoại bằng tiếng Việt`
- `/video <URL> Phân tích kỹ thuật camera và chuyển cảnh`
- `/video <URL> Liệt kê toàn bộ chữ xuất hiện trên màn hình`

## Kiến trúc

```
User ──> OpenCode /video <URL> [câu hỏi]
           │
           ├─ skill video-analysis (điều phối mỏng)
           │
           ▼
   MCP server video-analyzer (FastMCP stdio)
     video_inspect ──> READY | CACHED | NEEDS_BROWSER | UNSUPPORTED | ERROR
     video_analyze ──> job_id + cache_id
     video_job_status(job_id)
     video_get_evidence(cache_id, sections?, start_seconds?, end_seconds?)
     video_cache_info(cache_id?)
     video_cache_cleanup(max_age_hours=24)
           │
           ▼
   Pipeline: URL → cache check → acquisition → ffprobe → audio + key frames
             → transcript + Vision/OCR → evidence manifest → trả lời
           │
           ▼
   Chrome AI (chỉ fallback khi NEEDS_BROWSER)
```

### Luồng acquisition

1. URL trực tiếp (mp4/m3u8) → tải bằng httpx/ffmpeg.
2. Trang web thường → yt-dlp (ưu tiên).
3. Trang cần phiên đăng nhập/JS → trả `NEEDS_BROWSER`; skill `/video` mở URL bằng chrome-live,
   đọc network/DOM, lấy CDN media URL rồi gọi lại `video_analyze(url, resolved_media_url=...)`.
   MCP KHÔNG tự quản lý browser, KHÔNG export cookie.

### Job phases

`queued → acquire → probe → sample → transcribe → vision → package → completed`
Lỗi từng phần vẫn trả evidence hợp lệ (ví dụ NO_AUDIO, VISION_UNAVAILABLE).

## Thành phần

| File | Trách nhiệm |
|---|---|
| `src/video_analyzer/server.py` | FastMCP server, 6 tool |
| `models.py` | Dataclass/schema: job, manifest, evidence |
| `security.py` | Validate URL, chặn SSRF, guard redirect |
| `acquisition.py` | Tải media (direct + yt-dlp), trả NEEDS_BROWSER |
| `cache.py` | Cache 24h, cap 5GB, LRU evict |
| `jobs.py` | Hàng đợi 1 worker, lưu trạng thái |
| `analysis/media.py` | ffprobe metadata |
| `analysis/frames.py` | Scene detection + equal sampling, contact sheet |
| `analysis/transcript.py` | faster-whisper |
| `analysis/vision.py` | Ollama qwen2.5vl:7b (mô tả frame + OCR) |

## Security & giới hạn

- Chỉ http/https; chặn localhost/loopback/private/link-local; kiểm tra lại sau redirect (SSRF).
- Một video, không playlist/thread. Không DRM/paywall bypass.
- Phân tích tối đa 10 phút; tải ≤750MB; cache ≤5GB; TTL 24h.
- Một job nặng chạy một lúc.
- Balanced profile: 12–24 key frames (scene detection + fallback equal sampling), tối đa 6 frame/contact sheet, resize trước Vision.
- Video >10 phút: tối đa 5 cửa sổ, tổng ≤600s, giữ offset transcript theo timeline gốc, manifest ghi rõ khoảng đã phân tích.
- MCP gọi Ollama trực tiếp (không gọi subagent theo từng frame).
- Ollama chết → transcript + metadata vẫn đầy đủ, visual đánh dấu `VISION_UNAVAILABLE`.
- Không có audio → `NO_AUDIO`, tiếp tục phân tích hình ảnh.

## Cache layout

```
~/.cache/opencode/video-analyzer/<cache-id>/
  manifest.json
  source.mp4
  audio/
  frames/
  contact-sheets/
  evidence.json
```

## Error codes

`UNSUPPORTED_URL`, `NEEDS_BROWSER`, `ACCESS_DENIED`, `DRM_OR_ENCRYPTED`, `DURATION_LIMITED`,
`MEDIA_TOO_LARGE`, `DOWNLOAD_FAILED`, `NO_AUDIO`, `TRANSCRIBE_FAILED`, `VISION_UNAVAILABLE`, `INTERRUPTED`

## Báo cáo mặc định (không có câu hỏi)

1. Tóm tắt
2. Timeline cảnh có timestamp
3. Nội dung lời nói
4. Text trên màn hình
5. Kỹ thuật hình ảnh/chuyển động
6. Chi tiết đáng chú ý
7. Phạm vi thực tế đã phân tích

## Kiểm thử

- Unit: security (SSRF), cache (TTL/LRU), frames (sampling), transcript (mock), evidence, server (mock pipeline).
- E2E: video X/Twitter của Dreamina (112.5s, 1080p, có audio) — qua direct mp4 + qua trang X.
