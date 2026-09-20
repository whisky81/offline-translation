// Doc vung van ban dang duoc boi den. Tach rieng vi co hai nguon khac nhau
// va mot bay kho thay.
(() => {
  "use strict";
  const MIN_CHARS = 2;

  function rangeRect(sel) {
    try {
      const r = sel.getRangeAt(0).getBoundingClientRect();
      return r.width || r.height ? r : null;
    } catch { return null; }
  }

  /** Vung boi den trong <input>/<textarea>.
   *
   *  window.getSelection() CO tra ve chu cua o nhap, nhung
   *  getRangeAt(0).getBoundingClientRect() lai rong vi vung chon nam trong
   *  shadow tree cua chinh o nhap. Khi do phai lay khung cua o nhap. */
  function fieldSelection() {
    const el = document.activeElement;
    if (!el) return null;
    const tag = el.tagName;
    const typeOk = tag === "TEXTAREA"
      || (tag === "INPUT" && /^(text|search|url|email|tel|)$/i.test(el.type));
    if (!typeOk) return null;
    const { selectionStart: a, selectionEnd: b } = el;
    if (a == null || b == null || a === b) return null;
    const text = String(el.value).slice(a, b).trim();
    return text ? { text, rect: el.getBoundingClientRect() } : null;
  }

  /** Tra ve { text, rect } hoac null neu khong co gi dang dich. */
  function readSelection() {
    const sel = window.getSelection();
    const text = sel ? sel.toString().trim() : "";
    const field = fieldSelection();
    if (text.length >= MIN_CHARS) {
      return { text, rect: rangeRect(sel) || field?.rect || null };
    }
    if (field && field.text.length >= MIN_CHARS) return field;
    return null;
  }

  (window.DichOffline ||= {}).selection = { readSelection, MIN_CHARS };
})();
