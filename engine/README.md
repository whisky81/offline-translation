# Engine EnViT5

Engine dịch thứ hai, chạy song song với LibreTranslate. Dùng
[`VietAI/envit5-translation`](https://huggingface.co/VietAI/envit5-translation) —
model T5 huấn luyện riêng cho EN↔VI trên bộ dữ liệu MTet và PhoMT.

| | |
|---|---|
| Kiến trúc | T5, chạy bằng CTranslate2 int8 trên CPU |
| Cặp ngôn ngữ | **chỉ `en↔vi`** — mọi cặp khác do LibreTranslate lo |
| Giấy phép | `openrail` (dùng thương mại được, khác với NLLB `cc-by-nc`) |
| Trọng số gốc | 1.1 GB fp32 → ~300 MB sau khi lượng tử hoá int8 |
| Cổng | không mở ra ngoài; chỉ truy cập qua `:5001/api2/` |

## Vì sao build nhiều tầng

Convert từ Hugging Face sang CTranslate2 **cần PyTorch** (~1 GB), nhưng lúc chạy
thì không. Nên `Dockerfile` chia hai tầng: tầng đầu có torch làm nhiệm vụ convert,
tầng sau chỉ chép thư mục model đã convert sang. Image chạy vì thế nhỏ hơn hẳn,
và `HF_HUB_OFFLINE=1` đảm bảo nó không bao giờ gọi ra mạng.

Có một bản convert sẵn trên HF (`luigi000/envit5-translation-ct2-int8`) nhưng chỉ
67 lượt tải — tự convert thì tái lập được và không phải tin bên thứ ba.

## Chi tiết quan trọng: tiền tố ngôn ngữ

EnViT5 nhận **ngôn ngữ nguồn** làm tiền tố, và trả về chuỗi **có tiền tố ngôn ngữ đích**:

```
"en: Good morning"        →  "vi: Chào buổi sáng"
"vi: Chào buổi sáng"      →  "en: Good morning"
```

`server.py` gắn tiền tố vào và cắt tiền tố ở đầu ra. Có test riêng
(`test_language_prefix_is_stripped`) canh đúng chỗ này — sai là người dùng thấy
`"vi: ..."` lòi ra trong bản dịch.

Hệ quả: hướng dịch do **tiền tố nguồn** quyết định, không có cách chọn đích khác.
Vì thế engine từ chối thẳng mọi cặp ngoài `en↔vi` thay vì trả về rác.

## API

Cùng dạng với LibreTranslate để UI đổi engine mà không phải viết lại gì.

| Endpoint | Việc |
|---|---|
| `GET /health` | Còn sống không |
| `GET /info` | Model, lượng tử hoá, beam size, giấy phép |
| `GET /languages` | `en`, `vi` |
| `POST /translate` | `q` nhận chuỗi hoặc mảng; `source: "auto"` dùng nhận diện dấu tiếng Việt |

```bash
curl -s -X POST http://127.0.0.1:5001/api2/translate \
  -H 'Content-Type: application/json' \
  -d '{"q":"Good morning","source":"en","target":"vi","format":"text"}'
```

`format: "html"` bị từ chối có chủ đích — T5 không giữ được thẻ HTML. Dùng
LibreTranslate cho trường hợp đó; UI tự làm việc này.

## Cấu hình

Trong `.env` của thư mục cha:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `ENGINE_MODEL_ID` | `VietAI/envit5-translation` | Đổi model thì phải build lại |
| `ENGINE_QUANT` | `int8` | `int8_float32` hoặc `float32` nếu muốn chính xác hơn, đổi lại tốn RAM |
| `ENGINE_INTRA_THREADS` | `4` | Thread inference. Tổng của cả hai engine không nên vượt 12 luồng của máy |
| `ENGINE_BEAM_SIZE` | `2` | `1` nhanh nhất; `4` khá hơn chút nhưng chậm |
| `ENGINE_MEM_LIMIT` | `3g` | Trần RAM container |

Build lại sau khi đổi model:

```bash
cd .. && . scripts/_docker-env.sh
docker compose --project-directory . build engine
sudo systemctl restart libretranslate
```

## Test

```bash
python3 -m unittest tests.test_engine -v      # chạy từ thư mục cha
```

26 test: health/info/languages, dịch hai chiều, cắt tiền tố, tự nhận diện, batch,
từ chối đúng cách với cặp không hỗ trợ và `format=html`, CORS, cách UI chọn engine,
và một test canh cho PyTorch không lọt vào image chạy.
