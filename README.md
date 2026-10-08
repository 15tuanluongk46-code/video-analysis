# Video Analysis — gói bàn giao đầy đủ mã nguồn

Repository riêng tư: https://github.com/15tuanluongk46-code/video-analysis
Chứa mã nguồn để clone và cập nhật; không chỉ là bản ZIP lưu trữ.

```bash
gh repo clone 15tuanluongk46-code/video-analysis
```

Chạy các lệnh trong SETUP.md từ thư mục `video-analysis` vừa clone.
Tài khoản GitHub dùng để clone cần có quyền truy cập repo Private.

Gói gồm skill `video-analysis`, hai helper OCR/resolve URL, MCP `video-analyzer`,
lockfile và toàn bộ tests. Đọc [SETUP.md](SETUP.md) để cài trên máy khác và
[VERIFICATION.md](VERIFICATION.md) để biết chính xác những gì đã được kiểm tra.

## Nội dung

- `skills/video-analysis/`: skill đã hiệu chỉnh giới hạn thực tế; helper không còn mượn venv máy tác giả. Không sửa bản cài trên máy nguồn.
- `mcp/video-analyzer/`: source Python, manifest, lockfile và tests; đã bổ sung regression tests cho đường dẫn portable.
- `reference/`: thiết kế và kế hoạch triển khai lịch sử; không phải bằng chứng tính năng hiện tại.
- `examples/mcp-stdio.json`: cấu hình stdio mẫu trung lập cho client dùng `mcpServers`.
- `AGENTS.md`: quy tắc vận hành an toàn, giới hạn thực tế ưu tiên hơn tài liệu cũ.
- `PROVENANCE.md`, `MANIFEST.sha256`: nguồn gốc, phạm vi license và checksum từng file.

Đây là **source bundle có hướng dẫn cài**, không phải bản chạy offline một-click.
Không kèm `.venv`, binaries, model weights, credentials, cookies, browser profile,
cache video, transcript riêng tư hoặc cấu hình tài khoản. Cần Internet để cài dependency/model.

## Giới hạn quan trọng

1. Mặc định video quá 600 giây bị từ chối (`DURATION_LIMITED`). Code chưa tự chia 5 cửa sổ;
   SKILL.md đã được sửa để khớp giới hạn này. Không hứa phân tích đoạn chưa chạy.
2. OCR là helper độc lập, chưa tự nối vào pipeline MCP. Transcript rỗng **không chứng minh**
   video không có lời: phải kiểm tra lỗi transcribe và metadata.
3. `vision` subagent và `chrome-ops` là tích hợp tùy chọn của host gốc, không phải phụ thuộc
   Python. Máy đích có thể dùng công cụ vision/browser tương đương; không tự cài hay đổi MCP flags.
4. Không bảo đảm tải được video private/DRM/paywall hoặc mọi URL social.
5. FFmpeg/ffprobe ưu tiên PATH, sau đó `~/.local/bin` của người dùng hiện tại.
   Resolver dùng yt-dlp trên PATH hoặc interpreter đang chạy, không mượn venv máy tác giả.
6. Không có license riêng được tìm thấy cho source nội bộ. Không tự gán MIT/Apache hoặc
   suy diễn quyền công bố/phân phối rộng. Gói này bàn giao riêng theo yêu cầu chủ máy.
