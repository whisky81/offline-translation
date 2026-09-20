// Dung chung cho service worker, popup va trang tuy chon.

export const DEFAULTS = {
  base: "http://127.0.0.1:5001",
  engine: "auto",      // auto | lt | hf
  target: "vi",
  source: "auto",
  showBubble: true,    // hien nut nho khi boi den
  maxChars: 5000,
};

// Hai engine sau cung mot origin. EnViT5 chi lam duoc en<->vi.
export const ENGINES = {
  lt: { path: "/api",  name: "LibreTranslate", pairs: null },
  hf: { path: "/api2", name: "EnViT5",         pairs: [["en", "vi"], ["vi", "en"]] },
};

export async function getSettings() {
  const got = await chrome.storage.sync.get(DEFAULTS);
  return { ...DEFAULTS, ...got };
}

/** LibreTranslate bao 'zh-Hans'; nguoi dung va vai API viet 'zh'. Quy ve mot moi. */
export function normLang(code) {
  return code === "zh" ? "zh-Hans" : code;
}

/**
 * Engine nao phuc vu duoc cap ngon ngu nay.
 *
 * "auto" KHONG duoc coi la khop voi engine co gioi han cap. Truoc day no khop,
 * va hau qua that: boi den tieng Nhat voi dich=vi -> chon EnViT5 -> EnViT5 doan
 * bua thanh tieng Anh -> tra ve rac ma khong bao loi gi.
 */
export function engineHandles(key, source, target) {
  const e = ENGINES[key];
  if (!e) return false;
  if (!e.pairs) return true;
  if (source === "auto") return false;
  const s = normLang(source), t = normLang(target);
  return e.pairs.some(([a, b]) => normLang(a) === s && normLang(b) === t);
}

/**
 * Chon engine thuc su dung.
 *  - "auto": uu tien EnViT5 khi cap la en<->vi (dich sat hon), con lai dung LibreTranslate.
 *  - chon tay: neu engine do khong lam duoc cap nay thi quay ve LibreTranslate.
 */
export function pickEngine(pref, source, target) {
  if (pref === "auto") {
    return engineHandles("hf", source, target) ? { key: "hf", note: null }
                                               : { key: "lt", note: null };
  }
  if (engineHandles(pref, source, target)) return { key: pref, note: null };
  // pref co the la gia tri cu con sot trong storage. Doc thang ENGINES[pref].name
  // se nem loi va lam hong ca lan dich — phai chiu duoc gia tri la.
  const name = ENGINES[pref]?.name;
  return { key: "lt", note: name ? `${name} không dịch được cặp này` : null };
}

export class ApiError extends Error {}

async function jsonPost(url, body, timeoutMs = 30000) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctl.signal,
    });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { /* khong phai JSON */ }
    if (!res.ok) throw new ApiError(data?.error || `HTTP ${res.status}`);
    return data;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err.name === "AbortError") throw new ApiError("quá thời gian chờ");
    throw new ApiError(`không gọi được máy chủ — nó đang chạy chứ? (${err.message})`);
  } finally {
    clearTimeout(timer);
  }
}

/** Nhan dien ngon ngu bang LibreTranslate (no lo duoc moi thu tieng). */
export async function detectLanguage(base, q) {
  const data = await jsonPost(`${base}/api/detect`, { q: q.slice(0, 500) }, 10000);
  return Array.isArray(data) && data[0]?.language ? data[0].language : null;
}

/** Dich mot doan. Tra ve { text, engine, note, detected, source, target, ms }. */
export async function translate(q, settings) {
  const s = { ...DEFAULTS, ...settings };
  const text = q.length > s.maxChars ? q.slice(0, s.maxChars) : q;
  const notes = [];
  if (q.length > s.maxChars) notes.push(`đã cắt còn ${s.maxChars} ký tự`);

  // Nhan dien TRUOC khi chon engine. Neu chon truoc, engine co gioi han cap se
  // nhan phai thu tieng no khong biet roi tra ve rac ma khong bao loi.
  let source = s.source;
  let detected = null;
  if (source === "auto") {
    detected = await detectLanguage(s.base, text).catch(() => null);
    if (detected) source = detected;
  }

  // Van ban da o dung ngon ngu dich -> dich sang ngon ngu doi ung, dung bao loi.
  let target = s.target;
  if (source !== "auto" && normLang(source) === normLang(target)) {
    target = normLang(target) === "en" ? "vi" : "en";
    notes.push(`đã là ${source}, dịch sang ${target}`);
  }

  const { key, note: engNote } = pickEngine(s.engine, source, target);
  if (engNote) notes.push(engNote);

  const t0 = Date.now();
  const data = await jsonPost(`${s.base}${ENGINES[key].path}/translate`, {
    q: text, source, target, format: "text",
  });
  return {
    text: data.translatedText || "",
    engine: ENGINES[key].name,
    note: notes.length ? notes.join(" · ") : null,
    detected: detected || data.detectedLanguage?.language || null,
    source, target,
    ms: Date.now() - t0,
  };
}

export async function fetchLanguages(base) {
  const res = await fetch(`${base}/api/languages`);
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`);
  return res.json();
}

export async function engineAvailable(base) {
  try {
    const res = await fetch(`${base}/api2/health`);
    return res.ok;
  } catch { return false; }
}
