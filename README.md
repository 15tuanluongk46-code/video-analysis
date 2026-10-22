# Video Analysis — skill + MCP server phân tích video

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](mcp/video-analyzer/pyproject.toml)

Repository công khai: https://github.com/15tuanluongk46-code/video-analysis
Chứa mã nguồn để clone và cập nhật; không chỉ là bản ZIP lưu trữ.

```bash
git clone https://github.com/15tuanluongk46-code/video-analysis.git
# hoặc
gh repo clone 15tuanluongk46-code/video-analysis
```

Chạy các lệnh trong SETUP.md từ thư mục `video-analysis` vừa clone.
Repo công khai nên không cần quyền truy cập đặc biệt; chỉ cần Internet để clone và cài dependency.

Gói gồm skill `video-analysis`, hai helper OCR/resolve URL, MCP `video-analyzer`,
lockfile và toàn bộ tests. Đọc [SETUP.md](SETUP.md) để cài trên máy khác và
[VERIFICATION.md](VERIFICATION.md) để biết chính xác những gì đã được kiểm tra.

## Nội dung

- `skills/video-analysis/`: skill đã hiệu chỉnh giới hạn thực tế; helper không còn mượn venv máy tác giả. Không sửa bản cài trên máy nguồn.
- `mcp/video-analyzer/`: source Python, manifest, lockfile và tests; đã bổ sung regression tests cho đường dẫn portable.
- `reference/`: thiết kế và kế hoạch triển khai lịch sử; không phải bằng chứng tính năng hiện tại.
- `examples/mcp-stdio.json`: cấu hình stdio mẫu trung lập cho client dùng `mcpServers`.
- `AGENTS.md`: quy tắc vận hành an toàn, giới hạn thực tế ưu tiên hơn tài liệu cũ.
- `PROVENANCE.md`, `MANIFEST.sha256`: nguồn gốc, checksum từng file.
- `LICENSE`: giấy phép MIT.

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

## Giấy phép

Phát hành theo giấy phép [MIT](LICENSE) © 2026 15tuanluongk46-code.
Xem [PROVENANCE.md](PROVENANCE.md) cho lịch sử license của gói.

Dependency Python được cài từ upstream theo `uv.lock` và giữ license riêng của từng gói;
repo không nhúng dependency binaries, model weights hay thư viện vendor.
Bài viết tham khảo trong `skills/video-analysis/SKILL.md` ("Make your product videos look expensive
(Apple Framework)" của leo, [@leomeethewoo](https://www.instagram.com/leomeethewoo/)) chỉ giữ URL,
không kèm bản sao nội dung.

## Đóng góp

- Mở issue trước với thay đổi lớn hoặc thay đổi hành vi pipeline.
- Fork → tạo branch → chạy `uv sync --locked` và `pytest` theo [SETUP.md](SETUP.md) → mở pull request.
- Nêu rõ phần nào đã kiểm chứng thật (video thật, model thật) và phần nào chỉ là mock.
- Không commit `.venv`, cache, media, model weights hoặc credentials.
- Nếu sửa file có trong `MANIFEST.sha256`, cập nhật lại checksum tương ứng (không hash chính manifest).
