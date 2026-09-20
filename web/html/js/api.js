// Lop goi HTTP. Khong biet gi ve DOM.
//
// Cung origin qua nginx (/api, /api2) nen khong dinh toi CORS.

export class ApiError extends Error {}

export async function api(path, { json, form, signal, base = "/api" } = {}) {
  const opt = { method: json || form ? "POST" : "GET", signal };
  if (json) { opt.headers = { "Content-Type": "application/json" }; opt.body = JSON.stringify(json); }
  if (form) opt.body = form;

  let res;
  try {
    res = await fetch(base + path, opt);
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`không gọi được máy chủ (${err.message})`);
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* khong phai JSON */ }
  if (!res.ok) {
    throw new ApiError(data?.error || `HTTP ${res.status}`
      + (text ? `: ${text.slice(0, 160)}` : ""));
  }
  return data;
}

export const languages = () => api("/languages");
export const frontendSettings = () => api("/frontend/settings");

/** Nhan dien ngon ngu. LibreTranslate lo duoc moi thu tieng, ke ca cai
 *  EnViT5 khong biet — nen luon hoi no truoc khi chon engine. */
export async function detectLanguage(q) {
  const r = await api("/detect", { json: { q: q.slice(0, 500) } });
  return Array.isArray(r) && r[0]?.language ? r[0].language : null;
}

export async function engineAlive(base) {
  try { await api("/health", { base }); return true; } catch { return false; }
}
