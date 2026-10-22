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

Không thấy LICENSE/COPYING/NOTICE riêng trong hai package lúc đóng gói; pyproject khi đó không khai báo license.
Gói ban đầu được bàn giao private, không kèm cấp quyền công bố hay bán lại.

Ngày 2026-10-22 chủ sở hữu quyết định phát hành gói này như mã nguồn mở theo giấy phép **MIT**
(xem `LICENSE`, giữ nguyên thông báo copyright). Quyết định này áp dụng cho source/skill/tài liệu
do chủ sở hữu tạo trong repo, không mở rộng quyền cho dependency, model weights hay nội dung
của bên thứ ba. Dependency Python được lấy theo uv.lock từ upstream khi cài; license của từng
dependency vẫn áp dụng. Không nhúng dependency binaries, model weights hay thư viện vendor.

Nguồn tham khảo trong skill: bài "Make your product videos look expensive (Apple Framework)"
của leo (@leomeethewoo), URL được giữ trong SKILL.md; không bao gồm bản sao video/bài viết.
