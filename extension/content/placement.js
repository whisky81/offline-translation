// Dat vi tri popup. Khong biet gi ve dich thuat hay DOM cua extension —
// chi nhan mot hinh chu nhat va mot phan tu, roi tinh cho dat.
//
// Nguyen tac: KHONG che chu ma nguoi dung dang doc. Dat ngay duoi vung chon
// la cach de nhat nhung tren PDF day chu no nuot mat dong ke tiep. Vi vay uu
// tien khoang trong BEN CANH truoc (le trang PDF, cot van ban hep tren web),
// roi moi den duoi, roi tren.
(() => {
  "use strict";
  const PAD = 8, GAP = 10;

  const put = (el, left, top) => {
    el.style.left = `${Math.round(left)}px`;
    el.style.top = `${Math.round(top)}px`;
  };

  /** Keo phan tu vao trong khung nhin (dung sau khi doi kich thuoc cua so). */
  function clampIntoView(el) {
    const r = el.getBoundingClientRect();
    const left = Math.min(parseFloat(el.style.left) || 0, window.innerWidth - r.width - PAD);
    const top = Math.min(parseFloat(el.style.top) || 0, window.innerHeight - r.height - PAD);
    put(el, Math.max(PAD, left), Math.max(PAD, top));
  }

  /** Nut nho: nam ngay SAU duoi vung chon, trong khoang trang cuoi dong. */
  function placeBubble(el, rect) {
    const { width: w, height: h } = el.getBoundingClientRect();
    if (rect.right + GAP + w <= window.innerWidth - PAD) {
      put(el, rect.right + GAP, rect.top + (rect.height - h) / 2);
    } else {
      put(el, Math.max(PAD, rect.right - w), rect.bottom + GAP);
    }
    clampIntoView(el);
  }

  /** The ket qua: canh ben neu du cho, neu khong thi duoi, roi tren. */
  function placeCard(el, rect) {
    const { width: w, height: h } = el.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight;
    const vertical = Math.max(PAD, Math.min(rect.top, vh - h - PAD));
    if (vw - rect.right >= w + GAP + PAD)      put(el, rect.right + GAP, vertical);
    else if (rect.left >= w + GAP + PAD)       put(el, rect.left - w - GAP, vertical);
    else if (vh - rect.bottom >= h + GAP + PAD) put(el, rect.left, rect.bottom + GAP);
    else if (rect.top >= h + GAP + PAD)         put(el, rect.left, rect.top - h - GAP);
    else                                        put(el, rect.left, PAD);
    clampIntoView(el);
  }

  (window.DichOffline ||= {}).placement = { placeBubble, placeCard, clampIntoView };
})();
