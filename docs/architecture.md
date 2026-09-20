# Kiến trúc

## Toàn cảnh

```
                         ┌──────────────────────────────────────┐
                         │  systemd: libretranslate.service     │
                         │  (enabled — tự chạy từ lúc boot)     │
                         │      docker compose up               │
                         └───────────────┬──────────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
┌───────────────────┐         ┌────────────────────┐          ┌──────────────────┐
│  libretranslate   │         │  engine (EnViT5)   │          │   web (nginx)    │
│  Argos/CTranslate2│         │  CTranslate2 int8  │          │                  │
│  :5000 ra ngoài   │         │  chỉ nội bộ :8000  │          │  :5001 ra ngoài  │
│  8 model, 5 ngôn  │         │  chỉ en↔vi         │          │                  │
└─────────▲─────────┘         └─────────▲──────────┘          └────────┬─────────┘
          │                             │                              │
          │  /api/*                     │  /api2/*                     │
          └─────────────────────────────┴──────────────────────────────┘
                                   proxy cùng origin
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            ▼                            ▼                            ▼
    ┌───────────────┐          ┌──────────────────┐        ┌──────────────────┐
    │  UI tiếng Việt│          │ Extension Brave  │        │  Trình đọc PDF   │
    │  :5001 (tĩnh) │          │  (service worker)│        │  pdf.js trong ext│
    └───────────────┘          └──────────────────┘        └──────────────────┘
```

## Vì sao có hai engine

| | LibreTranslate (Argos) | EnViT5 |
|---|---|---|
| Cặp | cả 5 ngôn ngữ, bắc cầu qua `en` | **chỉ `en↔vi`** |
| Tốc độ | ~134 ms | ~220 ms |
| Chất lượng EN↔VI | khá | **tốt hơn rõ rệt** |
| Dịch tệp, giữ HTML | có | không |

Đo thật trên máy này: `"no data ever leaves it"` → Argos cho *"không có dữ liệu
nào **từng để lại** nó"*, EnViT5 cho *"…nào **rời khỏi** nó"*. `"Click **Save**"` →
Argos **nuốt mất chữ Save**.

Chế độ mặc định là **Tự chọn**: EnViT5 cho `en↔vi`, LibreTranslate cho phần còn lại.

## Chọn engine — mẫu Strategy

`web/html/js/engines.js` và `extension/common.js` giữ cùng một mô hình: mỗi
engine **tự khai báo** cặp ngôn ngữ nó phục vụ, bên gọi chỉ hỏi *"ai làm được
cặp này"*.

```js
ENGINES = {
  lt: { base: "/api",  pairs: null },                         // null = mọi cặp
  hf: { base: "/api2", pairs: [["en","vi"], ["vi","en"]] },
};
```

**Quy tắc bắt buộc:** nguồn `"auto"` không bao giờ được coi là khớp với engine có
giới hạn cặp. Phải gọi `/detect` để biết ngôn ngữ thật *trước* khi chọn. Bỏ quy
tắc này từng khiến tiếng Nhật rơi vào EnViT5 và nhận về `":"`
([issue #4](issues.md#4-tiếng-nhậthàntrung-bị-dịch-thành-rác-mà-không-báo-lỗi)).

## Vì sao mọi thứ đi qua nginx

- **Cùng origin**: UI và API chung `:5001`, web app tương lai không phụ thuộc CORS.
- **Một cổng ra ngoài**: engine EnViT5 không mở cổng riêng.
- **Phân giải upstream theo từng request** (`resolver 127.0.0.11` + biến): engine
  chết chỉ trả 502, nginx vẫn khởi động được. Viết cứng tên host thì engine chưa
  tồn tại là nginx không chạy nổi, mất cả UI.

## Extension — ranh giới các lớp

```
content/placement.js   toán đặt vị trí thuần, không biết gì về dịch thuật
content/selection.js   đọc vùng bôi đen (DOM thường + ô nhập)
content/ui.js          lớp Overlay: shadow DOM, nút, thẻ — không gọi mạng
content/main.js        điều phối: selection → ui → service worker
common.js              chọn engine + gọi HTTP (dùng chung SW/popup/options)
background.js          service worker: **mọi lệnh gọi mạng nằm ở đây**
```

**Vì sao mạng phải ở service worker:** content script chạy theo origin của
*trang*. Trang `https://` gọi `http://127.0.0.1` sẽ vướng mixed content và
Private Network Access. Service worker chạy theo origin `chrome-extension://`
với `host_permissions` nên gọi được. Có test chặn `fetch(` xuất hiện trong
content script.

**Vì sao shadow DOM `closed`:** phải chèn UI lên *mọi* trang web. Shadow root
chặn CSS hai chiều; `closed` để trang không với vào được.

## Vòng đời

systemd giữ vòng đời, compose đặt `restart: "no"` — một nguồn quyết định duy
nhất. Unit chạy `docker compose up --abort-on-container-exit` ở foreground,
`Restart=always` lo dựng lại, log chảy vào journald.

Hệ quả cần biết: ba container **bị ghép**. Một cái thoát là cả ba dừng rồi
dựng lại. Tự lành, nhưng lỗi cấu hình nginx cũng kéo API xuống theo.

## Bố cục thư mục

```
engine/          EnViT5: Dockerfile đa tầng, convert.py, server.py
web/             nginx.conf + html/ (UI tiếng Việt, ES module)
extension/       MV3: content/, vendor/pdfjs/, viewer.*, background.js
scripts/         _config.sh, _docker-env.sh, install, ltctl, lt, verify*
systemd/         template unit
tests/           support.py, browser.py, cdp.mjs, test_*.py, e2e_*.mjs
docs/            tài liệu này
```
