// Luu tuy chon va lich su. Bo qua moi loi: che do rieng tu hoac chan luu tru
// khong duoc phep lam hong trang.
const NS = "dich-offline";

export const load = (key, fallback) => {
  try { return JSON.parse(localStorage.getItem(`${NS}:${key}`)) ?? fallback; }
  catch { return fallback; }
};

export const save = (key, value) => {
  try { localStorage.setItem(`${NS}:${key}`, JSON.stringify(value)); }
  catch { /* che do rieng tu */ }
};

const MAX_HISTORY = 15;
const MAX_SOURCE_LEN = 400;

export function remember(source, translated) {
  if (!translated || source.length > MAX_SOURCE_LEN) return;
  const list = load("hist", []).filter((h) => h.s !== source);
  list.unshift({ s: source, o: translated });
  save("hist", list.slice(0, MAX_HISTORY));
}

export const history = () => load("hist", []);
export const clearHistory = () => save("hist", []);
