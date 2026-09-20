// Dieu phoi: noi vung boi den -> giao dien -> service worker.
//
// Moi lenh goi mang deu di qua service worker. Content script chay theo origin
// cua TRANG; trang https:// goi http://127.0.0.1 se vuong mixed content va
// Private Network Access. Service worker chay theo origin cua extension nen
// khong bi.
(() => {
  "use strict";
  const NS = window.DichOffline;
  const { readSelection, MIN_CHARS } = NS.selection;

  // Khi extension duoc nap lai, ban CU trong trang van con listener nhung
  // chrome.* cua no da chet. Bao ban cu tu don roi thay the han.
  if (typeof window.__dichOfflineCleanup === "function") {
    try { window.__dichOfflineCleanup(); } catch { /* ban cu da chet han */ }
  }

  const ac = new AbortController();
  const live = { capture: true, signal: ac.signal };
  const livePassive = { capture: true, passive: true, signal: ac.signal };

  let settings = { showBubble: true, target: "vi" };
  let lastText = "", lastRect = null;
  // Bam nut se an nut ngay o mousedown. Khi nha chuot, cho do khong con nut
  // nen mouseup roi xuong TRANG -> handler tuong da boi den cho khac ->
  // showBubble() -> ham do an mat the. Bo qua dung mot mouseup de tranh.
  let skipNextMouseup = false;
  // Moi lan dich mang mot so thu tu; dong the tang so nay len nen ket qua ve
  // MUON cua lan da huy khong con duoc ve ra.
  let runToken = 0;

  /** Sau khi extension nap lai, chrome.runtime cua content script cu da chet. */
  const extensionGone = () => {
    try { return !chrome.runtime?.id; } catch { return true; }
  };
  const RELOAD_MSG = "Extension vừa được cập nhật hoặc tắt đi. "
                   + "Tải lại trang (Ctrl+R) rồi bôi đen lại.";

  const overlay = new NS.ui.Overlay({
    onTranslate: () => { skipNextMouseup = true; run(); },
    onTargetChange: (target, sourceText) => {
      settings.target = target;
      try { chrome.storage.sync.set({ target }); } catch { /* context da chet */ }
      run(sourceText);
    },
  });

  const hideAll = () => { overlay.hideBubble(); closeCard(); };
  function closeCard() { runToken++; overlay.hideCard(); }

  try {
    chrome.storage.sync.get(settings).then((s) => (settings = { ...settings, ...s }), () => {});
    chrome.storage.onChanged.addListener((ch) => {
      if (ch.showBubble) settings.showBubble = ch.showBubble.newValue;
      if (ch.target) settings.target = ch.target.newValue;
    });
  } catch { /* context da chet — van chay duoc voi mac dinh */ }

  async function run(textOverride) {
    const text = (textOverride ?? lastText ?? "").trim();
    if (text.length < MIN_CHARS) return;
    const mine = ++runToken;
    overlay.hideBubble();
    if (extensionGone()) { overlay.renderError(RELOAD_MSG); return; }
    overlay.renderLoading(text);

    let res;
    try {
      res = await chrome.runtime.sendMessage({ type: "translate", q: text });
    } catch (err) {
      if (mine !== runToken) return;
      overlay.renderError(
        /context invalidated|receiving end does not exist/i.test(err.message || "")
          ? RELOAD_MSG : `Không gọi được extension: ${err.message}`);
      return;
    }
    if (mine !== runToken) return;    // nguoi dung da dong, hoac co lan dich moi
    if (!res) { overlay.renderError("Service worker không phản hồi."); return; }
    if (!res.ok) { overlay.renderError(res.error); return; }
    overlay.renderResult(res, text, res.target || settings.target);
  }

  // ---- su kien ----------------------------------------------------------
  document.addEventListener("mouseup", (e) => {
    if (skipNextMouseup) { skipNextMouseup = false; return; }  // nha chuot cua cu bam nut
    if (overlay.contains(e)) return;
    setTimeout(() => {
      const got = readSelection();
      if (!got || !got.rect) { overlay.hideBubble(); return; }
      lastText = got.text;
      lastRect = got.rect;
      if (settings.showBubble) overlay.showBubble(got.rect);
    }, 0);
  }, live);

  document.addEventListener("mousedown", (e) => {
    if (overlay.contains(e)) return;
    hideAll();
  }, live);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideAll();
  }, live);

  // Su kien scroll KHONG noi bot len, nhung CO di qua pha capture cua window.
  // Chi an NUT (no neo theo vung chon nen se lech cho); THE thi giu — tren
  // touchpad chi can hai ngon nhich nhe la cuon, dong the se lam mat ban dich.
  window.addEventListener("scroll", (e) => {
    if (overlay.element && (e.target === overlay.element || overlay.contains(e))) return;
    overlay.hideBubble();
  }, livePassive);

  window.addEventListener("resize", () => {
    overlay.hideBubble();
    overlay.reclamp();
  }, { passive: true, signal: ac.signal });

  const onRuntimeMessage = (msg) => {
    if (msg?.type !== "translate-selection") return;
    const got = readSelection();
    if (!got) return;
    lastText = got.text;
    lastRect = got.rect || { left: 20, top: 20, bottom: 40, right: 200, width: 180, height: 20 };
    overlay.rect = lastRect;
    run();
  };
  try { chrome.runtime.onMessage.addListener(onRuntimeMessage); } catch { /* context da chet */ }

  // Ban nap sau se goi ham nay de ban nay bien mat han.
  window.__dichOfflineCleanup = () => {
    ac.abort();
    try { chrome.runtime.onMessage.removeListener(onRuntimeMessage); } catch { /* da chet */ }
    overlay.destroy();
    delete window.__dichOfflineCleanup;
  };
})();
