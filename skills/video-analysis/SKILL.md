---
name: video-analysis
description: "Phân tích video từ URL bằng MCP video-analyzer: nội dung, transcript, OCR, keyframes, hình ảnh, camera, dựng và motion graphics; tạo storyboard, keywords và prompt tái tạo. Dùng bất cứ khi nào user gửi link/file video và hỏi phân tích, tóm tắt, lời thoại, cảnh, chữ, màu sắc/theme, Motion Design, layout text, camera, chuyển cảnh, phong cách dựng, hoặc xin prompt/keyword làm video tương tự. Trigger gồm 'video này', 'phân tích video', '/video', 'tóm tắt video', 'lời thoại trong video', 'cảnh từ 00:25', 'phân tích motion design', 'prompt làm video tương tự', 'keyword video này'."
---

# Video Analysis

## Nguyên tắc cốt lõi

Trả lời câu hỏi THẬT của user dựa trên evidence thật (transcript + frame + OCR + mô tả hình ảnh). Không bịa. Phần không truy cập/phân tích được phải nói rõ là không có, kèm lý do.

## Công cụ (MCP `video-analyzer`)

| Tool | Việc |
|---|---|
| `video_inspect(url)` | Kiểm tra URL + cache → `CACHED` / `READY` / `NEEDS_BROWSER` / `UNSUPPORTED` / `ERROR` |
| `video_analyze(url, resolved_media_url=None, profile="balanced", max_duration_seconds=600)` | Tạo job phân tích → `job_id`, `cache_id` |
| `video_job_status(job_id)` | Phase: `queued→acquire→probe→sample→transcribe→vision→package→completed` (hoặc `failed`) |
| `video_get_evidence(cache_id, sections=None, start_seconds=None, end_seconds=None)` | Evidence đã phân tích: media, frames, contact sheets, transcript, vision, errors |
| `video_cache_info(cache_id=None)` | Trạng thái cache (TTL 24h, cap 5GB) |
| `video_cache_cleanup(max_age_hours=24)` | Dọn cache |

`profile`: `fast` (6–10 frames) / `balanced` (12–24) / `detailed` (24–48).

## Quy trình (fast path)

1. `video_inspect(url)`.
2. `CACHED` → `video_get_evidence(cache_id)` luôn (đừng phân tích lại). `READY` → `video_analyze` rồi poll `video_job_status` (10–20s/lần, báo user là đang chạy).
3. Đọc evidence THEO THỨ TỰ RẺ → ĐẮT:
   a. **Metadata + transcript** (ffprobe: duration, resolution, fps, audio; transcript rỗng = video không lời, thường là nhạc/SFX).
   b. **OCR chữ trên màn hình** — với video UI/screen-recording/text-heavy đây là nguồn thông tin chính. Chạy `scripts/ocr_timeline.py <cache_dir>/frames` (tesseract eng+vie, tự resize 1920px) → timeline text theo timestamp. Không cần vision cho phần chữ.
   c. **Vision chỉ 2–3 frame key** (frame có UI/overlay quan trọng nhất), dùng subagent `vision` với ảnh ≤900px, ≤40KB, **1 ảnh/call**. Nếu bị "attachments too large"/compaction → giảm còn 1 ảnh nhỏ hơn và thử lại, KHÔNG gửi 3–4 ảnh một lúc.
4. Trả lời:
   - Câu hỏi cụ thể → trả lời trực tiếp + timestamp dẫn chứng.
   - Không có câu hỏi → báo cáo 7 mục: Tóm tắt / Timeline cảnh / Lời nói / Text trên màn hình / Kỹ thuật hình ảnh & chuyển động / Chi tiết đáng chú ý / Phạm vi đã phân tích.
5. Luôn nêu `analyzed_intervals` + cảnh báo `NO_AUDIO` / `VISION_UNAVAILABLE` nếu có. Ghi `cache_id` cuối câu trả lời (follow-up trong 24h dùng lại cache).

## Nếu video_inspect trả NEEDS_BROWSER cho X/TikTok/IG/FB

Từ bản MCP có resolver (2026-09), X/Twitter/TikTok/IG/FB **không cần Chrome**: inspect tự probe bằng resolver/yt-dlp. Nếu vẫn thấy `NEEDS_BROWSER`:

1. MCP server đang chạy có thể giữ code cũ — thử `scripts/resolve_media.py <url>` (X: vxtwitter/fxtwitter API; còn lại: yt-dlp) để lấy direct media URL rồi `video_analyze(url, resolved_media_url="<media URL>")`.
2. Chỉ khi resolver + yt-dlp đều thất bại thật (private/DRM/login) mới sang Chrome fallback bên dưới.

## Chrome fallback (chỉ khi private/DRM/bot-check thật)

1. Dùng skill `chrome-ops` (Chrome AI, CDP 9222 — đã đăng nhập sẵn X/FB/IG...), mở URL bài viết.
2. Đọc network request của player để lấy URL media trực tiếp (`.mp4`, `.m3u8` — thường là `video.twimg.com`, `*.cdninstagram.com`, `*.fbcdn.net`...).
3. Gọi lại `video_analyze(url, resolved_media_url="<media URL>")` — evidence giữ nguyên `source_url` gốc.
4. Không lấy được (DRM/paywall/private) → dừng và báo đúng lý do.

X Article (bài viết dài) trên X không có href trong DOM: dùng JS-click vào card bài viết, URL canonical là `x.com/<user>/article/<status_id>` (chi tiết trong playbook chrome-ops).

## Phân tích Motion Design / Motion Graphics chuyên sâu

Khi user yêu cầu phân tích phong cách, Motion Design/Motion Graphics, camera/chuyển cảnh hoặc prompt tái tạo, không dừng ở tóm tắt nội dung. Xem video như một hệ thống hình ảnh chuyển động; dùng metadata, transcript, OCR và frame theo thời gian để mô tả các lớp thiết kế và cách chúng phối hợp. Nếu user chỉ hỏi một câu hẹp (ví dụ lời thoại hoặc một timestamp), trả lời đúng câu đó, không áp đặt toàn bộ báo cáo.

### Bằng chứng và độ chắc chắn

- Ưu tiên video evidence theo timeline. Dùng đủ frame để nhận ra thay đổi shot, trạng thái chữ và nhịp chuyển động; nếu 12–24 frame chưa đủ cho kiểu dựng nhanh, lấy thêm frame quanh các cut/beat hoặc dùng profile `detailed` khi cần phân tích lại.
- Gắn timestamp cho nhận định cụ thể. Tách **quan sát trực tiếp** (nhìn thấy ở frame/video) khỏi **diễn giải** (ví dụ “tạo cảm giác cấp bách”).
- Phân biệt camera move với chuyển động của chủ thể/đồ họa: nếu chỉ có frame tĩnh hoặc keyframe thưa, không khẳng định pan, zoom, tracking, whip-pan, match cut hay easing cụ thể. Ghi “không đủ frame để xác nhận” và mô tả điều nhìn thấy được.
- Không suy ra màu chính xác chỉ từ ảnh đã nén hoặc ánh sáng thay đổi. Mô tả palette theo vai trò/mối quan hệ màu; chỉ nêu mã màu khi có phép đo phù hợp.

### Những lớp cần phân tích

1. **Color theme / color script:** màu nền và màu chủ thể; màu nhấn typography/đồ họa; tương phản nóng-lạnh, sáng-tối, bão hòa; màu có ổn định qua các cảnh hay đổi theo beat; màu nào dẫn mắt và tạo mood. Phân biệt màu của footage với màu graphic/text overlay.
2. **Typography và text layout:** phân cấp headline/subhead/body; kiểu chữ (geometric sans, condensed, serif... chỉ khi nhận diện đủ cơ sở), weight, uppercase/lowercase, scale tương đối, căn lề, vị trí trong frame, khoảng trống, line breaks, tương phản/legibility trên nền; cách chữ tương tác/che phủ/chừa khoảng cho chủ thể; nội dung OCR và thời điểm xuất hiện/biến mất.
3. **Motion design:** chuyển động của chữ, shape, icon, mask và footage; hướng, quãng đường tương đối, tốc độ/nhịp, hold, overlap, stagger, reveal/exit; cảm giác easing chỉ nêu như ước lượng khi quan sát đủ. Nêu chức năng thị giác (nhấn từ khóa, dẫn mắt, tạo nhịp, nối ý) thay vì chỉ liệt kê hiệu ứng.
4. **Camera và bố cục:** cỡ cảnh, góc nhìn, vị trí chủ thể, headroom/negative space, độ sâu; camera tĩnh hay có chuyển động đã quan sát; handheld/stabilized chỉ khi evidence cho thấy. Tách camera movement khỏi zoom/crop hậu kỳ hoặc chủ thể dịch chuyển khi chưa phân định được.
5. **Editing và transitions:** nhịp shot, độ dài tương đối, cut theo hành động/nhạc/lời, hard cut, dissolve, graphic match, wipe, whip-pan hoặc transition khác chỉ khi nhìn thấy bằng chứng; ghi timestamp điểm vào/ra và quan hệ với text/beat. Không gọi một thay đổi cảnh là transition cụ thể nếu chỉ có hai keyframe rời rạc.
6. **Âm thanh và nhịp:** thoại/voice-over, nhạc, SFX, khoảng lặng; BPM/nhịp chỉ ước lượng nếu chưa đo được. Mô tả cách cut, text reveal và accent chuyển động đồng bộ với âm thanh nếu evidence hỗ trợ.

### Quy trình phân tích sâu

- Đối chiếu metadata với evidence; tạo shot/beat map theo timestamp. Dùng transcript cho nhịp câu, OCR cho chữ trên màn hình, frames/vision cho bố cục và thay đổi hình ảnh.
- Với mỗi shot/beat quan trọng, ghi: timestamp, hình/subject, màu, layout chữ, chuyển động/camera, cách vào-ra/chuyển cảnh, âm thanh liên quan và độ chắc chắn nếu có điểm mơ hồ.
- Tổng hợp thành “design system”: palette và vai trò màu, quy tắc typography/layout, ngôn ngữ chuyển động, camera/editing rhythm, mood và những motif lặp lại.
- Chỉ từ các yếu tố quan sát được mới xây dựng prompt. Giữ phần text overlay nguyên văn khi OCR đủ rõ; nếu tạo nội dung mới, đánh dấu đó là nội dung thay thế chứ không phải chữ gốc.

## Output: "Product-video recreation" (Keywords & Prompt)

Khi user xin keyword/prompt để làm video tương tự, xuất đúng khung:

1. **Chẩn đoán video gốc** — duration/resolution/fps, loại video, audio/voice-over/music/SFX và phạm vi đã phân tích.
2. **Creative direction** — mood/thông điệp, color theme có phân vai, typography/text layout, visual hierarchy, camera/framing, motion language, editing rhythm và transitions. Gắn timestamp; nêu rõ điều nào được quan sát và điều nào chỉ là suy luận.
3. **Keywords** — chia nhóm: style/genre; palette/lighting; typography/layout; camera/lens/framing; motion/animation; editing/transitions; music (BPM nếu xác minh/ước lượng); SFX; background/stock/AI visual; negative keywords. Ưu tiên search terms tiếng Anh có thể dùng trực tiếp.
4. **Storyboard shot-by-shot** — các mốc theo timestamp thật; mỗi shot gồm thời lượng, hình/subject, text nguyên văn hoặc ghi chú OCR, palette, framing/camera, motion, transition và audio cue. Nếu timeline chỉ được lấy mẫu thưa, trình bày là các mốc đại diện, không giả vờ đầy đủ từng cut.
5. **Prompt tổng bằng tiếng Anh** — mô tả format/aspect ratio, creative direction, palette, footage/subject, bố cục, typography và vị trí chữ, chuyển động theo từng lớp, camera, nhịp dựng/chuyển cảnh, âm thanh và kết thúc. Viết đủ cụ thể để tái tạo ngôn ngữ thị giác nhưng tránh khẳng định kỹ thuật không được xác nhận.
6. **Negative prompt** — lỗi cần tránh liên quan đến font, hierarchy, palette, bố cục, camera, motion, transitions, clutter, footage và âm thanh; chỉ dùng ví dụ phù hợp với video.
7. **Checklist tái tạo** — Branding/palette; typography và safe area; one beat–one idea; animation/camera có chủ đích; music/SFX theo nhịp.

Nguồn framework tham khảo: bài "Make your product videos look expensive (Apple Framework)" — leo (@leomeethewoo), `x.com/leomeethewoo/article/2103529310208606701`.

## Scripts

| Script | Việc |
|---|---|
| `scripts/resolve_media.py <url>` | URL X/TikTok/IG/FB → direct media URL (X: vxtwitter→fxtwitter; còn lại: yt-dlp `-g`). In URL ra stdout, exit 1 nếu fail. |
| `scripts/ocr_timeline.py <frames_dir>` | OCR toàn bộ frame (tesseract `eng+vie`, tự resize 1920px, psm 11) → timeline text theo từng frame, xuất markdown. |

## Giới hạn cần nhớ

- Chỉ http/https, chặn host nội bộ (SSRF guard); 1 video/lần, không playlist.
- Video > 10 phút: chỉ phân tích tối đa 5 cửa sổ, tổng ≤ 600s — `analyzed_intervals` nói rõ đã phân tích đoạn nào, không suy đoán phần còn lại.
- Download ≤ 750MB; cache ≤ 5GB, TTL 24h.
- Ollama tắt → vẫn có transcript + metadata + OCR, phần hình ảnh báo `VISION_UNAVAILABLE`.
- Không audio → `NO_AUDIO`, vẫn phân tích hình ảnh.
- Video dài: whisper `small` chạy CPU, transcribe có thể mất vài phút — báo user là đang chạy, không im lặng.
