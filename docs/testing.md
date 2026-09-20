# Kiểm thử

## Chạy

```bash
./tests/run.sh            # tất cả
./tests/run.sh setup      # cấu hình project (không cần máy chủ)
./tests/run.sh api        # API + UI gốc
./tests/run.sh web        # UI tiếng Việt + proxy
./tests/run.sh engine     # EnViT5
./tests/run.sh edge       # ca xấu / ca biên
./tests/run.sh ext        # extension
./tests/run.sh pdf        # trình đọc PDF (chạy Brave thật)
./tests/run.sh tts        # máy đọc: API + cách nối dây
./tests/run.sh ttsui      # đọc thành tiếng trong Brave thật
```

Không cần cài gì: `unittest` thư viện chuẩn + Node có sẵn.

## Ba tầng, và vì sao cần cả ba

| Tầng | Kiểm cái gì | Bắt được loại lỗi nào |
|---|---|---|
| **Tĩnh** | manifest, quyền, cấu hình, mã nguồn | Quyền thiếu, phụ thuộc CDN, giá trị `.env` sai |
| **HTTP** | gọi thật vào máy chủ đang chạy | Dịch sai, ca xấu, hợp đồng API |
| **Trình duyệt thật** | nạp extension vào Brave headless, điều khiển bằng CDP | **Mọi thứ còn lại** |

Tầng thứ ba là bài học đắt nhất của dự án: có lúc **bộ test tĩnh xanh hết trong
khi extension hỏng hoàn toàn ngoài đời**. Tĩnh không thấy được ngoại lệ cắt đứt
`boot()`, popup bị đóng nhầm, hay lớp chữ lệch khỏi canvas.

## Những test đáng giá nhất

| Test | Bắt được |
|---|---|
| `test_extension.test_each_used_api_has_its_permission` | `chrome.*` dùng mà thiếu quyền — lỗi **chết lặng lẽ** lúc chạy. Đã bắt được `chrome.scripting` thiếu khai báo |
| `test_web.test_no_uncaught_exceptions_on_load` | Ngoại lệ cắt đứt `boot()` — trang vẫn "trông bình thường" |
| `test_pdf_viewer.test_text_layer_lines_up_with_the_rendered_glyphs` | **Đọc pixel thật trên canvas** so với mép span. Bắt lệch 152 px mà mắt thường khó thấy |
| `test_extension.test_content_script_does_not_fetch` | Gọi mạng sai chỗ → bị chặn trên trang https |
| `test_web.test_no_external_resources` | Một `<script src="https://…">` lọt vào là mất tính offline |
| `test_setup.test_user_docker_config_left_untouched` | Project lỡ tay sửa cấu hình Docker Desktop của người dùng |
| `test_tts.test_hai_ban_tts_js_giong_het_nhau` | So sánh **từng byte** `web/html/js/tts.js` với `extension/tts.js`. Hai bản sao là chỗ dễ trôi khỏi nhau nhất: sửa bug một bên, bên kia vẫn hỏng |
| `test_tts.test_content_script_khong_tu_phat_am_thanh` | Chặn `new Audio` lọt vào content script → sẽ dính CSP `media-src` của trang |
| `test_tts_browser.test_nhan_tu_tro_ve_khi_doc_xong` | Đường báo ngược offscreen → SW → tab. Đứt là nút kẹt ở "Dừng" vĩnh viễn, và **không tầng nào khác thấy được** |
| `test_tts_browser.test_khong_co_loi_console` | Đã bắt được [issue #29](issues.md) — promise tải trước bị huỷ |

## Cách viết test mới

**Dùng `tests/support.py`** — đừng viết lại `_env`/`http`/multipart:

```python
from tests.support import WEB, translate, request, multipart

r = translate(WEB + "/api", "Good morning", "vi", "en")
self.assertEqual(r.status, 200)
self.assertTrue(r.json()["translatedText"])
```

`request()` **luôn** trả `Response` kể cả khi mã ≥ 400 — test cần kiểm tra cả
trường hợp bị từ chối, nên lỗi HTTP là dữ liệu chứ không phải ngoại lệ.

**Test trình duyệt** dùng `tests/browser.py` + `tests/cdp.mjs`:

```python
from tests import browser
with browser.brave(9799, extension=EXT):
    result = browser.run_driver(ROOT / "tests" / "e2e_xxx.mjs", 9799, ...)
```

Driver là script Node in **một dòng JSON**; phía Python chỉ khẳng định trên dữ
liệu đó. Lớp `Page` trong `cdp.mjs` lo phần khó: bôi đen bằng chuột thật, nhìn
xuyên shadow root `closed`, đọc hộp bao.

## Bẫy khi viết test trình duyệt

Những cái này đã làm tôi mất thời gian, ghi lại để bạn khỏi vấp:

- **Isolated world**: content script chạy trong thế giới JS riêng. `Runtime.evaluate`
  chạy ở main world nên **không thấy** biến của content script. Chỉ DOM là chung.
- **Shadow root `closed`**: không truy cập được bằng JS. Phải dùng
  `DOM.getDocument({pierce: true})`.
- **`mouseReleased` phải kèm `buttons: 0`** — nếu không, trình duyệt coi như nút
  vẫn đang giữ và `mouseup` không hoàn tất.
- **`import()` động bị cấm trong service worker** — không dò module bằng cách đó được.
- **Chờ đúng thứ**: chờ "thẻ hiện ra" là sai, vì thẻ hiện ngay ở trạng thái
  *đang dịch*. Phải chờ **có bản dịch thật**.
- **Phiên trình duyệt sạch**: gộp nhiều kịch bản vào một phiên khiến chúng can
  nhiễu nhau (thẻ đang mở che đúng vùng chữ sắp kéo qua). Đó là lý do
  `e2e_pdf.mjs` và `e2e_pdf_select.mjs` tách riêng.
- **`pkill -f` tự giết mình**: mẫu khớp cả dòng lệnh của shell đang chạy. Neo vào
  đường dẫn binary: `pgrep -f '^/opt/brave\.com/brave/brave'`.
- **Cuộn trước khi bấm**: cửa sổ headless mặc định chỉ **740×443**. Phần tử nằm
  dưới mép vẫn cho `getBoundingClientRect()` hợp lệ, nhưng bấm vào toạ độ ngoài
  khung nhìn thì không trúng gì — và trông y hệt một tính năng hỏng
  ([issue #31](issues.md)). Gọi `scrollIntoView({block:'center'})` rồi **đo lại**.
- **Âm thanh của extension không nằm trong trang**: nó phát ở tài liệu offscreen,
  nên không probe được từ `Runtime.evaluate` của tab. Bằng chứng thay thế: số mục
  trong bộ đệm `/api3/info` tăng lên, và `offscreen.html` xuất hiện trong danh
  sách target.
- **Văn bản trùng lần chạy trước sẽ ăn bộ đệm** của máy đọc và trả về sau 8 ms —
  không chứng minh được gì. Chèn `Date.now()` vào văn bản thử.

## Ca biên đã phủ

`tests/test_edge_cases.py` — mọi khẳng định đều đo từ máy chủ thật:

- `q` rỗng / chỉ khoảng trắng / mảng rỗng / không phải chuỗi
- `target` thiếu, ngôn ngữ không tồn tại, format lạ
- JSON hỏng, sai content-type
- Chỉ dấu câu, một từ 600 ký tự, emoji thuần, ký tự điều khiển
- Mảng 120 phần tử, đoạn văn 3000 ký tự
- EnViT5: cặp không hỗ trợ, nguồn trùng đích, CJK với `auto`
- Tệp rỗng, đuôi lạ, không có đuôi
- Đặt vị trí popup: vùng chọn to hơn khung nhìn, kích thước 0, thẻ to hơn màn hình
- Chọn engine: khoá lạ, `auto` với engine giới hạn, `zh` alias
- Máy đọc: `q` sai kiểu (số, mảng, bool, null), `speed` sai kiểu, `speed` ngoài
  khoảng (kẹp lại), ngôn ngữ chưa có giọng, id giọng không tồn tại, chuỗi không
  có chữ nào, ký tự điều khiển, văn bản vượt `TTS_MAX_CHARS`, thân không phải
  đối tượng JSON
