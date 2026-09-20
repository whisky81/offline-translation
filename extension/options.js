import { DEFAULTS, ENGINES, engineAvailable, fetchLanguages, getSettings } from "./common.js";

const $ = (id) => document.getElementById(id);
const LANG_NAMES = { vi: "Tiếng Việt", en: "Tiếng Anh", "zh-Hans": "Tiếng Trung",
                     zh: "Tiếng Trung", ja: "Tiếng Nhật", ko: "Tiếng Hàn" };

function setStatus(msg, cls = "") { $("status").textContent = msg; $("status").className = "status " + cls; }

async function fillLanguages(base, keep) {
  $("target").innerHTML = "";
  try {
    for (const l of await fetchLanguages(base)) {
      $("target").append(new Option(LANG_NAMES[l.code] || l.name, l.code));
    }
  } catch {
    for (const [c, n] of Object.entries(LANG_NAMES)) $("target").append(new Option(n, c));
  }
  if (keep) $("target").value = keep;
}

async function init() {
  const s = await getSettings();
  $("engine").append(new Option("Tự chọn (EnViT5 cho EN↔VI)", "auto"));
  for (const [k, e] of Object.entries(ENGINES)) $("engine").append(new Option(e.name, k));
  $("base").value = s.base;
  $("engine").value = s.engine;
  $("showBubble").checked = s.showBubble;
  $("maxChars").value = String(s.maxChars);
  await fillLanguages(s.base, s.target);
}

$("save").addEventListener("click", async () => {
  const base = $("base").value.trim().replace(/\/+$/, "");
  const n = parseInt($("maxChars").value, 10);
  if (!/^https?:\/\/[^/]+$/.test(base)) {
    setStatus("Địa chỉ không hợp lệ, ví dụ đúng: http://127.0.0.1:5001", "err"); return;
  }
  if (!Number.isFinite(n) || n < 100) { setStatus("Giới hạn ký tự phải ≥ 100.", "err"); return; }
  await chrome.storage.sync.set({
    base, engine: $("engine").value, target: $("target").value,
    showBubble: $("showBubble").checked, maxChars: n,
  });
  setStatus("Đã lưu.", "ok");
});

$("test").addEventListener("click", async () => {
  const base = $("base").value.trim().replace(/\/+$/, "");
  setStatus("Đang kiểm tra…");
  try {
    const langs = await fetchLanguages(base);
    const hf = await engineAvailable(base);
    setStatus(`LibreTranslate OK · ${langs.length} ngôn ngữ. `
              + (hf ? "EnViT5 OK." : "EnViT5 chưa bật (không sao, vẫn dịch được)."), "ok");
    await fillLanguages(base, $("target").value);
  } catch (err) {
    setStatus(`Hỏng: ${err.message}`, "err");
  }
});

$("reset").addEventListener("click", async () => {
  await chrome.storage.sync.set(DEFAULTS);
  await init();
  setStatus("Đã khôi phục mặc định.", "ok");
});

init();
