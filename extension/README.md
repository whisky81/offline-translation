# Extension "Dịch offline" cho Brave / Chrome

Bôi đen chữ trên bất kỳ trang nào → hiện nút nhỏ → bấm → thẻ dịch hiện ngay tại chỗ.
Dùng chính máy chủ đang chạy trên máy bạn, không gửi gì ra ngoài.

## Cài

Brave không cho cài extension ngoài Web Store bằng cách kéo thả, phải bật chế độ nhà phát triển:

1. Mở `brave://extensions`
2. Bật **Developer mode** (góc trên bên phải)
3. Bấm **Load unpacked** → chọn thư mục `~/setup-translate/extension`

Xong. Ghim biểu tượng lên thanh công cụ cho tiện.

> Máy chủ phải đang chạy: `cd ~/setup-translate && ./scripts/ltctl status`

## Dùng

| Thao tác | Kết quả |
|---|---|
| Bôi đen chữ | Hiện nút **🗣️ Dịch** ngay dưới vùng chọn |
| Bấm nút đó | Thẻ dịch hiện ra, đổi được ngôn ngữ đích ngay trong thẻ |
| **Alt+T** | Dịch phần đang bôi đen, không cần bấm nút |
| Chuột phải → *Dịch đoạn đang chọn* | Như trên |
| Bấm biểu tượng extension | Popup để dán văn bản dài; nếu đang bôi đen sẵn thì tự điền vào |
| `Esc`, cuộn trang, hoặc bấm ra ngoài | Đóng thẻ |

## Bộ dịch

| Lựa chọn | Hành vi |
|---|---|
| **Tự chọn** (mặc định) | EnViT5 cho EN↔VI (dịch sát hơn), LibreTranslate cho các cặp còn lại |
| LibreTranslate | Luôn dùng Argos — nhanh nhất, phủ mọi cặp |
| EnViT5 | Chỉ EN↔VI; cặp khác tự quay về LibreTranslate và nói rõ lý do |

## Vì sao mọi lệnh gọi mạng nằm ở service worker

Đây là phần dễ sai nhất của extension kiểu này.

Content script chạy theo **origin của trang đang mở**. Một trang `https://` gọi
`http://127.0.0.1:5001` sẽ bị chặn vì hai lý do: mixed content, và Private Network
Access (Chromium chặn trang công cộng gọi vào mạng nội bộ).

Service worker của extension thì chạy theo origin `chrome-extension://`, và với
`host_permissions` trỏ tới `http://127.0.0.1:5001/*` thì fetch được phép — bất kể
trang người dùng đang mở là http hay https.

Nên luồng là:

```
content.js  --chrome.runtime.sendMessage-->  background.js  --fetch-->  127.0.0.1:5001
            <--------- kết quả -------------
```

`tests/test_extension.py` có test khẳng định `content.js` **không** chứa `fetch(`.

## PDF

Trình đọc PDF sẵn của Chromium **không cho extension chạm vào nội dung**. Đo bằng CDP:

```
contentType : application/pdf
body        : "\n    \n  \n"          ← trang ngoài rỗng
iframe      : chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/index.html
window.getSelection() sau Ctrl+A : ""
```

Chữ nằm trong PDF Viewer nội bộ (một extension khác) và sâu hơn nữa là plugin PDFium.
Extension bên thứ ba không chèn content script vào origin `chrome-extension://` của
extension khác được. Không có cách nào lách.

Nên extension này ship **trình đọc PDF riêng** dùng pdf.js (`viewer.html`), ở đó lớp chữ
là DOM thật. `viewer.html` nhúng thẳng `content.js`, nên nút và thẻ dịch giống hệt trên web.

**Cách mở:** chuột phải trên trang PDF → *Mở PDF bằng trình đọc có dịch*, hoặc bấm biểu
tượng extension rồi bấm nút hiện ra. Trong trình đọc còn có nút **Dịch cả tệp** (đi qua
`/translate_file` của LibreTranslate, vốn đã hỗ trợ `.pdf`).

**Với tệp trên máy** (`file:///…`): vào `brave://extensions` → *Dịch offline* → bật
**"Allow access to file URLs"**. Không có nó thì Brave chặn, và trình đọc sẽ báo đúng điều này.

**Với PDF trên một trang web khác:** extension không đòi quyền đọc mọi trang từ đầu.
Lần đầu mở PDF ở một tên miền lạ, trình đọc hiện nút **Cho phép** để xin quyền đúng
tên miền đó (`optional_host_permissions`).

pdf.js 6.3.289 (Apache-2.0) được chép vào `vendor/pdfjs/` — **không gọi CDN**, đúng tinh
thần offline. Kèm `standard_fonts/` (PDF dùng Helvetica/Times cần nó), `cmaps/`
(PDF tiếng Trung/Nhật/Hàn) và `wasm/` (JBIG2, JPEG2000, quản lý màu).

Trình đọc đặt `verbosity: ERRORS` khi gọi `getDocument` — pdf.js cảnh báo về mọi
khiếm khuyết của tài liệu (vd `TT: undefined function: 32` khi font nhúng khai dùng
một hàm hinting mà không định nghĩa), và chúng làm đầy trang lỗi trong
`brave://extensions` dù chữ vẫn hiện bình thường. Thêm `?debug=1` vào URL của trình
đọc để bật lại mức đầy đủ.

Phần `wasm/` đòi nới CSP: trang extension MV3 mặc định là `script-src 'self'`, và CSP
này **cấm WebAssembly**. Manifest vì vậy khai thêm `'wasm-unsafe-eval'` — nó chỉ mở
WebAssembly, **không** mở `eval()` cho chuỗi JavaScript. Thiếu nó thì PDF quét mất
hết ảnh và console báo `#instantiateWasm: CompileError`.

## Vì sao phải nhận diện ngôn ngữ *trước* khi chọn bộ dịch

Lúc đầu tôi để `source: "auto"` được coi là khớp với mọi cặp. Chạy thật trong Brave
mới lộ ra hai lỗi:

| Thao tác | Trước khi sửa | Sau khi sửa |
|---|---|---|
| Bôi đen **tiếng Nhật**, đích `vi` | Rơi vào EnViT5 → nó đoán bừa thành tiếng Anh → trả về `":"`, **sai thầm lặng** | LibreTranslate `ja→vi` → "Hôm nay thời tiết rất tốt…" |
| Bôi đen **tiếng Việt**, đích `vi` | `vi→vi` → lỗi 400, thông báo thô của máy chủ lòi ra thẻ | Tự đổi sang `vi→en`, ghi rõ *"đã là vi, dịch sang en"* |

Nên luồng bây giờ là: gọi `/api/detect` trước → biết ngôn ngữ thật → mới chọn engine.
`engineHandles()` từ chối thẳng `source === "auto"` với engine có giới hạn cặp.

Có thêm lớp chắn thứ hai ngay trong `engine/server.py`: nếu văn bản chứa chữ
Hán / Kana / Hangul mà `source="auto"`, engine **từ chối** thay vì đoán. Hai lớp,
vì sai thầm lặng khó phát hiện hơn nhiều so với báo lỗi.

## "Extension context invalidated"

Gặp khi bạn bấm ⟳ ở `brave://extensions` mà **không tải lại các tab đang mở**.
Chrome/Brave không tự chèn lại content script vào tab cũ, nên script ở đó mất
kết nối với service worker.

Đã xử lý ba lớp:

1. **Thông báo dễ hiểu** thay vì lỗi kỹ thuật: *"Extension vừa được cập nhật hoặc
   tắt đi. Tải lại trang (Ctrl+R) rồi bôi đen lại."* Kiểm tra `chrome.runtime?.id`
   trước khi gọi, và bắt cả `context invalidated` lẫn `receiving end does not exist`.
2. **Tự chèn lại** vào các tab mà extension có quyền (`127.0.0.1:5001`, `file://`)
   mỗi lần extension được nạp. Dùng `chrome.storage.session` làm cờ — nó bị xoá
   đúng lúc extension nạp lại, nên chèn một lần cho mỗi lần nạp chứ không phải
   mỗi lần service worker thức dậy.
3. **Thay thế thay vì chồng lên**: bản mới gọi `window.__dichOfflineCleanup()` của
   bản cũ. Mọi listener đều gắn vào một `AbortController` nên gỡ sạch trong một
   lệnh, kèm xoá host shadow DOM. Không có bước này thì chèn lại sẽ thành hai bộ
   giao diện chồng nhau.

Với các trang web khác (không có trong `host_permissions`), extension không thể
tự chèn lại — lúc đó thông báo ở mục 1 là thứ hướng dẫn bạn.

## Chi tiết UX đã xử lý

Tìm ra bằng cách điều khiển Brave thật và **chụp ảnh màn hình để nhìn**, không phải bằng đọc code:

| Vấn đề | Cách xử lý |
|---|---|
| **Bản dịch hiện ra rồi biến mất ngay.** `run()` ẩn nút ngay ở `mousedown`; đến lúc nhả chuột, chỗ đó không còn nút nên `mouseup` rơi xuống **trang** bên dưới → `composedPath()` không chứa host → handler tưởng vừa bôi đen chỗ khác → `showBubble()` → hàm này gọi `hideCard()`. EnViT5 trả về trong ~130 ms nên một cú bấm bình thường cũng đủ mất kết quả | Bỏ qua đúng một `mouseup` sau khi bấm nút (`skipNextMouseup`) |
| **Popup che mất dòng ngay dưới vùng chọn** — trên PDF dày chữ thì mất ngữ cảnh | Đặt **cạnh bên** vùng chọn trước (lề trang PDF, cột hẹp trên web), rồi mới dưới, rồi trên; đo kích thước thật sau khi vẽ xong rồi mới định vị |
| Biểu tượng emoji 🗣️ ra ô vuông trống khi thiếu font | Thay bằng SVG nội tuyến |
| **Bản dịch biến mất khi cuộn trang.** Trên touchpad chỉ cần hai ngón nhích nhẹ là cuộn — đọc PDF thì gần như không tránh được, nên vừa bấm dịch xong đã phải bấm lại | Cuộn chỉ ẩn **nút** (nó neo theo vùng chọn nên sẽ lệch chỗ); **thẻ giữ nguyên**. Thẻ dùng `position:fixed` nên cuộn cũng không trôi. Đóng bằng `Esc`, nút ✕, hoặc bấm ra ngoài |
| **Vùng tô sáng không phủ hết chữ, nhưng copy lại lấy cả phần trông như chưa chọn.** pdf.js 6.x đọc biến CSS `--total-scale-factor`, tôi đặt nhầm tên cũ `--scale-factor` → `calc()` trong `textlayer.css` hỏng → `font-size` của span rơi về mặc định 14px thay vì 20px → span **ngắn hơn chữ thật tới ~150px** | Đặt đúng `--total-scale-factor` (giữ cả tên cũ cho bản pdf.js đời trước). Đo lại: lệch còn **1px** |
| **Bấm `Esc` lúc đang dịch không huỷ được** — vài trăm ms sau bản dịch về và tự mở lại thẻ | Mỗi lần dịch mang một số thứ tự; đóng thẻ thì tăng số đó lên, kết quả của lần đã huỷ không còn được vẽ ra |
| **Bôi đen trong PDF hay nhảy sang đoạn khác, copy ra sai chữ** | pdf.js chia việc: *thư viện* vẽ các span, *viewer* lo phần bôi đen — mà viewer là tôi tự viết nên thiếu hẳn. Đã thêm `.endOfContent` (lớp không-chọn-được nằm dưới các span) và class `selecting` bật/tắt theo thao tác kéo, đúng cách viewer chính thức của pdf.js làm |
| Cuộn **bên trong** thẻ dịch làm thẻ tự đóng — bản dịch dài không đọc hết được | Sự kiện `scroll` không nổi bọt nhưng **có** đi qua pha capture của `window`. Loại trừ host khỏi listener đó |
| Bôi đen trong `<textarea>`/`<input>` không hiện nút | `window.getSelection()` **có** trả về chữ, nhưng `getRangeAt(0).getBoundingClientRect()` rỗng vì vùng chọn nằm trong shadow tree của ô nhập. Khi rect rỗng thì lấy khung của chính ô nhập |
| Trình đọc màn hình không thấy nút và thẻ | Thêm `role="button"` + `tabindex` + `aria-label` cho nút (bấm được bằng Enter/Space), `role="dialog"` + `aria-live` cho thẻ, `:focus-visible` rõ ràng |
| Đổi kích thước cửa sổ làm thẻ tràn ra ngoài màn hình | Kẹp lại trong khung nhìn thay vì đóng |

## Vì sao giao diện nằm trong shadow DOM

Nút và thẻ dịch được gắn vào một shadow root `mode: "closed"`. CSS của trang không
lọt vào được, và CSS của extension không làm hỏng trang. Không có cách nào khác an
toàn khi phải chèn UI lên *mọi* trang web.

Chi tiết nhỏ nhưng quan trọng: nút bắt sự kiện **`mousedown`** chứ không phải `click`.
Dùng `click` thì trình duyệt đã xoá vùng bôi đen trước khi mình kịp đọc.

## Tuỳ chọn

`brave://extensions` → *Dịch offline* → **Extension options**, hoặc bấm "Tuỳ chọn" trong popup.

| Mục | Mặc định |
|---|---|
| Địa chỉ máy chủ | `http://127.0.0.1:5001` |
| Bộ dịch | Tự chọn |
| Dịch sang | Tiếng Việt |
| Hiện nút khi bôi đen | Bật — tắt đi thì vẫn dùng được Alt+T và menu chuột phải |
| Giới hạn ký tự | 5000 |

Nút **Kiểm tra kết nối** cho biết cả hai engine có sống không.

## Quyền xin và lý do

| Quyền | Để làm gì |
|---|---|
| `storage` | Nhớ tuỳ chọn |
| `contextMenus` | Mục "Dịch đoạn đang chọn" trong menu chuột phải |
| `scripting` + `activeTab` | Đọc vùng bôi đen khi bạn mở popup từ thanh công cụ |
| `host_permissions: 127.0.0.1:5001` | Gọi máy chủ dịch — **chỉ localhost, không có tên miền nào khác** |
| `content_scripts: <all_urls>` | Bắt buộc, vì phải bôi đen được trên mọi trang |

Không xin quyền `tabs` (không đọc URL hay tiêu đề trang bạn mở).

## Test

```bash
python3 -m unittest tests.test_extension -v     # chạy từ thư mục cha
```

31 test: manifest MV3, mọi tệp tham chiếu tồn tại, icon đúng kích thước, **mọi API
`chrome.*` được dùng đều có quyền tương ứng** (và ngược lại — không xin quyền thừa),
mạng chỉ đi qua service worker, và **hàm `translate()` chạy thật bằng Node đánh vào
máy chủ thật** cho cả 5 thứ tiếng — khoá lại đúng hai lỗi nêu ở trên.

### Kiểm thử đầu-cuối trong trình duyệt thật

Test tĩnh không đủ: hai lỗi trên chỉ lộ ra khi chạy thật. Cách tái lập:

```bash
brave --headless=new --no-sandbox --user-data-dir=/tmp/p --remote-debugging-port=9555 \
      --load-extension=$PWD/extension about:blank &
```

rồi điều khiển qua DevTools Protocol: `Input.dispatchMouseEvent` để bôi đen bằng
chuột thật, `DOM.getDocument` với `pierce: true` để nhìn xuyên shadow root `closed`,
và `Runtime.evaluate` trên trang `popup.html` để gọi `chrome.runtime.sendMessage`
đúng như extension gọi.

Hai bẫy khi làm việc này: `window.__x` đặt trong content script **không** thấy được từ
main world (isolated world riêng), và `import()` động **bị cấm** trong service worker
nên không dò module bằng cách đó được.
