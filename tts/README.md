# Máy đọc (Piper)

Đọc văn bản thành tiếng, chạy hoàn toàn trên máy. Dùng
[Piper](https://github.com/OHF-Voice/piper1-gpl) — mạng neural VITS chạy bằng
onnxruntime trên CPU.

| | |
|---|---|
| Kiến trúc | VITS (ONNX), chạy CPU |
| Giọng mặc định | `vi_VN-vais1000-medium`, `en_US-amy-medium` |
| Giấy phép | mã Piper **GPL-3.0-or-later**, giọng nói **MIT** |
| Kích thước image | ~711 MB (giọng 121 MB, onnxruntime 67 MB, numpy 70 MB, dữ liệu espeak 46 MB) |
| RAM | ~290 MB lúc mới nạp, chạm trần **~1,3 GB** khi đọc đoạn 2000 ký tự |
| Cổng | không mở ra ngoài; chỉ truy cập qua `:5001/api3/` |

## Vì sao phải là máy chủ, không dùng trình duyệt

Cách rẻ nhất lẽ ra là `speechSynthesis` của trình duyệt: 0 dòng phía máy chủ.
Nhưng trên máy này:

```
> speechSynthesis.getVoices()
{"count": 0, "sample": [], "vi": []}
```

Chrome và Brave trên Linux **không kèm giọng nào** — chúng đi mượn
`speech-dispatcher` của hệ thống, mà ở đây nó đang `inactive` và thiếu luôn
engine espeak-ng. Nút "Đọc" kiểu đó sẽ bấm mà không ra tiếng, và không báo lỗi
gì. Tổng hợp ở máy chủ rồi trả về WAV thì máy nào, trình duyệt nào cũng nghe được.

## Vì sao build nhiều tầng

Tầng đầu chỉ tải giọng từ Hugging Face; tầng sau cài Piper rồi chép giọng sang.
Nhờ vậy đổi `TTS_VOICES` không bắt cài lại pip, và ngược lại. Lúc chạy không
có lệnh gọi mạng nào.

## API

Chỉ có `POST`. Không có `GET /speak` — bề mặt càng hẹp càng tốt.

```
GET  /health   {"status":"ok","voices":2,"languages":["en","vi"],"loaded":[...]}
GET  /voices   [{"id","lang","locale","quality","sample_rate","speakers"}, ...]
GET  /info     {"engine":"piper","max_chars":2000,"speed_range":[0.5,2.0],"cache":{...}}
POST /speak    {"q": "...", "lang": "vi" | "voice": "<id>", "speed": 1.0}  ->  audio/wav
```

`/speak` trả về **âm thanh**, không phải JSON. Thông tin phụ nằm ở header:

| Header | Nghĩa |
|---|---|
| `X-Voice` | giọng đã dùng |
| `X-Lang` | mã ngôn ngữ |
| `X-Ms` | thời gian tổng hợp (0 nếu lấy từ bộ đệm) |
| `X-Cached` | `1` nếu lấy từ bộ đệm |
| `X-Truncated` | `1` nếu văn bản đã bị cắt ở `TTS_MAX_CHARS` |
| `X-Chars` | số ký tự thực sự đã đọc |
| `X-Seconds` | độ dài đoạn tiếng |

Mọi đầu vào hỏng đều ra `400` kèm thông báo đọc được, **không bao giờ** ra một
tệp WAV rỗng — bấm Đọc mà im lặng là kiểu hỏng khó chẩn đoán nhất.

## Vì sao client phải tự cắt câu

Tổng hợp 2000 ký tự mất ~8–10 giây. Bấm Đọc rồi ngồi chờ 10 giây thì người dùng
tưởng hỏng. Nhưng tổng hợp **nhanh hơn phát khoảng 10 lần** — đo thực tế:

```
301 ký tự  ->  1,37 giây tổng hợp  ->  15,93 giây tiếng
```

Nên client cắt văn bản theo ranh giới câu (~320 ký tự một đoạn), phát đoạn này
trong lúc tải đoạn sau. Tiếng bắt đầu sau ~1 giây, và từ đoạn thứ hai trở đi
không bao giờ hụt. Máy chủ vì thế giữ nguyên là một hàm thuần `text -> wav`;
`TTS_MAX_CHARS` chỉ là chốt chặn. Bản đầy đủ nằm ở `web/html/js/tts.js`
(`chunk()` và `class Reader`).

## Đổi giọng

Danh sách giọng nướng vào image lúc build. Sửa `TTS_VOICES` trong `.env` rồi:

```bash
./scripts/ltctl rebuild-tts
```

Đường dẫn lấy từ repo [`rhasspy/piper-voices`](https://huggingface.co/rhasspy/piper-voices),
**không kèm đuôi tệp**, cách nhau bằng khoảng trắng:

```
TTS_VOICES=vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium en/en_US/amy/medium/en_US-amy-medium
```

Giọng tiếng Việt khác: `vi/vi_VN/25hours_single/low/...`, `vi/vi_VN/vivos/x_low/...`
(nhẹ hơn nhưng nghe kém hơn rõ rệt).

Ngôn ngữ của mỗi giọng đọc từ tệp `.onnx.json` đi kèm, nên thêm một thứ tiếng
mới **không phải sửa mã nguồn** — chỉ thêm đường dẫn rồi build lại. Nút Đọc trên
web UI và trên thẻ dịch tự hiện theo danh sách `/health`.

Thêm nhiều giọng thì RAM tăng theo: giọng được nạp **lười**, chỉ khi có người
dùng đến, mỗi giọng `medium` khoảng 90 MB.

## Giấy phép

Piper là GPL-3.0 (vì nó nhúng espeak-ng để chuyển chữ sang âm vị). Nó chạy trong
container riêng và chỉ giao tiếp qua HTTP — cùng dạng với LibreTranslate (AGPL-3.0)
trong dự án này. Bản thân các tệp giọng là MIT. Xem `LICENSE` ở gốc dự án.
