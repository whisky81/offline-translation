# Quyết định thiết kế

Mỗi mục ghi **bối cảnh**, **lựa chọn**, và **cái giá phải trả** — để sau này
đọc lại còn biết vì sao, và biết khi nào nên đổi.

---

## Docker thay vì cài trực tiếp

**Bối cảnh:** máy chỉ có Python 3.14; `libretranslate` ghim `flask==2.2.5`,
`werkzeug==2.3.8` (đời 2023).

**Chọn:** chạy trong Docker. Image mang Python riêng nên miễn nhiễm.

**Giá:** thêm một lớp hạ tầng; phải cô lập khỏi Docker Desktop.

---

## `docker.service` native thay vì Docker Desktop

**Bối cảnh:** máy cài cả hai.

**Chọn:** Docker Engine hệ thống. Desktop chạy container trong VM gắn với phiên
đăng nhập GUI — không có mặt lúc boot nên không làm daemon được.

**Giá:** phải cô lập cấu hình CLI (`DOCKER_CONFIG` riêng), vì `~/.docker/config.json`
của Desktop có `credsStore` và context trỏ vào VM của nó.

---

## systemd giữ vòng đời, compose `restart: "no"`

**Chọn:** một nguồn quyết định duy nhất. Unit chạy `docker compose up
--abort-on-container-exit` ở foreground, `Restart=always` lo dựng lại, log vào
journald.

**Giá:** ba container **bị ghép** — một cái thoát là cả ba dừng. Tự lành, nhưng
lỗi cấu hình nginx cũng kéo API xuống. Chấp nhận được với stack 3 container trên
máy cá nhân.

---

## Hai engine thay vì một

**Bối cảnh:** Argos nhanh và phủ mọi cặp nhưng EN↔VI chỉ ở mức khá; EnViT5 dịch
tiếng Việt tốt hơn rõ rệt nhưng chỉ biết `en↔vi`.

**Chọn:** chạy cả hai, mặc định **Tự chọn**.

**Giá:** thêm ~640 MB đĩa, ~600 MB RAM, và một lớp logic chọn engine — chính lớp
này từng sinh ra [issue #4](issues.md#4-tiếng-nhậthàntrung-bị-dịch-thành-rác-mà-không-báo-lỗi).

**Đã cân nhắc rồi loại:**

| Model | Vì sao loại |
|---|---|
| `facebook/nllb-200-distilled-600M` | Phủ cả 5 ngôn ngữ trong một model, nhưng `cc-by-nc-4.0` — cấm thương mại |
| `vinai/vinai-translate-*-v2` | Chất lượng tốt nhưng `agpl-3.0` lây sang mã của bạn, và cần 2 model cho 2 chiều |
| `Helsinki-NLP/opus-mt-en-vi` | Cùng họ Marian/OPUS với Argos — đổi gần như không được gì |
| LLM qua Ollama | Chất lượng cao nhất nhưng CPU-only thì chậm hơn nhiều bậc |

---

## Nhận diện ngôn ngữ trước, chọn engine sau

**Bối cảnh:** engine có giới hạn cặp mà nhận phải thứ tiếng nó không biết thì
trả về rác **mà không báo lỗi**.

**Chọn:** gọi `/api/detect` trước; `"auto"` không bao giờ khớp engine có giới hạn.

**Giá:** thêm một round-trip (~10 ms) cho mỗi lần dịch khi nguồn là `auto`.
Đáng, vì sai thầm lặng khó phát hiện hơn nhiều so với chậm thêm 10 ms.

---

## nginx phân giải upstream theo từng request

**Chọn:** `resolver 127.0.0.11` + biến trong `proxy_pass`.

**Vì sao:** nginx phân giải tên upstream **một lần lúc nạp config**. Viết cứng
`proxy_pass http://engine:8000` nghĩa là engine chưa tồn tại thì nginx không
khởi động nổi — mất cả UI lẫn API vì một engine phụ.

**Lợi ích phụ:** container tạo lại đổi IP thì nginx bắt kịp.

---

## Không framework, không CDN

**Bối cảnh:** công cụ phải chạy khi mất mạng hoàn toàn.

**Chọn:** DOM thuần cho UI web và extension; pdf.js chép hẳn vào repo.

**Giá:** viết tay nhiều hơn. Bù lại không có bước build, không có `node_modules`,
và có test tự động chặn mọi tham chiếu `https://` lọt vào.

---

## Mọi lệnh gọi mạng của extension nằm ở service worker

**Vì sao:** content script chạy theo origin của *trang*. Trang `https://` gọi
`http://127.0.0.1` sẽ vướng mixed content và Private Network Access. Service
worker chạy theo origin `chrome-extension://` với `host_permissions` nên gọi được.

**Giá:** thêm một chặng nhắn tin. Có test chặn `fetch(` xuất hiện trong content script.

---

## Trình đọc PDF riêng

**Bối cảnh:** trình đọc sẵn của Chromium không cho extension chạm vào nội dung
([issue #13](issues.md#13-không-bắt-được-vùng-bôi-đen-trong-pdf-giới-hạn-của-chromium)).

**Chọn:** ship pdf.js, `viewer.html` nhúng thẳng bộ `content/*.js` nên nút và
thẻ giống hệt trên web.

**Giá:** 5.7 MB vendor. Đổi lại không nhân đôi mã giao diện.

---

## Quyền tuỳ chọn thay vì `<all_urls>` từ đầu

**Chọn:** `host_permissions` chỉ có `127.0.0.1:5001`, `localhost:5001`, `file:///*`.
`<all_urls>` nằm trong `optional_host_permissions`, xin khi người dùng mở PDF ở
tên miền lạ.

**Giá:** thêm một bước bấm *Cho phép*. Đáng, vì extension không cần và không nên
đọc được mọi trang.

---

## Chỉ mở một cổng, chỉ trên loopback

**Bối cảnh:** trước đây cả `:5000` (LibreTranslate) và `:5001` (nginx) đều được
công bố, địa chỉ lấy từ biến `BIND_ADDR` trong `.env`.

**Chọn:** chỉ nginx công bố cổng, địa chỉ `127.0.0.1` **ghi cứng** trong
`docker-compose.yml`. LibreTranslate và engine dùng `expose` — chỉ thấy được
trong mạng nội bộ của compose.

**Vì sao ghi cứng:** một biến trong `.env` là một dòng cách "chỉ máy này" với
"cả mạng LAN". Muốn chia sẻ thì phải sửa chính tệp compose — một hành động có ý thức.

**Giá:** muốn gọi thẳng LibreTranslate để gỡ lỗi thì phải qua `/api`, hoặc
`docker exec`. Chấp nhận được.

---

## Gỡ bỏ `Access-Control-Allow-Origin: *`

**Bối cảnh:** LibreTranslate tự gửi header này cho mọi phản hồi. Với một máy chủ
chạy trên loopback, điều đó có nghĩa: **bất kỳ trang web nào bạn ghé cũng có thể
gọi máy chủ dịch của bạn** từ trình duyệt của bạn.

**Chọn:** `proxy_hide_header` ở nginx, và engine tự viết thì không gửi từ đầu.

**Vì sao không mất gì:** giao diện web cùng origin với `/api` nên CORS không áp
dụng; extension gọi từ service worker với `host_permissions` nên không chịu luật
CORS; `examples/` dùng curl và Python, không phải trình duyệt.

**Giá:** một web app ở origin khác muốn gọi API sẽ phải thêm origin đó vào nginx
một cách tường minh. Đó là điều nên làm.

---

## Tắt giao diện gốc của LibreTranslate

Đã có giao diện riêng ở `:5001` với đầy đủ tính năng. Giữ giao diện gốc chỉ là
thêm một bề mặt (một ứng dụng Vue, các endpoint `/`, `/js/app.js`) mà không ai
dùng. `LT_DISABLE_WEB_UI=true`.

**Giá:** mất một giao diện dự phòng. Swagger ở `/docs/` vẫn còn.

---

## Test ba tầng, trong đó có trình duyệt thật

**Bối cảnh:** đã có lúc bộ test tĩnh xanh hết trong khi extension hỏng hoàn toàn.

**Chọn:** thêm tầng chạy Brave headless điều khiển qua CDP — bôi đen bằng chuột
thật, nhìn xuyên shadow root, **đọc pixel canvas**.

**Giá:** chậm hơn (~60 s cho các test trình duyệt), và cần Brave/Node. Test tự
bỏ qua nếu thiếu. Đây là tầng duy nhất bắt được phần lớn lỗi giao diện trong
[sổ lỗi](issues.md).
