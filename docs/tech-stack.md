# Công nghệ và ràng buộc

## Máy chạy

| | |
|---|---|
| OS | Ubuntu 26.04.1 LTS, kernel 7.0.0-31, x86_64 |
| Máy | Dell Inspiron 15 3520 |
| CPU | Intel i5-1235U — 10 nhân / 12 luồng (2P + 8E) |
| GPU | **Chỉ Intel Iris Xe (iGPU)** — không CUDA, mọi thứ chạy CPU |
| RAM | 14 GiB |
| Đĩa | 468 GB |
| Desktop | GNOME 50 / Wayland |
| Trình duyệt | Brave (Chromium) |

Ba ràng buộc này chi phối gần như mọi quyết định:

1. **Không GPU rời** → chọn engine dịch chuyên dụng (CTranslate2) thay vì LLM.
2. **Python hệ thống là 3.14** → không cài trực tiếp được `libretranslate`
   (nó ghim `flask==2.2.5`, `werkzeug==2.3.8` đời 2023). Mọi thứ chạy trong Docker.
3. **Máy có cả Docker Desktop lẫn docker-ce** → phải cô lập, xem
   [`issues.md`](issues.md#16-docker-desktop-chiếm-cấu-hình-cli).

## Thành phần

| Lớp | Công nghệ | Phiên bản | Ghi chú |
|---|---|---|---|
| Engine mặc định | LibreTranslate (Argos + CTranslate2) | 1.9.6 | Docker `libretranslate/libretranslate` |
| Engine chất lượng | VietAI/envit5-translation qua CTranslate2 | int8, 285 MB | Chỉ `en↔vi`, giấy phép `openrail` |
| Máy chủ engine | Python 3.12 + `http.server` | — | Tự viết, ~180 dòng |
| Proxy + UI | nginx | 1.29-alpine | Phục vụ UI tĩnh, proxy `/api` và `/api2` |
| UI web | HTML + ES module thuần | — | **Không framework, không CDN** |
| Extension | Chrome MV3 | — | Content script + service worker |
| Đọc PDF | pdf.js | 6.3.289 (Apache-2.0) | Chép vào `extension/vendor/`, không CDN |
| Vòng đời | systemd + docker compose | systemd 259 | Unit `libretranslate.service` |
| Test | `unittest` thư viện chuẩn + Node CDP | Python 3.14, Node 22 | Không phụ thuộc ngoài |

## Vì sao không có framework

Công cụ này phải chạy khi **mất mạng hoàn toàn**. Một CDN trong `<script src>`
là đủ để phá vỡ lời hứa đó. UI web và extension vì vậy dùng DOM thuần; pdf.js
được chép hẳn vào repo. Có test tự động chặn mọi tham chiếu `https://` lọt vào
mã nguồn UI.

## Mô hình ngôn ngữ

`LT_LOAD_ONLY=en,vi,zh,ja,ko` → 8 model Argos. Cặp không có model trực tiếp
(vd `vi→ja`) được dịch bắc cầu qua tiếng Anh, Argos tự lo.

`/languages` báo mã **`zh-Hans`**; gửi `zh` cũng được vì máy chủ tự quy đổi.
Mã ngôn ngữ giao diện thì `vi` **không dùng được** — bản dịch giao diện của
upstream chưa đủ hoàn chỉnh nên bị lọc bỏ khỏi 24 locale được chấp nhận.
