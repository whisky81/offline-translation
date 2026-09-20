# Dịch offline

Máy chủ dịch chạy hoàn toàn trên máy bạn — kèm giao diện web, extension cho
trình duyệt, và trình đọc PDF dịch tại chỗ. Không tài khoản, không API key,
**không byte nào rời khỏi máy** sau khi cài xong.

Làm cho tiếng Việt: `en ⇄ vi` dùng model chuyên dụng, cộng thêm `zh · ja · ko`.

```
┌─ trình duyệt ────────────────┐     ┌─ trên máy bạn ──────────────┐
│  bôi đen chữ → nút Dịch      │────▶│  nginx  127.0.0.1:5001      │
│  PDF → trình đọc có dịch     │     │    ├── /      giao diện     │
│  giao diện web đầy đủ        │     │    ├── /api   LibreTranslate│
└──────────────────────────────┘     │    └── /api2  EnViT5        │
                                     └─────────────────────────────┘
```

---

## Có gì

| | |
|---|---|
| **Giao diện web** | Dịch ngay khi gõ, tự nhận diện ngôn ngữ, các cách dịch khác, nền sáng/tối, lịch sử, kéo thả tệp |
| **Extension Brave/Chrome** | Bôi đen chữ trên bất kỳ trang nào → nút Dịch → thẻ kết quả tại chỗ. Có `Alt+T` và menu chuột phải |
| **Trình đọc PDF** | Trình đọc sẵn của Chromium không cho extension chạm vào nội dung, nên dự án ship trình đọc riêng bằng pdf.js — bôi đen và dịch như trang web thường |
| **Dịch cả tệp** | `.txt .odt .odp .docx .pptx .epub .html .srt .pdf`, giữ nguyên định dạng |
| **REST API** | `POST /api/translate`, nhận chuỗi hoặc mảng chuỗi |
| **Hai bộ dịch** | Argos nhanh, phủ mọi cặp; EnViT5 dịch EN↔VI sát hơn. Mặc định tự chọn |

## Yêu cầu

- Linux với systemd, Docker Engine (không phải Docker Desktop — xem [tại sao](docs/decisions.md))
- ~4 GB đĩa, ~3 GB RAM
- Mạng **chỉ cho lần cài đầu** (kéo image và tải model)

Đã chạy thật trên Ubuntu 26.04 / Intel i5-1235U / không GPU. Không cần GPU.

## Cài

```bash
git clone <repo> && cd setup-translate
cp .env.example .env

./scripts/preflight.sh        # kiểm tra môi trường, không đổi gì
sudo ./scripts/install.sh     # bước duy nhất cần sudo
./scripts/verify.sh           # 23 mục kiểm tra
```

Mở **<http://127.0.0.1:5001/>**.

<details>
<summary>Extension cho trình duyệt</summary>

```
brave://extensions  →  bật Developer mode  →  Load unpacked  →  chọn thư mục extension/
```

Với PDF trên máy, bật thêm **Allow access to file URLs** cho extension.
Sau mỗi lần bấm ⟳ nạp lại extension, nhớ `Ctrl+R` các tab đang mở.
</details>

<details>
<summary>Engine EnViT5 (tuỳ chọn, chất lượng EN↔VI cao hơn)</summary>

Được build sẵn trong `docker compose`. Lần đầu mất vài phút để tải model từ
Hugging Face và convert sang CTranslate2 int8 (~285 MB). Không bật cũng dùng
được — giao diện tự ẩn lựa chọn đó đi.
</details>

## Dùng

```bash
./scripts/lt "Good morning"              # dịch từ terminal
./scripts/lt --clip                      # dịch nội dung clipboard
./scripts/ltctl status                   # trạng thái
./scripts/ltctl logs                     # log trực tiếp
./scripts/ltctl url                      # in mọi địa chỉ
```

```bash
curl -X POST http://127.0.0.1:5001/api/translate \
  -H 'Content-Type: application/json' \
  -d '{"q":"Good morning","source":"auto","target":"vi","format":"text"}'
```

Dịch **mảng** trong một request nhanh hơn hẳn gọi từng câu:

```json
{"q": ["Save", "Cancel", "Delete"], "source": "en", "target": "vi", "format": "text"}
```

Client mẫu không phụ thuộc thư viện ngoài: [`examples/`](examples/) — Python
(thư viện chuẩn), TypeScript (`fetch`), và curl.

## Bảo mật

Đây là máy chủ chạy trên máy cá nhân, và dự án được cấu hình theo hướng đó:

| | |
|---|---|
| **Chỉ loopback** | Cổng duy nhất cống bố là `127.0.0.1:5001`. Địa chỉ được **ghi cứng** trong `docker-compose.yml`, không lấy từ biến — một dòng trong `.env` không thể vô tình mở cả stack ra mạng |
| **Một cửa duy nhất** | LibreTranslate và EnViT5 không cống bố cổng nào; chỉ tiếp cận được qua nginx |
| **Không CORS rộng** | LibreTranslate mặc định gửi `Access-Control-Allow-Origin: *` — nghĩa là *bất kỳ trang web nào bạn ghé cũng dùng được máy chủ dịch của bạn*. Header này bị gỡ ở proxy. Client của dự án không cần nó: giao diện web cùng origin, extension gọi từ service worker |
| **Bề mặt tối thiểu** | Giao diện gốc của LibreTranslate bị tắt — đã có giao diện riêng, giữ nó chỉ thêm chỗ để tấn công |
| **Container bị siết** | `cap_drop: ALL`, `no-new-privileges`, chạy dưới user không phải root, trần RAM |
| **Header an toàn** | CSP, `X-Content-Type-Options`, `Referrer-Policy` trên giao diện |
| **Không CDN** | Mọi tài nguyên nằm trên máy, kể cả pdf.js. Có test chặn mọi tham chiếu ra ngoài |
| **Extension xin ít quyền** | Chỉ `127.0.0.1:5001` và `file://`. Không xin quyền `tabs` (không đọc URL bạn mở). Quyền rộng là **tuỳ chọn**, xin khi cần |

`./scripts/verify.sh` kiểm tra lại những điều này mỗi lần chạy.

## Kiểm thử

```bash
./tests/run.sh          # 233 test
./tests/run.sh edge     # chỉ ca xấu / ca biên
```

Chỉ dùng `unittest` thư viện chuẩn và Node có sẵn — không cài gì thêm.

Ba tầng: **tĩnh** (manifest, quyền, cấu hình), **HTTP** (gọi thật vào máy chủ),
và **trình duyệt thật** (nạp extension vào Brave headless, bôi đen bằng chuột
thật, đọc pixel canvas). Tầng thứ ba là bài học đắt nhất của dự án — đã có lúc
bộ test tĩnh xanh hết trong khi extension hỏng hoàn toàn ngoài đời.

## Tài liệu

| | |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Thành phần, luồng dữ liệu, ranh giới các lớp |
| [`docs/issues.md`](docs/issues.md) | **26 lỗi đã gặp: triệu chứng, nguyên nhân gốc, cách sửa** |
| [`docs/decisions.md`](docs/decisions.md) | Quyết định thiết kế và cái giá của chúng |
| [`docs/testing.md`](docs/testing.md) | Chiến lược test, bẫy khi test trình duyệt |
| [`docs/operations.md`](docs/operations.md) | Vận hành, xử lý sự cố |
| [`docs/tech-stack.md`](docs/tech-stack.md) | Công nghệ, phiên bản, ràng buộc |

`docs/issues.md` là tài liệu đáng đọc nhất nếu bạn định sửa gì — nó ghi lại vì
sao code trông như hiện tại.

## Cấu hình

Sửa `.env` rồi `sudo systemctl restart libretranslate`.

| Biến | Mặc định | |
|---|---|---|
| `WEB_PORT` | `5001` | Cổng duy nhất cống bố (luôn trên loopback) |
| `LT_LOAD_ONLY` | `en,vi,zh,ja,ko` | Thêm ngôn ngữ rồi `ltctl update-models` |
| `LT_THREADS` | `4` | Số **worker gunicorn** — mỗi worker nạp model riêng, tăng là nhân RAM |
| `OMP_NUM_THREADS` | `4` | Thread inference mỗi worker. Tổng tải = tích hai số này |
| `ENGINE_MODEL_ID` | `VietAI/envit5-translation` | Đổi thì phải build lại engine |

## Gỡ

```bash
sudo ./scripts/uninstall.sh            # giữ model đã tải
sudo ./scripts/uninstall.sh --purge    # xoá sạch
```

## Giấy phép

Mã của dự án: MIT (xem [`LICENSE`](LICENSE)).

Thành phần bên thứ ba giữ giấy phép riêng: LibreTranslate (AGPL-3.0),
Argos Translate (MIT), [`VietAI/envit5-translation`](https://huggingface.co/VietAI/envit5-translation)
(OpenRAIL), [pdf.js](https://github.com/mozilla/pdf.js) (Apache-2.0), nginx (BSD-2-Clause).

Model dịch được tải khi chạy và **không** nằm trong repo này.
