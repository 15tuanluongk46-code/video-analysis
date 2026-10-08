# Nguồn gốc và license

Ngày đóng gói: 2026-10-08 (ngày môi trường phiên).

Nguồn được người dùng chỉ định bàn giao:
- `/home/sss/.agents/skills/video-analysis`: SKILL.md, scripts/resolve_media.py, scripts/ocr_timeline.py.
- `/home/sss/AI-Home/mcp/video-analyzer`: pyproject.toml, uv.lock, src/**/*.py, tests/**/*.py.
- `/home/sss/AI-Home/docs/superpowers/specs/2026-09-21-video-analyzer-design.md`.
- `/home/sss/AI-Home/docs/superpowers/plans/2026-09-21-video-analyzer-implementation.md`.

Không tìm thấy Git repository ở AI-Home tại thời điểm kiểm tra: không gán commit SHA giả.
MANIFEST.sha256 xác định chính xác bytes bàn giao. Source Python/skill/lockfile được copy nguyên byte;
README/SETUP/AGENTS/examples/VERIFICATION là tài liệu bổ sung của gói, không sửa bản cài gốc.
Tài liệu reference là lịch sử và có thể lệch code hiện hành; README/SETUP chỉ rõ các khác biệt đã phát hiện.

Đợt portability 2026-10-08 sửa bản skill trong checkout (không sửa skill cài trên máy):
làm rõ duration limit, transcript rỗng và OCR/Ollama, bỏ giả định máy đích có phiên Chrome sẵn.
Đợt này cũng sửa fallback FFmpeg/ffprobe thành home người dùng hiện tại, bỏ venv máy tác giả
trong resolver và thêm regression tests. Source/skill được sửa không còn byte-identical với
snapshot ban đầu; dependency manifest và lockfile giữ nguyên. Các lệnh/path trong reference/
là lịch sử, không phải hướng dẫn cài hiện hành.

Không thấy LICENSE/COPYING/NOTICE riêng trong hai package, pyproject không khai báo license.
Không khẳng định gói là MIT/Apache. Đây là bàn giao private theo yêu cầu chủ máy, không phải cấp quyền
công bố hay bán lại. Dependency Python được lấy theo uv.lock từ upstream khi cài; license của từng
dependency vẫn áp dụng. Không nhúng dependency binaries, model weights hay thư viện vendor.

Nguồn tham khảo trong skill: bài "Make your product videos look expensive (Apple Framework)"
của leo (@leomeethewoo), URL được giữ trong SKILL.md; không bao gồm bản sao video/bài viết.
