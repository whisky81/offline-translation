# Vận hành

## Hằng ngày

| Việc | Lệnh |
|---|---|
| Mở UI | <http://127.0.0.1:5001/> |
| Trạng thái | `./scripts/ltctl status` |
| Log | `journalctl -u libretranslate -f` |
| Khởi động lại | `sudo systemctl restart libretranslate` |
| Dịch từ terminal | `./scripts/lt "Good morning"` |
| Xem mọi địa chỉ | `./scripts/ltctl url` |

## Tên daemon

**`libretranslate.service`** — một unit quản cả ba container:

| Container | Cổng |
|---|---|
| `libretranslate` | 5000 (API + UI gốc) |
| `lt-engine` | chỉ nội bộ |
| `lt-web` | 5001 (UI tiếng Việt) |

## Sau khi sửa cấu hình

| Sửa gì | Làm gì |
|---|---|
| `.env` | `sudo systemctl restart libretranslate` |
| `web/html/*` | Chỉ cần tải lại trang (bind-mount, `Cache-Control: no-store`) |
| `web/nginx.conf` | `docker exec lt-web nginx -s reload` |
| `engine/server.py` | `docker compose build engine` rồi restart |
| `extension/*` | `brave://extensions` → ⟳ → **Ctrl+R các tab đang mở** |
| `systemd/*.in` | `sudo ./scripts/install.sh` |

> Quên Ctrl+R sau khi nạp lại extension sẽ gặp thông báo *"Extension vừa được
> cập nhật…"* — xem [issue #19](issues.md#19-extension-context-invalidated).

## Kiểm tra sau khi khởi động máy

```bash
./scripts/ltctl boot-check              # 23 mục, không cần sudo
./scripts/ltctl boot-check --simulate   # diễn tập: down rồi up y như lúc boot
```

Cả `:5000` và `:5001` tự lên, **không cần đăng nhập**. Chuỗi phụ thuộc:

```
containerd → docker.socket → docker.service → libretranslate.service
```

`ExecStart` chạy `docker compose up` **không kèm tên service** nên khởi động mọi
service trong compose — thêm service mới là tự động được quản.

## Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| `error getting credentials … docker-credential-desktop` | Chạy `docker` ngoài script của project. Dùng `./scripts/ltctl`, hoặc `source scripts/_docker-env.sh` trước |
| Cổng 5000/5001 bị chiếm | Đổi `HOST_PORT`/`WEB_PORT` trong `.env` rồi restart |
| `/api2` trả 502 | Engine chưa chạy. `docker logs lt-engine`. UI vẫn dùng được với LibreTranslate |
| Khởi động lần đầu treo lâu | Đang tải model Argos, theo dõi `ltctl logs` |
| Extension không phản hồi | Ctrl+R trang. Xem log tại `brave://extensions` → service worker |
| PDF không bôi đen được | Đang dùng trình đọc sẵn của Chromium. Chuột phải → *Mở PDF bằng trình đọc có dịch* |
| PDF trên máy không mở được | `brave://extensions` → bật **Allow access to file URLs** |

## Tài nguyên

| | |
|---|---|
| RAM | ~1.7 GB (LibreTranslate 4 worker) + ~0.6 GB (engine) + nginx |
| Đĩa | image ~2 GB, model Argos ~870 MB, pdf.js 5.7 MB |
| Độ trễ | Argos ~134 ms, EnViT5 ~220 ms cho một câu |

`LT_THREADS` là số **worker gunicorn** (tiến trình riêng), mỗi worker nạp model
riêng → tăng là nhân RAM. Tổng tải = `LT_THREADS × OMP_NUM_THREADS`; máy 12 luồng
nên 4×4 là vừa.

## Gỡ

```bash
sudo ./scripts/uninstall.sh            # giữ model đã tải
sudo ./scripts/uninstall.sh --purge    # xoá sạch cả model lẫn image
```
