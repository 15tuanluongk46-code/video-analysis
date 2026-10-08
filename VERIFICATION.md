# Verification — 2026-10-08

## Portability follow-up local — sau publication

- Source FFmpeg/ffprobe dùng PATH rồi home người dùng hiện tại; resolver không còn mượn
  venv máy tác giả. Fixture FFmpeg cũng không chứa đường dẫn home cố định.
- RED: regression tests trước sửa cho thấy 5 lỗi do fallback máy tác giả; 2 ca PATH priority pass.
- PASS: `uv run --project mcp/video-analyzer pytest mcp/video-analyzer/tests -o addopts= -q -ra`
  sau sửa — 79 passed, 0 skipped, 7.53s.
- PASS: `uv build --project mcp/video-analyzer` — wheel và sdist.
- PASS: `git diff --check`.
- Skill đã sửa mô tả giới hạn duration, transcript rỗng và browser authorization;
  Python manifest/lockfile không thay đổi. Các mục lịch sử bên dưới mô tả phiên bản cũ.
- Chưa chạy live social video, inference model, hoặc phục hồi trên OS thứ hai.
- Đây là thay đổi trong checkout riêng; không phải bằng chứng đã commit/push lên GitHub.

## Phạm vi

Kiểm thử trên Linux, Python 3.12.3, trong bản copy riêng; không sửa source/skill gốc.
Không có Git repository tại AI-Home nên không có commit SHA; dùng MANIFEST.sha256.

## Kết quả đã chạy

- PASS: `uv sync --locked --project <bundle>/mcp/video-analyzer` — venv mới, 51 packages.
- PASS: `uv run --project <bundle>/mcp/video-analyzer pytest <bundle>/mcp/video-analyzer/tests -o addopts= -q -ra` — 72 passed, 0 skipped, 5.27s.
- PASS: `uv build --project <bundle>/mcp/video-analyzer` — sdist và wheel 0.1.0 build thành công; artifacts không cần đưa vào source bundle.
- PASS: `python3 -m compileall -q <bundle>/mcp/video-analyzer/src <bundle>/skills/video-analysis/scripts`.
- PASS: `tesseract --list-langs` có eng, vie; FFmpeg/ffprobe/uv có trên PATH.
- PASS: source copy so sánh SHA-256 với bản gốc ngay lúc staging.

## Kiểm tra archive thử đã chạy

- PASS: ZIP CRC (`ZipFile.testzip`) và kiểm tra SHA-256 toàn bộ manifest sau giải nén.
- PASS: `gitleaks dir <extracted-bundle> --redact --no-banner` — no leaks found, quét khoảng 409 KB source/docs.
- PASS: `uv sync --locked --project <extracted-bundle>/mcp/video-analyzer` — tạo venv mới sau giải nén.
- PASS: `uv run --project <extracted-bundle>/mcp/video-analyzer pytest <extracted-bundle>/mcp/video-analyzer/tests -o addopts= -q -ra` — 72 passed, 0 skipped, 6.73s.
- Archive cuối chỉ cập nhật báo cáo này; source/tests/lockfile giữ nguyên bytes của archive thử.
  CRC/manifest và secret scan của archive cuối được kiểm tra lại trước upload; kết quả báo trong phiên bàn giao.

## Không chạy / giới hạn

- NOT RUN: live video social/private, inference Whisper/Ollama thật, OCR accuracy E2E.
  Tests dùng mock ở phần inference; không có video đầu vào cho nhiệm vụ bàn giao này.
- NOT RUN: Windows/macOS; máy đích chưa được truy cập.
- NOT RUN: lint/typecheck riêng — manifest không cấu hình các checker đó.
- Context7 bị quota; lệnh uv đối chiếu với manifest/lockfile và chạy thực tế.

Verdict: source/package verified; live end-to-end và máy đích chưa được xác minh.

## Kiểm thử mới trước GitHub publication — 2026-10-08

Workspace độc lập: `/home/sss/Projects/video-analysis-full`, Linux / Python 3.12.3.
Repo mới, chưa có baseline commit; source/tests/lockfile giữ nguyên từ bundle Drive.

- PASS: `sha256sum -c MANIFEST.sha256` trước sửa docs — toàn bộ file khớp bản ZIP.
- PASS: `uv sync --locked --project ./mcp/video-analyzer` — venv mới, 51 packages.
  uv fallback từ hardlink sang copy do khác filesystem; cài đặt vẫn thành công.
- PASS: `uv run --project ./mcp/video-analyzer pytest ./mcp/video-analyzer/tests -o addopts= -q -ra` — 72 passed, 0 skipped, 6.61s.
- PASS: `uv build --project ./mcp/video-analyzer` — wheel + sdist 0.1.0.
- PASS: `./mcp/video-analyzer/.venv/bin/python -m compileall -q ./mcp/video-analyzer/src ./skills/video-analysis/scripts`.
- NOT RUN: live video/inference/OCR accuracy E2E và Windows/macOS; phạm vi kiểm thử không thay đổi.
- Manifest sẽ được cập nhật theo tài liệu GitHub; kiểm tra staged diff, quét secrets và
  đối chiếu remote SHA/visibility thực hiện trước khi báo publication thành công.
