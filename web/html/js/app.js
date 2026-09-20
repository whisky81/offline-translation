// Dieu phoi UI: noi cac o nhap voi lop api va lop chon engine.
import { ApiError, api, detectLanguage, engineAlive, frontendSettings, languages } from "./api.js";
import { ENGINES, normLang, pickEngine } from "./engines.js";
import { clearHistory, history, load, remember, save } from "./store.js";

const $ = (id) => document.getElementById(id);
const el = Object.fromEntries(
  ["health", "src", "tgt", "swap", "input", "output", "alts", "detected", "count",
   "timing", "status", "copy", "clear", "theme", "file", "dofile", "formats",
   "fileout", "hist", "inpane", "engine", "clearhist", "histcount"]
    .map((id) => [id, $(id)]));

const DEBOUNCE_MS = 350;
let langs = [];
let debounce = null;
let inflight = null;        // AbortController cua request dang chay
let seq = 0;                // chong ket qua ve tre ghi de ket qua moi
let detectedSource = null;  // ngon ngu nhan dien duoc gan nhat

const esc = (s) => s.replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nameOf = (code) => langs.find((l) => l.code === code)?.name || code;

// ---------- trang thai hien thi -----------------------------------------
function setStatus(msg, isErr = false) {
  el.status.textContent = msg;
  el.status.classList.toggle("err", isErr);
}

/** Lam mo ket qua CU trong luc dich, de khoi tuong day la ket qua moi. */
function setBusy(on) {
  el.output.classList.toggle("busy", on);
  if (on) el.timing.innerHTML = '<span class="spinner"></span>đang dịch…';
}

function updateCount() {
  el.count.textContent = `${el.input.value.length.toLocaleString("vi-VN")} ký tự`;
}

/** Khong cho chon dich trung nguon, va chi bat nut dao chieu khi biet nguon. */
function refreshPairControls() {
  const src = el.src.value;
  for (const opt of el.tgt.options) {
    opt.disabled = src !== "auto" && normLang(opt.value) === normLang(src);
  }
  if (el.tgt.selectedOptions[0]?.disabled) {
    const first = [...el.tgt.options].find((o) => !o.disabled);
    if (first) { el.tgt.value = first.value; save("tgt", first.value); }
  }
  const known = src !== "auto" || Boolean(detectedSource);
  el.swap.disabled = !known;
  el.swap.title = known ? "Đảo chiều dịch" : "Dịch một lần trước để biết ngôn ngữ nguồn";
}

function refreshEngineHint() {
  const { key, fallback } = pickEngine(
    el.engine.value, el.src.value === "auto" ? (detectedSource ?? "auto") : el.src.value,
    el.tgt.value);
  el.engine.classList.toggle("unavailable", Boolean(fallback));
  el.engine.title = fallback || `Bộ dịch: ${ENGINES[key]?.name ?? "tự chọn"}`;
}

// ---------- dich ---------------------------------------------------------
const schedule = () => { clearTimeout(debounce); debounce = setTimeout(translate, DEBOUNCE_MS); };

function resetOutput() {
  setBusy(false);
  el.output.textContent = "";
  el.alts.hidden = true;
  el.detected.textContent = "";
  el.detected.dataset.code = "";
  el.timing.textContent = "";
}

async function translate() {
  clearTimeout(debounce);
  const q = el.input.value.trim();
  save("draft", el.input.value);
  if (!q) { resetOutput(); return; }

  inflight?.abort();
  inflight = new AbortController();
  const mine = ++seq;
  setBusy(true);

  // Nguon 'auto': phai biet ngon ngu that TRUOC khi chon engine, neu khong
  // engine co gioi han cap se nhan phai thu tieng no khong biet.
  let source = el.src.value;
  if (source === "auto") {
    detectedSource = await detectLanguage(q).catch(() => null);
    if (mine !== seq) return;
    if (detectedSource) { source = detectedSource; refreshPairControls(); }
  }

  // Nguon trung dich thi ket qua se y het dau vao — trong nhu hong.
  let target = el.tgt.value;
  let flipped = null;
  if (source !== "auto" && normLang(source) === normLang(target)) {
    target = normLang(target) === "en" ? "vi" : "en";
    flipped = `đã là ${source}, dịch sang ${target}`;
  }

  const { key, fallback } = pickEngine(el.engine.value, source, target);
  const engine = ENGINES[key];
  const t0 = performance.now();

  try {
    const data = await api("/translate", {
      base: engine.base,
      json: { q, source, target, format: "text", alternatives: 3 },
      signal: inflight.signal,
    });
    if (mine !== seq) return;

    setBusy(false);
    el.output.textContent = data.translatedText || "";
    el.timing.textContent = `${engine.name} · ${Math.round(performance.now() - t0)} ms`
                          + (flipped ? ` · ${flipped}` : "");

    const alts = (data.alternatives || []).filter((a) => a && a !== data.translatedText);
    el.alts.hidden = alts.length === 0;
    if (alts.length) el.alts.innerHTML = "Cách khác: " + alts.map((a) => `<b>${esc(a)}</b>`).join(" · ");

    const d = data.detectedLanguage;
    el.detected.dataset.code = d ? d.language : "";
    el.detected.innerHTML = d
      ? `<span class="chip">${esc(nameOf(d.language))} ${Math.round(d.confidence)}%</span>` : "";

    setStatus(fallback || "");
    remember(q, data.translatedText);
    renderHistory();
  } catch (err) {
    if (err.name === "AbortError") return;
    setBusy(false);
    setStatus(`Dịch thất bại: ${err.message}`, true);
  } finally {
    if (mine === seq) inflight = null;
  }
}

// ---------- lich su -------------------------------------------------------
function renderHistory() {
  const list = history();
  el.hist.innerHTML = "";
  el.histcount.textContent = list.length ? `${list.length} mục gần đây` : "Chưa có lịch sử";
  el.clearhist.disabled = list.length === 0;
  for (const h of list) {
    const b = document.createElement("button");
    b.innerHTML = `<span class="h-src">${esc(h.s.slice(0, 70))}</span><br>${esc(h.o.slice(0, 70))}`;
    b.addEventListener("click", () => {
      el.input.value = h.s; updateCount(); translate(); el.input.focus();
    });
    el.hist.append(b);
  }
}

// ---------- dich tep ------------------------------------------------------
async function translateFile(f) {
  if (!f) { setStatus("Chọn một tệp trước đã.", true); return; }
  el.fileout.textContent = `Đang dịch ${f.name}…`;
  const form = new FormData();
  form.append("file", f);
  form.append("source", el.src.value);
  form.append("target", el.tgt.value);
  try {
    // EnViT5 khong co endpoint tep — dich tep luon qua LibreTranslate.
    const data = await api("/translate_file", { form, base: ENGINES.lt.base });
    el.fileout.textContent = "";
    const a = document.createElement("a");
    a.href = data.translatedFileUrl;
    a.textContent = `Tải bản dịch của ${f.name}`;
    a.download = "";
    el.fileout.append(a);
  } catch (err) {
    el.fileout.textContent = "";
    setStatus(`Dịch tệp thất bại: ${err.message}`, true);
  }
}

// ---------- nen sang/toi --------------------------------------------------
const applyTheme = (t) => {
  if (t) document.documentElement.setAttribute("data-theme", t);
  else document.documentElement.removeAttribute("data-theme");
};

// ---------- khoi tao ------------------------------------------------------
async function boot() {
  applyTheme(load("theme", null));

  try {
    langs = await languages();
  } catch (err) {
    el.health.className = "dot off";
    setStatus(`Không gọi được máy chủ dịch: ${err.message}`, true);
    return;
  }
  el.health.className = "dot on";
  el.health.title = `Máy chủ hoạt động · ${langs.length} ngôn ngữ`;

  for (const l of langs) {
    el.src.append(new Option(l.name, l.code));
    el.tgt.append(new Option(l.name, l.code));
  }
  el.src.value = load("src", "auto");
  el.tgt.value = load("tgt", "vi") || langs[0]?.code || "en";
  el.engine.value = load("engine", "auto");

  // Engine thu hai co the chua duoc bat -> vo hieu hoa thay vi de bam vao loi.
  if (!(await engineAlive(ENGINES.hf.base))) {
    const opt = el.engine.querySelector('option[value="hf"]');
    if (opt) opt.disabled = true;
    if (el.engine.value === "hf") el.engine.value = "auto";
    el.engine.title = "EnViT5 chưa bật — xem engine/README.md";
  }

  try {
    const s = await frontendSettings();
    el.formats.textContent = (s.supportedFilesFormat || []).join("  ");
  } catch { /* khong quan trong */ }

  refreshEngineHint();
  refreshPairControls();
  renderHistory();

  const draft = load("draft", "");
  if (draft) { el.input.value = draft; updateCount(); translate(); }
  setStatus(`Sẵn sàng · ${langs.length} ngôn ngữ · mọi thứ chạy trên máy này.`);
}

// ---------- su kien -------------------------------------------------------
el.input.addEventListener("input", () => { updateCount(); schedule(); });
el.src.addEventListener("change", () => {
  save("src", el.src.value); refreshPairControls(); refreshEngineHint(); translate();
});
el.tgt.addEventListener("change", () => {
  save("tgt", el.tgt.value); refreshEngineHint(); translate();
});
el.engine.addEventListener("change", () => {
  save("engine", el.engine.value); refreshEngineHint(); translate();
});

el.swap.addEventListener("click", () => {
  const src = el.src.value === "auto" ? el.detected.dataset.code : el.src.value;
  if (!src || !langs.some((l) => l.code === src)) {
    setStatus("Chưa biết ngôn ngữ nguồn để đảo — chọn thủ công.", true);
    return;
  }
  el.src.value = el.tgt.value;
  el.tgt.value = src;
  el.input.value = el.output.textContent;
  save("src", el.src.value); save("tgt", el.tgt.value);
  refreshPairControls(); updateCount(); translate();
});

el.clear.addEventListener("click", () => {
  el.input.value = ""; updateCount(); translate(); el.input.focus();
});

el.copy.addEventListener("click", async () => {
  if (!el.output.textContent) return;
  try { await navigator.clipboard.writeText(el.output.textContent); setStatus("Đã chép."); }
  catch { setStatus("Trình duyệt chặn chép tự động — bôi đen rồi Ctrl+C.", true); }
});

el.theme.addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme");
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const next = cur ? (cur === "dark" ? "light" : null) : (dark ? "light" : "dark");
  applyTheme(next); save("theme", next);
});

el.dofile.addEventListener("click", () => translateFile(el.file.files[0]));
el.clearhist.addEventListener("click", () => {
  clearHistory(); renderHistory(); setStatus("Đã xoá lịch sử.");
});

document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); translate(); }
});

for (const ev of ["dragenter", "dragover"]) {
  el.inpane.addEventListener(ev, (e) => { e.preventDefault(); el.inpane.classList.add("drop"); });
}
for (const ev of ["dragleave", "drop"]) {
  el.inpane.addEventListener(ev, () => el.inpane.classList.remove("drop"));
}
el.inpane.addEventListener("drop", (e) => {
  e.preventDefault();
  const f = e.dataTransfer.files[0];
  if (f) { el.file.files = e.dataTransfer.files; translateFile(f); }
});

boot();
