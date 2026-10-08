# Cài đặt trên máy khác

## 1. Prerequisites

Khuyến nghị Linux/Ubuntu, Python 3.11 trở lên (kiểm thử bàn giao dùng Python 3.12),
`uv`, FFmpeg/ffprobe trên PATH; Tesseract với `eng` và `vie` để dùng OCR.
Windows/macOS chưa được kiểm thử; Windows dùng `.venv/Scripts/python.exe` thay `.venv/bin/python`.
Không cần API key cho pipeline mặc định. Không sao chép credentials từ máy nguồn.

Trên Ubuntu, nếu còn thiếu system tools (người cài tự duyệt quyền sudo):

```bash
sudo apt-get update
sudo apt-get install ffmpeg tesseract-ocr tesseract-ocr-eng tesseract-ocr-vie imagemagick
```

ImageMagick là tùy chọn để resize OCR. Cài `uv` theo https://docs.astral.sh/uv/getting-started/installation/.
Whisper `small` CPU/int8 được tải lần đầu khi transcribe. Ollama và `qwen2.5vl:7b`
cần cài riêng cho vision: https://ollama.com/download . Model weights không nằm trong gói.
Không có cam kết RAM/VRAM tối thiểu; phần vision có thể tốn nhiều RAM và thời gian.

## 2. Kiểm tra toàn vẹn và cài dependency

Clone repo Private bằng tài khoản đã được cấp quyền:

```bash
gh auth login
gh repo clone 15tuanluongk46-code/video-analysis
cd video-analysis
```

Nếu GitHub CLI đã đăng nhập đúng tài khoản thì bỏ qua `gh auth login`.
Không đặt token vào clone URL. Có thể dùng bản ZIP đã bàn giao thay cho clone;
giải nén vào một thư mục cố định. Những lệnh sau chạy từ thư mục gốc repo/gói:

```bash
sha256sum -c MANIFEST.sha256
uv sync --locked --project ./mcp/video-analyzer
uv run --project ./mcp/video-analyzer python --version
ffmpeg -version
ffprobe -version
tesseract --list-langs
```

`uv sync --locked` dùng `uv.lock`, tạo `.venv` mới riêng cho package; không copy venv từ máy nguồn.
Nếu lockfile không cài được trên OS/Python đích, giữ nguyên file và lưu lỗi; không âm thầm nâng dependency.

## 3. Vision và biến môi trường

Với Ollama đã cài, chạy `ollama serve` nếu chưa có service, rồi ở terminal khác:

```bash
ollama pull qwen2.5vl:7b
ollama list
```

Mặc định và override:

| Biến | Mặc định / ý nghĩa |
|---|---|
| `VIDEO_ANALYZER_CACHE` | `~/.cache/opencode/video-analyzer`; chọn thư mục private, có quyền ghi |
| `VIDEO_ANALYZER_WHISPER_MODEL` | `small`, faster-whisper CPU/int8 |
| `VIDEO_ANALYZER_OLLAMA_URL` | `http://localhost:11434` |
| `VIDEO_ANALYZER_VISION_MODEL` | `qwen2.5vl:7b` |
| `VIDEO_ANALYZER_VISION_NUM_CTX` | `8192` |

Không bật Ollama ra Internet. Thiếu Ollama/model → pipeline có thể trả `VISION_UNAVAILABLE`;
không được mô tả đó là phân tích hình ảnh thành công.

## 4. Tích hợp MCP stdio và skill

Lệnh server, chạy từ root gói để kiểm tra khởi động thủ công:

```bash
./mcp/video-analyzer/.venv/bin/python -m video_analyzer.server
```

Đây là **stdio server**, không phải HTTP web server; chờ input khi chạy terminal là bình thường.
Nhấn Ctrl+C để dừng. Client MCP nên tự khởi chạy và quản lý tiến trình này.

`examples/mcp-stdio.json` là mẫu cho client dùng `mcpServers` (ví dụ cấu trúc kiểu Claude Desktop).
Thay `/ABSOLUTE/PATH/video-analysis-full` bằng thư mục clone/giải nén thực tế; JSON không tự expand `~`.
OpenCode dùng schema MCP khác: thêm local server với **command dạng array** gồm đường dẫn Python
và `-m`, `video_analyzer.server`, theo tài liệu client hiện tại. Không copy nguyên `mcpServers` vào
OpenCode; không ghi đè config đang có và không tự bật tool đang bị policy hạn chế.

Copy `skills/video-analysis/` vào thư mục skills mà host hỗ trợ (OpenCode thường là
`~/.agents/skills/video-analysis`). Nếu đã có bản cũ, so sánh/backup trước, không ghi đè mù.
Sau đó reload host theo hướng dẫn của host. Source MCP là độc lập, không cần OpenCode để chạy.

Workflow: `video_inspect(url)` → `video_analyze(url, profile="balanced")` nếu cần →
poll `video_job_status(job_id)` → `video_get_evidence(cache_id)`.
Có cache còn hạn thì dùng lại. Khi chỉ có kết quả một phần, báo đúng phần thiếu.

## 5. Hai helper (không cần đường dẫn máy nguồn)

Dùng **Python của venv MCP**, không dùng system Python thiếu yt-dlp:

```bash
./mcp/video-analyzer/.venv/bin/python ./skills/video-analysis/scripts/resolve_media.py 'https://example.com/video'
./mcp/video-analyzer/.venv/bin/python ./skills/video-analysis/scripts/ocr_timeline.py /ABSOLUTE/PATH/frames --lang eng+vie
```

URL đầu tiên chỉ minh họa cú pháp; thay bằng URL video được quyền truy cập.
Resolver dùng yt-dlp trên PATH, sau đó module qua `sys.executable`:
lệnh trên bảo đảm chạy đúng interpreter, không mượn venv của máy tác giả.
FFmpeg/ffprobe ưu tiên PATH rồi tìm trong `~/.local/bin` của người dùng hiện tại.
Không tạo symlink giả về home máy nguồn. Helper resolver có thể in signed media URL:
không đưa output đó vào tài liệu public hoặc log chia sẻ.

Skill gốc nhắc subagent `vision` và `chrome-ops`/CDP 9222. Đây là **tích hợp tùy chọn**,
không được đóng gói browser đang đăng nhập. Dùng vision của host hoặc evidence Ollama;
dùng browser tool tương đương đã được người dùng cho phép khi thật sự cần fallback.
Nếu đăng nhập/CAPTCHA/DRM chặn, dừng và báo; không né kiểm soát truy cập.

## 6. Kiểm thử

```bash
uv run --project ./mcp/video-analyzer pytest ./mcp/video-analyzer/tests -q -ra
uv build --project ./mcp/video-analyzer
./mcp/video-analyzer/.venv/bin/python -m compileall -q ./mcp/video-analyzer/src ./skills/video-analysis/scripts
```

Test suite có một số probe mạng (resolver X/URL) nên không gọi toàn bộ suite là offline.
FFmpeg fixture được sinh lúc chạy tests; thiếu FFmpeg có thể SKIP, phải báo số skip.
Whisper/Ollama trong tests phần lớn được mock: test pass không chứng minh tải video social,
đăng nhập, chất lượng OCR hoặc inference model thật. Chưa có cấu hình lint/typecheck riêng trong manifest.

## 7. Output, lỗi và phạm vi bảo mật

Cache TTL mặc định 24h, mục tiêu cap 5GiB; tải tối đa 750MiB theo code.
Cache có video, audio, frames, transcript, source/resolved URLs; giữ private, không upload để bàn giao.
Mặc định duration >600s bị từ chối, không có window sampling tự động.
Client nhận evidence + `analyzed_intervals`; chỉ kết luận về phần thật sự có bằng chứng.

- Không tìm thấy FFmpeg: sửa PATH mà MCP client kế thừa, không chỉ PATH của terminal.
- yt-dlp import lỗi: chạy bằng `.venv/bin/python` sau `uv sync --locked`.
- Model download thất bại: kiểm tra mạng/dung lượng; không báo đã có transcript/vision.
- Server không hiện tools: kiểm tra command tuyệt đối, môi trường và stderr trong client.
- Không sửa config MCP hay session trên máy nguồn chỉ để chạy bundle.
