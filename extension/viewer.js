// Trinh doc PDF rieng cua extension.
//
// Vi sao can no: PDF mo bang trinh doc san cua Chromium nam trong iframe
// chrome-extension://mhjfbmdgcf.../index.html va noi dung that do plugin PDFium
// ve ra. Extension ben thu ba khong chen duoc content script vao do, va
// window.getSelection() tren trang ngoai luon rong. Da kiem chung bang CDP.
//
// Trang nay ve PDF bang pdf.js kem LOP VAN BAN that (cac <span> trong suot dat
// dung vi tri chu). Nho vay boi den duoc, va content.js — duoc nhung o day nhu
// mot script thuong — cho ra dung cai nut va the dich nhu tren moi trang web.

import * as pdfjsLib from "./vendor/pdfjs/pdf.mjs";

const $ = (id) => document.getElementById(id);
const V = "vendor/pdfjs/";
pdfjsLib.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL(V + "pdf.worker.mjs");

const params = new URLSearchParams(location.search);
const fileUrl = params.get("file") || "";
const debug = params.has("debug");
let pdf = null, scale = 1.25;

function setTip(msg, err = false) {
  $("tip").textContent = msg || "";
  $("tip").classList.toggle("err", err);
  $("tip").style.display = msg ? "" : "none";
}

async function render() {
  $("pages").innerHTML = "";
  $("zoom").textContent = Math.round(scale * 80) + "%";
  for (let n = 1; n <= pdf.numPages; n++) {
    const p = await pdf.getPage(n);
    const viewport = p.getViewport({ scale });

    const wrap = document.createElement("div");
    wrap.className = "page";
    wrap.style.width = `${Math.floor(viewport.width)}px`;
    wrap.style.height = `${Math.floor(viewport.height)}px`;
    // pdf.js 6.x doc --total-scale-factor (ban cu dung --scale-factor). Thieu
    // bien nay thi calc() trong textlayer.css hong -> font-size cua cac span
    // sai -> vung to sang khi boi den lech khoi chu that su ve tren canvas:
    // nhin thay to mot doan nhung copy ra lai duoc doan khac.
    wrap.style.setProperty("--total-scale-factor", String(scale));
    wrap.style.setProperty("--scale-factor", String(scale));   // cho ban pdf.js cu

    const canvas = document.createElement("canvas");
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(viewport.width * ratio);
    canvas.height = Math.floor(viewport.height * ratio);
    canvas.style.width = `${Math.floor(viewport.width)}px`;
    canvas.style.height = `${Math.floor(viewport.height)}px`;
    wrap.appendChild(canvas);

    const layer = document.createElement("div");
    layer.className = "textLayer";
    wrap.appendChild(layer);
    $("pages").appendChild(wrap);

    await p.render({
      canvasContext: canvas.getContext("2d"),
      viewport,
      transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : null,
    }).promise;

    const textLayer = new pdfjsLib.TextLayer({
      textContentSource: await p.getTextContent(),
      container: layer,
      viewport,
    });
    await textLayer.render();

    // pdf.js chia viec nay: THU VIEN ve cac span, con VIEWER phai tu lo phan
    // boi den. Thieu no thi keo chuot hay nhay lung tung sang doan khac va
    // copy ra sai chu.
    //
    // .endOfContent la mot lop khong-chon-duoc nam DUOI cac span. Binh thuong
    // no bi day xuong day (inset:100% 0 0); khi dang keo thi CSS keo no len
    // phu ca trang (.selecting .endOfContent { top:0 }), nho vay trinh duyet
    // co mot be mat lien tuc de tinh vung chon thay vi nhay giua cac span roi rac.
    layer.append(Object.assign(document.createElement("div"), { className: "endOfContent" }));
    layer.addEventListener("mousedown", () => layer.classList.add("selecting"));
  }
}

/** Extension chi co san quyen toi 127.0.0.1 va file://. Voi PDF tren mot trang
 *  web khac, phai xin quyen cho dung origin do — hon la doi <all_urls> tu dau. */
async function ensureAccess(url) {
  let origin;
  try { origin = new URL(url).origin + "/*"; } catch { return true; }
  if (url.startsWith("file:")) return true;          // phu thuoc toggle rieng cua Brave
  if (await chrome.permissions.contains({ origins: [origin] })) return true;

  return new Promise((resolve) => {
    setTip("");
    const box = $("tip");
    box.style.display = "";
    box.textContent = `Cần quyền đọc ${new URL(url).host} để tải PDF. `;
    const btn = document.createElement("button");
    btn.className = "iconbtn";
    btn.textContent = "Cho phép";
    btn.addEventListener("click", async () => {
      // chrome.permissions.request bat buoc phai goi tu mot cu bam that
      resolve(await chrome.permissions.request({ origins: [origin] }));
    });
    box.appendChild(btn);
  });
}

async function open() {
  if (!fileUrl) { setTip("Thiếu tham số ?file=", true); return; }
  $("name").textContent = decodeURIComponent(fileUrl.split("/").pop() || fileUrl);
  $("name").title = fileUrl;
  $("orig").href = fileUrl;

  if (!(await ensureAccess(fileUrl))) {
    setTip("Bạn đã từ chối quyền — không tải được PDF này.", true);
    return;
  }

  setTip("Đang tải PDF…");
  try {
    pdf = await pdfjsLib.getDocument({
      url: fileUrl,
      // pdf.js canh bao ve MOI khiem khuyet cua tai lieu, vd
      // "TT: undefined function: 32" khi font nhung khai dung mot ham hinting
      // ma khong dinh nghia no. Do la loi cua tep PDF, nguoi dung khong sua
      // duoc, va chung lam day trang loi cua extension trong brave://extensions.
      // Chi hien LOI; them ?debug=1 vao URL de xem lai day du.
      verbosity: debug ? pdfjsLib.VerbosityLevel.INFOS : pdfjsLib.VerbosityLevel.ERRORS,
      cMapUrl: chrome.runtime.getURL(V + "cmaps/"),
      cMapPacked: true,
      standardFontDataUrl: chrome.runtime.getURL(V + "standard_fonts/"),
      wasmUrl: chrome.runtime.getURL(V + "wasm/"),
    }).promise;
  } catch (err) {
    const local = fileUrl.startsWith("file:");
    setTip(`Không mở được PDF: ${err.message}.`
         + (local ? ' Với tệp trên máy, vào brave://extensions → "Dịch offline" → '
                  + 'bật "Allow access to file URLs".' : ""), true);
    return;
  }
  setTip(`${pdf.numPages} trang · bôi đen chữ để dịch`);
  await render();
  setTip("");
}

// Nha chuot o bat cu dau cung ket thuc thao tac boi den.
for (const ev of ["pointerup", "mouseup"]) {
  document.addEventListener(ev, () => {
    for (const l of document.querySelectorAll(".textLayer.selecting")) {
      l.classList.remove("selecting");
    }
  });
}

$("zoomin").addEventListener("click", async () => { scale = Math.min(scale * 1.25, 4); await render(); });
$("zoomout").addEventListener("click", async () => { scale = Math.max(scale / 1.25, 0.4); await render(); });

// Dich ca tep: LibreTranslate co endpoint /translate_file nhan .pdf san.
$("whole").addEventListener("click", async () => {
  setTip("Đang dịch cả tệp… (có thể mất một lúc)");
  try {
    const { base, target } = await chrome.storage.sync.get(
      { base: "http://127.0.0.1:5001", target: "vi" });
    const blob = await (await fetch(fileUrl)).blob();
    const form = new FormData();
    form.append("file", blob, $("name").textContent || "document.pdf");
    form.append("source", "auto");
    form.append("target", target);
    const res = await fetch(`${base}/api/translate_file`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok || !data.translatedFileUrl) throw new Error(data.error || `HTTP ${res.status}`);

    $("tip").style.display = "";
    $("tip").textContent = "";
    const a = document.createElement("a");
    a.href = data.translatedFileUrl; a.target = "_blank"; a.rel = "noopener";
    a.className = "iconbtn";
    a.textContent = "Mở bản dịch của cả tệp";
    $("tip").appendChild(a);
  } catch (err) {
    setTip(`Dịch cả tệp thất bại: ${err.message}`, true);
  }
});

open();
