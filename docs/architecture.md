# Kiến trúc

## Toàn cảnh

```
                         ┌──────────────────────────────────────┐
                         │  systemd: libretranslate.service     │
                         │  (enabled — tự chạy từ lúc boot)     │
                         │      docker compose up               │
                         └───────────────┬──────────────────────┘
                                         │
       ┌───────────────┬─────────────────┬──────────────────┐
       ▼               ▼                 ▼                  ▼
┌──────────────┐ ┌───────────────┐ ┌──────────────┐ ┌─────────────────┐
│libretranslate│ │engine (EnViT5)│ │  tts (Piper) │ │   web (nginx)   │
│Argos/CTrans2 │ │CTranslate2int8│ │  VITS / ONNX │ │                 │
│ nội bộ :5000 │ │ nội bộ :8000  │ │ nội bộ :8100 │ │ 127.0.0.1:5001  │
│8 model,5 ngôn│ │   chỉ en↔vi   │ │ giọng vi, en │ │ ← cổng DUY NHẤT │
└──────▲───────┘ └───────▲───────┘ └──────▲───────┘ └────────┬────────┘
       │ /api/*          │ /api2/*        │ /api3/*          │
       └─────────────────┴────────────────┴──────────────────┘
                     proxy cùng origin, đã bỏ CORS
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            ▼                            ▼                            ▼
    ┌───────────────┐          ┌──────────────────┐        ┌──────────────────┐
    │  UI tiếng Việt│          │ Extension Brave  │        │  Trình đọc PDF   │
    │  :5001 (tĩnh) │          │  (service worker)│        │  pdf.js trong ext│
    └───────────────┘          └──────────────────┘        └──────────────────┘
```

Không container nào ngoài `web` công bố cổng ra host, và `127.0.0.1` được **ghi
cứng** trong `docker-compose.yml` chứ không lấy từ `.env` — để một dòng cấu hình
không thể vô tình mở cả stack ra mạng.

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

Máy đọc theo cùng tinh thần nhưng **tự khai báo lúc chạy**: ngôn ngữ của mỗi
giọng đọc từ tệp `.onnx.json` đi kèm, `/api3/health` liệt kê ra, và UI chỉ hiện
nút Đọc cho những thứ tiếng có trong danh sách. Thêm một giọng mới không phải
sửa dòng mã nào.

**Quy tắc bắt buộc:** nguồn `"auto"` không bao giờ được coi là khớp với engine có
giới hạn cặp. Phải gọi `/detect` để biết ngôn ngữ thật *trước* khi chọn. Bỏ quy
tắc này từng khiến tiếng Nhật rơi vào EnViT5 và nhận về `":"`
([issue #4](issues.md#4-tiếng-nhậthàntrung-bị-dịch-thành-rác-mà-không-báo-lỗi)).

## Máy đọc — vì sao là máy chủ, không phải trình duyệt

Cách rẻ nhất lẽ ra là `speechSynthesis`. Nhưng trong Brave trên máy này
`getVoices()` trả về **mảng rỗng**: Chromium trên Linux không kèm giọng nào, nó
mượn `speech-dispatcher` của hệ thống, mà ở đây nó `inactive` và thiếu engine.
Nút Đọc kiểu đó sẽ im lặng và không báo lỗi gì. Nên máy đọc nằm ở phía máy chủ
và trả về WAV.

### Cắt câu ở client, không ở máy chủ

`tts/server.py` là một hàm thuần `text -> wav`. Việc cắt nằm ở client
(`web/html/js/tts.js` và bản sao `extension/tts.js`). Lý do là con số đo được:

| | |
|---|---|
| Tổng hợp 2000 ký tự | ~8–10 giây |
| Tổng hợp 301 ký tự | **1,37 giây** → **15,93 giây tiếng** |

Tổng hợp nhanh hơn phát ~10 lần. Nên client cắt theo ranh giới câu (~320 ký tự),
phát đoạn này **trong lúc tải đoạn sau**. Tiếng bắt đầu sau ~1 giây thay vì ~10
giây, và từ đoạn thứ hai trở đi không bao giờ hụt. Đo trong trình duyệt thật:
đoạn 1 tải xong ở giây 5,3 nhưng mãi giây 21,8 mới tới lượt phát.

`web/html/js/tts.js` và `extension/tts.js` **giống nhau từng byte** — có test so
sánh nhị phân để chúng không trôi ra khỏi nhau.

### Vì sao cần tài liệu offscreen

Service worker của MV3 không có DOM nên không phát được âm thanh. Còn phát trong
content script thì thẻ `<audio>` nằm trong trang và **chịu CSP `media-src` của
trang đó** — một trang siết `default-src 'self'` sẽ chặn `blob:` và nút Đọc lại
im lặng. `offscreen.html` chạy theo origin của extension nên thoát cả hai.

```
content/ui.js  bấm Đọc
      │  chrome.runtime.sendMessage {type:"tts-speak"}
      ▼
background.js  chrome.offscreen.createDocument(AUDIO_PLAYBACK)
      │  sendMessage {target:"offscreen", type:"tts-play"}
      ▼
offscreen.js   Reader: cắt câu → fetch /api3/speak → <audio>.play()
      │  sendMessage {type:"tts-state"}            ┐
      ▼                                            │ đường báo ngược
background.js  chrome.tabs.sendMessage(ttsTabId)   │ (nhãn nút tự trở về)
      ▼                                            ┘
content/main.js  overlay.setReading(null)
```

Đường báo ngược là bắt buộc: `chrome.runtime.sendMessage` **không tới được**
content script, nên service worker phải chuyển tiếp qua `chrome.tabs.sendMessage`.
Đứt đoạn này thì nút kẹt ở "Dừng" vĩnh viễn — có test riêng cho đúng điều đó.

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
tts.js                 cắt câu + phát nối tiếp (bản sao byte-đối-byte của web UI)
offscreen.js           nơi duy nhất thật sự phát âm thanh
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

Hệ quả cần biết: bốn container **bị ghép**. Một cái thoát là cả bốn dừng rồi
dựng lại. Tự lành, nhưng lỗi cấu hình nginx cũng kéo API xuống theo.

## Bố cục thư mục

```
engine/          EnViT5: Dockerfile đa tầng, convert.py, server.py
tts/             Piper: Dockerfile đa tầng, download_voices.py, server.py
web/             nginx.conf + html/ (UI tiếng Việt, ES module)
extension/       MV3: content/, vendor/pdfjs/, viewer.*, background.js
scripts/         _config.sh, _docker-env.sh, install, ltctl, lt, verify*
systemd/         template unit
tests/           support.py, browser.py, cdp.mjs, test_*.py, e2e_*.mjs
docs/            tài liệu này
```
