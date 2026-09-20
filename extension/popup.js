import { DEFAULTS, ENGINES, engineAvailable, fetchLanguages, getSettings } from "./common.js";

const $ = (id) => document.getElementById(id);
const LANG_NAMES = { vi: "Tiếng Việt", en: "Tiếng Anh", "zh-Hans": "Tiếng Trung",
                     zh: "Tiếng Trung", ja: "Tiếng Nhật", ko: "Tiếng Hàn" };

let settings = DEFAULTS;

function setStatus(msg, cls = "") { $("status").textContent = msg; $("status").className = "status " + cls; }

async function init() {
  settings = await getSettings();

  $("engine").append(new Option("Tự chọn (EnViT5 cho EN↔VI)", "auto"));
  for (const [k, e] of Object.entries(ENGINES)) $("engine").append(new Option(e.name, k));
  $("engine").value = settings.engine;

  try {
    const langs = await fetchLanguages(settings.base);
    for (const l of langs) $("target").append(new Option(LANG_NAMES[l.code] || l.name, l.code));
    $("health").className = "dot on";
    setStatus(`Máy chủ hoạt động · ${langs.length} ngôn ngữ`, "ok");
  } catch (err) {
    $("health").className = "dot off";
    setStatus(`Không gọi được ${settings.base} — máy chủ đang chạy chứ? (${err.message})`, "err");
    for (const [c, n] of Object.entries(LANG_NAMES)) $("target").append(new Option(n, c));
  }
  $("target").value = settings.target;

  if (!(await engineAvailable(settings.base))) {
    const opt = $("engine").querySelector('option[value="hf"]');
    if (opt) opt.disabled = true;
    if (settings.engine === "hf") $("engine").value = "auto";
  }

  // Mo popup khi dang boi den san -> nap luon vao o nhap.
  // activeTab cho phep doc url cua dung tab nay ma khong can quyen "tabs".
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  // Tren PDF, trinh doc san cua Chromium khong cho doc vung boi den -> moi
  // nguoi dung sang trinh doc rieng.
  if (tab?.url && /\.pdf(\?|#|$)/i.test(tab.url)) {
    $("pdfbar").hidden = false;
    $("openpdf").addEventListener("click", () => {
      chrome.tabs.create({
        url: chrome.runtime.getURL(`viewer.html?file=${encodeURIComponent(tab.url)}`),
      });
      window.close();
    });
    setStatus("Đây là PDF — bôi đen chỉ hoạt động trong trình đọc riêng.", "");
  }

  if (tab?.id != null) {
    try {
      const [{ result }] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => window.getSelection()?.toString() || "",
      });
      if (result?.trim()) { $("text").value = result.trim(); go(); }
    } catch { /* trang khong cho chen script (chrome://, store...) */ }
  }
}

async function go() {
  const q = $("text").value.trim();
  if (!q) { setStatus("Chưa có gì để dịch.", "err"); return; }
  $("out").textContent = "…";
  setStatus("Đang dịch…");
  const res = await chrome.runtime.sendMessage({
    type: "translate", q,
    override: { engine: $("engine").value, target: $("target").value },
  });
  if (!res?.ok) { $("out").textContent = ""; setStatus(res?.error || "Không rõ lỗi", "err"); return; }
  $("out").textContent = res.text;
  setStatus(`${res.engine}${res.detected ? " · nhận ra " + res.detected : ""} · ${res.ms} ms`
            + (res.note ? ` · ${res.note}` : ""), "ok");
}

$("go").addEventListener("click", go);
$("text").addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") go();
});
$("engine").addEventListener("change", () => chrome.storage.sync.set({ engine: $("engine").value }));
$("target").addEventListener("change", () => chrome.storage.sync.set({ target: $("target").value }));
$("copy").addEventListener("click", async () => {
  if (!$("out").textContent) return;
  try { await navigator.clipboard.writeText($("out").textContent); setStatus("Đã chép.", "ok"); }
  catch { setStatus("Trình duyệt chặn chép tự động.", "err"); }
});
$("opts").addEventListener("click", (e) => { e.preventDefault(); chrome.runtime.openOptionsPage(); });

init();
