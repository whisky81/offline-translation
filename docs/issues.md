# Sổ lỗi

Mọi lỗi đã gặp trong quá trình xây dựng, kèm **nguyên nhân gốc** và **cách sửa**.
Ghi lại để không lặp lại, và để biết vì sao code trông như hiện tại.

Mỗi mục có test chặn hồi quy — cột cuối ghi tên test.

---

## Nhóm A — Lỗi tôi gây ra trong cấu hình

### 1. Web UI "gõ không dịch" — `LT_FRONTEND_TIMEOUT`

| | |
|---|---|
| **Triệu chứng** | Gõ vào UI gốc `:5000` nhưng không ra bản dịch |
| **Nguyên nhân** | Tên biến nghe như timeout của request, thực ra là **độ trễ debounce trước khi gửi**: `setTimeout(() => request.send(data), frontendTimeout)`. Tôi đặt `60000` → UI đợi **60 giây** sau khi ngừng gõ |
| **Cách sửa** | Đặt về `500` (mặc định gốc của LibreTranslate) |
| **Bài học** | Không suy ra ngữ nghĩa từ tên biến — đọc mã dùng nó |
| **Test** | `test_setup.test_frontend_timeout_is_a_debounce_not_a_request_timeout` |

### 2. Ô nguồn khoá ở tiếng Anh

| | |
|---|---|
| **Triệu chứng** | Gõ tiếng Việt vào UI, ra kết quả rác |
| **Nguyên nhân** | Tôi đặt `LT_FRONTEND_LANGUAGE_SOURCE=en`; mặc định gốc là `auto` |
| **Cách sửa** | Trả về `auto` |
| **Test** | `test_api.TestWebUI.test_frontend_source_is_auto_detect` |

Cùng đợt còn `LT_BATCH_LIMIT=64` (mặc định `-1`) — tôi tự giới hạn vô cớ.

### 3. `<html lang="None">`

| | |
|---|---|
| **Nguyên nhân** | Template render `{{ current_locale }}`; `get_locale()` rơi về `Accept-Language`, không có header đó thì trả `None` và Jinja in thẳng chữ `"None"` |
| **Cách sửa** | Đặt `LT_FRONTEND_LANGUAGE=en` |
| **Ghi chú** | Mã `vi` **không dùng được** — chỉ 24/66 locale được chấp nhận, `vi` bị lọc vì bản dịch giao diện chưa đủ hoàn chỉnh |
| **Test** | `test_web.TestStockUiLangAttribute` |

---

## Nhóm B — Sai thầm lặng (nguy hiểm nhất)

### 4. Tiếng Nhật/Hàn/Trung bị dịch thành rác mà không báo lỗi

| | |
|---|---|
| **Triệu chứng** | Bôi đen tiếng Nhật, đích `vi` → nhận về `":"`. **Không có lỗi nào** |
| **Nguyên nhân gốc** | `engineHandles()` coi `source: "auto"` là khớp **mọi** cặp, nên EnViT5 (chỉ `en↔vi`) được chọn. Engine dùng heuristic *"không có dấu tiếng Việt ⇒ tiếng Anh"* nên dịch tiếng Nhật như tiếng Anh |
| **Cách sửa** | Hai lớp: (a) gọi `/api/detect` để biết ngôn ngữ thật **trước** khi chọn engine, và `"auto"` không bao giờ khớp engine có giới hạn cặp; (b) `engine/server.py` từ chối thẳng khi thấy chữ Hán/Kana/Hangul mà `source=auto` |
| **Bài học** | Sai thầm lặng khó phát hiện hơn nhiều so với báo lỗi — thà từ chối còn hơn đoán |
| **Test** | `test_extension.TestEngineSelectionSafety`, `test_edge_cases.test_cjk_with_auto_source_is_refused_not_guessed` |

### 5. Dịch `vi → vi` trả lại y nguyên đầu vào

| | |
|---|---|
| **Triệu chứng** | Bôi đen tiếng Việt khi đích là `vi` → kết quả giống hệt, trông như hỏng |
| **Nguyên nhân** | Không ai xử lý trường hợp nguồn trùng đích |
| **Cách sửa** | Tự đổi chiều sang ngôn ngữ đối ứng, ghi rõ *"đã là vi, dịch sang en"*. UI cũng vô hiệu hoá lựa chọn trùng nguồn |
| **Test** | `test_web.test_same_language_flips_instead_of_echoing` |

### 6. Bản vá `str.replace` âm thầm không khớp

| | |
|---|---|
| **Triệu chứng** | Tôi tưởng đã sửa xong lỗi #4, nhưng footer vẫn báo LibreTranslate ở cặp lẽ ra dùng EnViT5 |
| **Nguyên nhân** | Chuỗi tìm kiếm viết `da cat con` (không dấu) còn file có `đã cắt còn`. `str.replace` không khớp thì **không báo gì** |
| **Cách sửa** | Dùng `assert` sau mọi phép thay thế, hoặc định vị theo chỉ số |
| **Bài học** | Mọi phép sửa file bằng script phải tự kiểm chứng |

---

## Nhóm C — Lỗi giao diện

### 7. Bản dịch hiện ra rồi biến mất ngay

| | |
|---|---|
| **Triệu chứng** | Bấm Dịch, thẻ hiện một chớp rồi mất |
| **Nguyên nhân gốc** | `run()` ẩn nút ngay ở `mousedown`. Đến lúc **nhả** chuột, chỗ đó không còn nút nên `mouseup` rơi xuống **trang** bên dưới → `composedPath()` không chứa shadow host → handler tưởng vừa bôi đen chỗ khác → `showBubble()` → hàm này gọi `hideCard()`. EnViT5 trả về trong ~130 ms nên kết quả kịp hiện rồi bị xoá |
| **Cách sửa** | Bỏ qua đúng một `mouseup` sau cú bấm nút (`skipNextMouseup`) |
| **Test** | `test_extension.TestPopupPlacement.test_card_survives_a_slow_click` (giữ chuột 400 ms) |

### 8. Bản dịch biến mất khi cuộn trang

| | |
|---|---|
| **Triệu chứng** | Vẫn mất thẻ dù đã sửa #7 — phải bấm Dịch lại |
| **Nguyên nhân** | Listener `scroll` đóng **cả thẻ**. Trên touchpad chỉ cần hai ngón nhích nhẹ là cuộn — đọc PDF thì gần như không tránh được |
| **Cách sửa** | Cuộn chỉ ẩn **nút** (nó neo theo vùng chọn nên sẽ lệch chỗ); thẻ giữ nguyên, nó `position: fixed` nên không trôi. Đóng bằng `Esc` / ✕ / bấm ra ngoài |
| **Ghi chú** | Sự kiện `scroll` **không nổi bọt** nhưng **có** đi qua pha capture của `window` — đó là lý do listener bắt được nó |
| **Test** | `test_pdf_viewer.TestPdfSelection.test_scrolling_does_not_close_the_translation` |

### 9. Bấm `Esc` lúc đang dịch không huỷ được

| | |
|---|---|
| **Triệu chứng** | Đóng thẻ xong vài trăm ms sau nó tự bật lại |
| **Nguyên nhân** | Kết quả về muộn vẫn gọi `renderResult()` |
| **Cách sửa** | Mỗi lần dịch mang một số thứ tự; đóng thẻ tăng số đó lên, kết quả của lần đã huỷ không còn được vẽ |
| **Test** | `test_pdf_viewer.test_escape_cancels_a_translation_in_flight` |

### 10. Popup che mất chữ đang đọc

| | |
|---|---|
| **Nguyên nhân** | Đặt ngay dưới vùng chọn — trên PDF dày chữ thì nuốt mất dòng kế tiếp |
| **Cách sửa** | Ưu tiên **cạnh bên** vùng chọn (lề trang PDF, cột hẹp trên web), rồi mới dưới, rồi trên. Đo kích thước thật sau khi vẽ xong mới định vị, thay vì đoán 380×240 |
| **Test** | `test_extension.TestPopupPlacement.test_card_never_leaves_the_viewport` |

### 11. Emoji 🗣️ ra ô vuông trống

Thiếu font emoji thì glyph không render. **Sửa:** dùng SVG nội tuyến.

### 12. Bôi đen trong `<textarea>` không hiện nút

| | |
|---|---|
| **Nguyên nhân** | `window.getSelection()` **có** trả về chữ, nhưng `getRangeAt(0).getBoundingClientRect()` rỗng vì vùng chọn nằm trong shadow tree của ô nhập → `rect` null → không hiện nút |
| **Cách sửa** | Khi rect rỗng thì lấy khung của chính ô nhập |
| **Test** | `test_extension` (QA tương tác) |

---

## Nhóm D — PDF

### 13. Không bắt được vùng bôi đen trong PDF — giới hạn của Chromium

| | |
|---|---|
| **Đo được** | `contentType: application/pdf`, body trang ngoài **rỗng**, nội dung nằm trong iframe `chrome-extension://mhjfbmdgcf…/index.html`, `window.getSelection()` sau `Ctrl+A` trả `""` |
| **Nguyên nhân** | PDF do PDF Viewer nội bộ (một extension khác) + plugin PDFium render. Extension bên thứ ba không chèn content script vào origin `chrome-extension://` của extension khác |
| **Cách giải quyết** | Ship trình đọc PDF riêng bằng pdf.js; `viewer.html` nhúng thẳng bộ `content/*.js` nên nút và thẻ giống hệt trên web |
| **Không phải bug** | Đây là ràng buộc của trình duyệt, ghi lại để khỏi tìm lại |

### 14. Bôi đen trong PDF nhảy sang đoạn khác, copy ra sai chữ

| | |
|---|---|
| **Nguyên nhân gốc** | pdf.js **chia việc**: *thư viện* vẽ các span, *viewer* lo phần bôi đen. Tôi tự viết viewer nên thiếu hẳn nửa sau. Đo được: `document.querySelectorAll('.endOfContent').length` = **0** |
| **Cách sửa** | Thêm `.endOfContent` (lớp không-chọn-được nằm **dưới** các span) vào mỗi lớp chữ, và bật/tắt class `selecting` theo thao tác kéo — đúng cách `TextLayerBuilder` chính thức làm. Khi đang kéo, CSS kéo `.endOfContent` lên phủ cả trang để trình duyệt có bề mặt liền mạch |
| **Test** | `test_pdf_viewer.test_each_text_layer_has_an_end_of_content`, `test_multiline_selection_is_contiguous` |

### 15. Vùng tô sáng không khớp chữ — **sai tên biến CSS**

| | |
|---|---|
| **Triệu chứng** | Tô sáng không phủ hết chữ, nhưng copy lại lấy cả phần trông như chưa chọn |
| **Nguyên nhân gốc** | pdf.js 6.x đọc **`--total-scale-factor`**; tôi đặt tên đời cũ `--scale-factor`. Thiếu biến thì `calc()` trong `textlayer.css` hỏng → `font-size` của span rơi về mặc định |
| **Số đo** | Hỏng: font 14px, bề rộng 219/288/353. Đúng: font 20px, bề rộng 312/411/505 → span **ngắn hơn chữ thật tới 152 px** |
| **Cách sửa** | Đặt `--total-scale-factor` (giữ cả tên cũ cho bản pdf.js đời trước) |
| **Test** | `test_pdf_viewer.test_text_layer_lines_up_with_the_rendered_glyphs` — **đọc pixel thật trên canvas**, lệch hiện tại 1 px. Đã chứng minh nó bắt được lỗi: bỏ biến đi thì test báo lệch −72 px |

---

## Nhóm E — Hạ tầng

### 16. Docker Desktop chiếm cấu hình CLI

| | |
|---|---|
| **Triệu chứng** | Lệnh `docker` hỏng khi Docker Desktop không chạy |
| **Nguyên nhân** | `~/.docker/config.json` có `"credsStore": "desktop"` (mọi lệnh gọi `docker-credential-desktop`), `"currentContext": "desktop-linux"` (trỏ vào VM của Desktop), và hook plugin chèn vào `compose up` |
| **Cách sửa** | **Không sửa file của người dùng.** Project có `docker-config/` riêng; `scripts/_docker-env.sh` đặt `DOCKER_HOST` + `DOCKER_CONFIG`, systemd unit nhận cùng hai biến |
| **Test** | `test_setup.TestDockerIsolation` — gồm một test khẳng định `~/.docker/config.json` **không** bị thay đổi |

### 17. Container `lt-web` báo unhealthy

| | |
|---|---|
| **Nguyên nhân** | `/etc/hosts` trong container có cả `::1 localhost`; nginx chỉ bind `0.0.0.0:80` (IPv4). Healthcheck gọi `http://localhost/` → busybox `wget` thử IPv6 trước → `Connection refused` |
| **Cách sửa** | Thêm `listen [::]:80;` (sửa gốc) **và** đổi healthcheck sang `127.0.0.1` (bỏ phụ thuộc thứ tự phân giải tên) |
| **Test** | `test_web.test_nginx_listens_on_ipv6_too` |

### 18. nginx không khởi động nổi khi engine chưa tồn tại

| | |
|---|---|
| **Nguyên nhân** | nginx phân giải tên upstream **một lần lúc nạp config**. `proxy_pass http://engine:8000` mà container `engine` chưa có → nginx chết → mất cả UI lẫn API |
| **Cách sửa** | `resolver 127.0.0.11` + biến trong `proxy_pass` → phân giải theo từng request. Engine tắt chỉ trả 502. Lợi ích phụ: container tạo lại đổi IP thì nginx bắt kịp |
| **Test** | `test_web.test_upstreams_are_resolved_at_request_time` |

### 19. "Extension context invalidated"

| | |
|---|---|
| **Triệu chứng** | Sau khi bấm ⟳ ở `brave://extensions`, bấm Dịch ra lỗi này |
| **Nguyên nhân** | Chrome/Brave **không tự chèn lại** content script vào tab đang mở. Script cũ mất kết nối với service worker |
| **Cách sửa** | Ba lớp: (a) thông báo dễ hiểu *"Tải lại trang (Ctrl+R)"*; (b) tự chèn lại vào tab có quyền (`127.0.0.1:5001`, `file://`), dùng `chrome.storage.session` làm cờ để chèn **một lần mỗi lần nạp** chứ không phải mỗi lần SW thức dậy; (c) bản mới gọi `window.__dichOfflineCleanup()` của bản cũ — mọi listener gắn `AbortController` nên gỡ sạch một lệnh |
| **Test** | `test_pdf_viewer.test_reinjecting_replaces_instead_of_duplicating` |

---

## Nhóm F — Tìm thấy khi refactor

### 20. `q` là số làm engine trả 502

| | |
|---|---|
| **Triệu chứng** | `POST /api2/translate` với `{"q": 123}` → **502 Bad Gateway** |
| **Nguyên nhân gốc** | `engine/server.py` làm `list(q)`; với `int` thì `TypeError` không ai bắt → handler chết → nginx thấy kết nối đứt → 502 |
| **Cách sửa** | Kiểm tra `q` phải là chuỗi hoặc mảng chuỗi, trả 400 nếu không. Thêm `try/except` bao `do_POST` để lỗi lập trình thành 500 có thân JSON thay vì 502 |
| **Test** | `test_edge_cases.test_non_string_q_is_rejected_not_crashed` |

### 21. Phần tử rỗng trong mảng sinh ra `":"`

| | |
|---|---|
| **Nguyên nhân** | EnViT5 nhận `"en: "` (tiền tố mà không có nội dung) và sinh ra rác |
| **Cách sửa** | Bỏ qua phần tử rỗng, giữ nguyên vị trí trong mảng kết quả |
| **Test** | `test_edge_cases.test_empty_items_are_preserved_not_turned_into_junk` |

### 22. `pickEngine` với giá trị lạ làm hỏng cả lần dịch

| | |
|---|---|
| **Nguyên nhân** | `ENGINES[pref].name` với `pref` không tồn tại → `TypeError`. Xảy ra nếu storage còn giá trị cũ từ bản trước |
| **Cách sửa** | Dùng optional chaining, bỏ phần ghi chú nếu không biết tên engine |
| **Ghi chú** | Cùng loại với lỗi `ENGINES["auto"].name` từng **cắt đứt `boot()`** của UI web giữa chừng — trang trông vẫn bình thường nhưng nút đảo chiều và danh sách ngôn ngữ không bao giờ cập nhật |
| **Test** | `test_edge_cases.TestEngineSelectionEdges` |

### 23. WebAssembly bị CSP chặn trong trình đọc PDF

| | |
|---|---|
| **Triệu chứng** | Console báo `#instantiateWasm: CompileError: … violates the following Content Security policy directive because neither 'wasm-eval' nor 'unsafe-eval' is an allowed source … "script-src 'self'"` |
| **Nguyên nhân gốc** | CSP mặc định của trang extension MV3 là `script-src 'self'`, **cấm WebAssembly**. pdf.js dùng WASM cho **JBIG2** (nén ảnh trong PDF quét), **OpenJPEG** (JPEG2000) và **QCMS** (quản lý màu) |
| **Vì sao không thấy sớm** | PDF chỉ có chữ không cần WASM nên test cũ không chạm tới. Chỉ PDF có ảnh (đặc biệt là **PDF quét**) mới kích hoạt |
| **Cách sửa** | Khai `"content_security_policy": {"extension_pages": "script-src 'self' 'wasm-unsafe-eval'; object-src 'self'"}`. `wasm-unsafe-eval` **chỉ** mở WebAssembly, không mở `eval()` cho chuỗi JavaScript — đây là mức tối thiểu pdf.js cần |
| **Test** | `test_pdf_viewer.test_webassembly_is_permitted` (chạy thật trong trang extension), `test_csp_allows_wasm_but_not_eval` (tĩnh, cũng chặn `'unsafe-eval'` lọt vào) |

### 24. `TT: undefined function: 32` làm đầy trang lỗi của extension

| | |
|---|---|
| **Triệu chứng** | `brave://extensions` liệt kê warning này mỗi lần mở PDF |
| **Nguyên nhân gốc** | Font nhúng trong PDF **khai dùng** hàm hinting TrueType số 32 nhưng **không định nghĩa** nó. pdf.js đặt `hintsValid = false` rồi vẽ tiếp — lỗi của tệp PDF, không phải của ta, và chữ vẫn ra đủ (đo thật: 72 trang, 4888 span) |
| **Vì sao vẫn phải xử lý** | Người dùng không sửa được tệp PDF, mà danh sách warning làm extension trông như đang hỏng |
| **Cách sửa** | `getDocument({ verbosity: VerbosityLevel.ERRORS })` — nó truyền cả sang worker. `setVerbosityLevel` không có trong API công khai của pdf.js 6.3.289, phải đi qua tham số của `getDocument`. Thêm `?debug=1` vào URL để bật lại mức đầy đủ khi cần chẩn đoán |
| **Test** | `test_pdf_viewer.test_no_console_warnings`, `test_viewer_quiets_document_warnings_but_keeps_errors` |

### 25. `Access-Control-Allow-Origin: *` cho phép mọi trang web dùng máy chủ của bạn

| | |
|---|---|
| **Triệu chứng** | Không có triệu chứng — phát hiện khi rà bề mặt tấn công |
| **Nguyên nhân** | LibreTranslate gửi `Access-Control-Allow-Origin: *` cho mọi phản hồi. Máy chủ chạy trên loopback nhưng **trình duyệt của bạn** thì đến được nó, nên một trang web bất kỳ có thể dùng nó làm dịch vụ dịch miễn phí, và biết được bạn đang chạy nó |
| **Cách sửa** | `proxy_hide_header` ở nginx cho cả `/api` và `/api2`; engine tự viết thì bỏ hẳn. Ngừng công bố cổng `:5000` để không ai đi vòng qua proxy |
| **Vì sao không mất gì** | UI web cùng origin, extension gọi từ service worker (không chịu CORS), examples dùng curl |
| **Test** | `test_api.TestNoWildcardCors`, `test_engine.test_no_wildcard_cors`, và `scripts/verify.sh` mục [8] |

### 26. Symlink trong `docker-config/` không di động

| | |
|---|---|
| **Triệu chứng** | Chưa gặp — thấy khi chuẩn bị đẩy lên GitHub |
| **Nguyên nhân** | `docker-config/cli-plugins/` chứa symlink tới `/usr/libexec/docker/cli-plugins/…`. Đường dẫn này khác nhau giữa các bản phân phối; clone sang máy khác sẽ thành symlink chết và `docker compose` hỏng |
| **Cách sửa** | Đưa vào `.gitignore`; `scripts/_docker-env.sh` tự tạo lại, dò qua các đường dẫn hệ thống thường gặp |
| **Test** | `test_setup.test_compose_plugin_is_docker_ce_build` tự tạo trước khi kiểm, và bỏ qua nếu máy không có docker-ce |

### 27. `speechSynthesis` của trình duyệt không có giọng nào

| | |
|---|---|
| **Triệu chứng** | Phát hiện trước khi viết dòng mã nào: `speechSynthesis.getVoices()` trong Brave trả về `{"count": 0, "sample": [], "vi": []}` |
| **Nguyên nhân gốc** | Chromium trên Linux **không kèm giọng nào**. Nó đi mượn `speech-dispatcher` của hệ thống, mà trên máy này `speech-dispatcher` đang `inactive` và thiếu luôn engine espeak-ng (module `sd_espeak-ng` có mặt nhưng binary `espeak-ng` thì không) |
| **Vì sao nguy hiểm** | Đây là kiểu hỏng tệ nhất: `speak()` không ném lỗi, không trả về gì, chỉ **im lặng**. Nút Đọc sẽ trông như bình thường và người dùng không có manh mối nào |
| **Cách sửa** | Bỏ hẳn hướng đi này. Tổng hợp ở máy chủ (Piper) rồi trả về WAV — nghe được bất kể máy có cài gì |
| **Test** | `test_tts.TestTtsService.test_doc_tieng_viet_ra_wav_that`, `test_tts_browser.test_bam_doc_thi_goi_may_chu_va_phat_that` |

### 28. Văn bản không phát âm được cho ra tệp WAV rỗng

| | |
|---|---|
| **Triệu chứng** | Đọc `"... !!! ???"` hoặc `"🙂🙂🙂"` trả về HTTP 200 với một tệp WAV chỉ có phần header. Bấm Đọc, không nghe gì, không báo gì |
| **Nguyên nhân gốc** | Piper nhận chuỗi không có âm vị nào thì sinh ra 0 mẫu, nhưng vẫn là một tệp WAV hợp lệ |
| **Cách sửa** | Hai lớp: từ chối sớm bằng `_SPEAKABLE = re.compile(r"[^\W_]")` (phải có ít nhất một chữ cái hoặc chữ số), và kiểm `getnframes() == 0` sau khi tổng hợp rồi trả 400 kèm lời khuyên |
| **Bài học** | Với API trả về nhị phân, "200 + thân rỗng" là cái bẫy. Phải đọc lại chính tệp vừa tạo chứ không tin rằng gọi hàm xong là xong |
| **Test** | `test_tts.TestTtsBadInput.test_van_ban_khong_co_chu` (4 chuỗi khác nhau) |

### 29. Đoạn tải trước bị huỷ làm nổi `Uncaught (in promise)`

| | |
|---|---|
| **Triệu chứng** | Bấm Đọc rồi bấm Dừng giữa chừng → console báo `Uncaught (in promise)` tại `tts.js`. Chức năng vẫn chạy đúng |
| **Ai tìm ra** | Tầng test trình duyệt (`test_tts_browser.test_khong_co_loi_console`) — hai tầng kia đều xanh |
| **Nguyên nhân gốc** | `Reader.play()` bắt đầu tải đoạn `i+1` **trước khi** phát đoạn `i`. Dừng giữa chừng thì vòng lặp thoát ra và bỏ lại promise đó đang bay; `ctl.abort()` làm nó bị từ chối, mà không còn ai `await` nữa |
| **Cách sửa** | `p.catch(() => {})` ngay sau khi tạo: promise dẫn xuất này đánh dấu `p` là đã xử lý, còn `p` gốc vẫn ném lỗi bình thường cho chỗ nào thật sự `await` nó |
| **Bài học** | Mọi mẫu "tải trước" đều sinh ra promise có thể không bao giờ được tiêu thụ. Cứ có `abort()` là phải nghĩ tới chúng |
| **Test** | `test_tts_browser.TestReaderOnWebUi.test_khong_co_loi_console` |

### 30. onnxruntime ghi cảnh báo telemetry mỗi lần khởi động

| | |
|---|---|
| **Triệu chứng** | `[W:onnxruntime:Default, telemetry.cc:800] Failed to persist telemetry device ID; using an in-memory identifier` trong log container |
| **Nguyên nhân gốc** | onnxruntime cố ghi một "telemetry device ID" vào `$HOME` lúc `import`, nhưng user hệ thống `tts` tạo bằng `useradd --system` nên `/home/tts` không tồn tại |
| **Cách sửa đã CÂN NHẮC rồi bỏ** | Đặt `HOME=/tmp` cũng làm hết cảnh báo — nhưng nó hết vì việc ghi **thành công**, để lại một định danh máy trong `/tmp/.cache/Microsoft`. Với một công cụ offline thì đó là bước lùi |
| **Cách sửa đã chọn** | `ENV ORT_DISABLE_TELEMETRY=1` trong `tts/Dockerfile` — tắt hẳn, không sinh và không lưu định danh nào |
| **Bài học** | Cảnh báo im đi không có nghĩa là vấn đề đã hết. Phải hỏi *vì sao* nó im |

### 31. Nút Đọc ở ô bản dịch "không hoạt động" — hoá ra là lỗi của test

| | |
|---|---|
| **Triệu chứng** | Driver CDP báo bấm nút Đọc ở ô bản dịch cho `speaks: 0`, `plays: []`, nhãn không đổi. Nút ở ô gốc thì chạy bình thường |
| **Nguyên nhân gốc** | **Không phải lỗi ứng dụng.** Cửa sổ Brave headless mặc định chỉ 740×443; ô bản dịch nằm dưới mép dưới. `getBoundingClientRect()` vẫn trả toạ độ hợp lệ, nhưng `Input.dispatchMouseEvent` ở `y` ngoài khung nhìn thì không trúng gì cả |
| **Cách sửa** | Hàm `centerOf()` trong driver gọi `scrollIntoView({block:'center'})` rồi **đo lại** rect trước khi bấm |
| **Bài học** | Bổ sung vào danh sách sai lầm khi viết test CDP trong [`testing.md`](testing.md). Một cú bấm không trúng trông y hệt một tính năng hỏng |

---

## Hạn chế của upstream (không sửa được từ đây)

| Vấn đề | Chi tiết |
|---|---|
| `q` là số → **HTTP 500** | LibreTranslate trả lỗi nội bộ thay vì 400. Mọi client trong dự án đều gửi chuỗi nên không ảnh hưởng. Có test ghi nhận — nếu bản mới sửa thì test đỏ và ta cập nhật tài liệu |
| Không có giao diện tiếng Việt | `vi` không nằm trong 24 locale được chấp nhận |
| `.xlsx` không dịch được | Argos chỉ hỗ trợ `.txt .odt .odp .docx .pptx .epub .html .srt .pdf` |
| Tệp rỗng vẫn trả link | Không coi là lỗi, trả về tệp "đã dịch" rỗng |
