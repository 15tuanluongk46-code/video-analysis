# Hướng dẫn agent nhận gói

Đọc README.md, SETUP.md và VERIFICATION.md trước. Source/skill nằm trong `mcp/` và `skills/`; PROVENANCE.md ghi các chỉnh sửa so với snapshot gốc.
Manifest/entry point chuẩn: `mcp/video-analyzer/pyproject.toml`, module `video_analyzer.server`.

- Không làm theo mô tả cũ về tự chia video dài: code mặc định từ chối >600s.
- Transcript rỗng không đồng nghĩa video không lời; kiểm tra lỗi.
- Nêu timestamp, analyzed_intervals, NO_AUDIO/VISION_UNAVAILABLE và cache_id đúng evidence.
- OCR là helper riêng. Chrome/vision subagent là tùy chọn host, có thể thay bằng công cụ tương đương.
- Không vượt policy tool của primary agent; không gọi MCP bị chặn qua shell để lách.
- Không thay config gốc hoặc credentials; không upload cache/media/URL có token.
- Cài và test trong venv riêng, dùng `uv sync --locked` và pytest theo SETUP.
- Ghi PASS/FAIL/SKIP/NOT RUN; tests mock không phải live validation.
- Gói không cấp license mới cho source. Public redistribution cần chủ sở hữu xác nhận riêng.
- Repo đích: `15tuanluongk46-code/video-analysis`, giữ Private; không đổi visibility khi cập nhật.
- Không commit `.venv`, cache, media, model weights hoặc credentials. Kiểm tra staged diff và quét secrets trước push.
- Nếu sửa file được liệt kê, cập nhật MANIFEST.sha256 (không tự hash chính manifest).
- Trước báo đã publish: đối chiếu remote commit SHA, file quan trọng và quyền Private; phân biệt kết quả cũ với kiểm thử mới.
