// Chon bo dich. Day la Strategy: moi engine tu khai bao cap ngon ngu no lam
// duoc, ben goi chi hoi "ai lam duoc cap nay".
export const ENGINES = {
  lt: { base: "/api",  name: "LibreTranslate", pairs: null },   // null = moi cap
  hf: { base: "/api2", name: "EnViT5",         pairs: [["en", "vi"], ["vi", "en"]] },
};

/** LibreTranslate bao 'zh-Hans'; vai cho viet 'zh'. Quy ve mot moi. */
export const normLang = (code) => (code === "zh" ? "zh-Hans" : code);

/**
 * Engine co phuc vu duoc cap ngon ngu nay khong.
 *
 * 'auto' KHONG duoc coi la khop voi engine co gioi han cap: neu khop, go
 * tieng Nhat voi dich=vi se roi vao EnViT5, va no doan bua thanh tieng Anh
 * roi tra ve rac ma khong bao loi. Vi vay phai nhan dien nguon TRUOC.
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
 * Tra ve { key, fallback }.
 *  - "auto": uu tien EnViT5 khi la cap en<->vi, con lai LibreTranslate.
 *  - chon tay: neu engine do khong lam duoc cap nay thi quay ve LibreTranslate.
 */
export function pickEngine(pref, source, target) {
  if (pref === "auto") {
    return { key: engineHandles("hf", source, target) ? "hf" : "lt", fallback: null };
  }
  if (engineHandles(pref, source, target)) return { key: pref, fallback: null };
  // pref co the la gia tri cu con sot trong localStorage — doc thang
  // ENGINES[pref].name se nem loi va lam dut ca boot().
  const name = ENGINES[pref]?.name;
  return { key: "lt",
           fallback: name ? `${name} không dịch được cặp này — dùng LibreTranslate.` : null };
}
