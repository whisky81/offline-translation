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

  // Cac khoa o day cung la danh sach khoa duoc doc tu storage.sync — thieu
  // mot khoa la khoa do khong bao gio duoc nap.
  let settings = { showBubble: true, target: "vi", rate: 1 };
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
    onSpeak: speak,
    onStopSpeak: stopSpeak,
  });

  const hideAll = () => { overlay.hideBubble(); closeCard(); };
  function closeCard() { runToken++; stopSpeak(); overlay.hideCard(); }

  // ---- doc thanh tieng --------------------------------------------------
  // Viec phat nam o tai lieu offscreen cua extension, khong o day: the <audio>
  // dat trong trang se chiu CSP media-src cua TRANG, va trang nao siet chat
  // blob: thi nut Doc se im lang ma khong bao gi.
  let ttsAsked = null;

  /** Hoi mot lan cho moi lan nap content script, chay song song voi lan dich. */
  function ensureTtsLangs() {
    if (ttsAsked) return ttsAsked;
    try {
      ttsAsked = chrome.runtime.sendMessage({ type: "tts-langs" })
        .then((r) => overlay.setTtsLanguages(r?.languages || []))
        .catch(() => overlay.setTtsLanguages([]));
    } catch {
      overlay.setTtsLanguages([]);
      ttsAsked = Promise.resolve();
    }
    return ttsAsked;
  }

  async function speak(which, text, lang) {
    if (extensionGone()) { overlay.setReadError(which, RELOAD_MSG); return; }
    // Doi nhan nut ngay, truoc khi goi mang: bam xong ma nut khong nhuc nhich
    // trong nua giay thi nguoi dung se bam lan nua.
    overlay.setReading(which);
    try {
      const res = await chrome.runtime.sendMessage({
        type: "tts-speak", q: text, lang, speed: settings.rate ?? 1,
      });
      if (!res?.ok) overlay.setReadError(which, res?.error || "máy đọc không phản hồi");
    } catch (err) {
      overlay.setReadError(which, /context invalidated/i.test(err.message || "")
        ? RELOAD_MSG : String(err.message || err));
    }
  }

  function stopSpeak() {
    if (!overlay.reading) return;
    overlay.setReading(null);
    try { chrome.runtime.sendMessage({ type: "tts-stop" }).catch(() => {}); }
    catch { /* context da chet — khong con gi de dung */ }
  }

  try {
    chrome.storage.sync.get(settings).then((s) => (settings = { ...settings, ...s }), () => {});
    chrome.storage.onChanged.addListener((ch) => {
      if (ch.showBubble) settings.showBubble = ch.showBubble.newValue;
      if (ch.target) settings.target = ch.target.newValue;
      if (ch.rate) settings.rate = ch.rate.newValue;
    });
  } catch { /* context da chet — van chay duoc voi mac dinh */ }

  async function run(textOverride) {
    const text = (textOverride ?? lastText ?? "").trim();
    if (text.length < MIN_CHARS) return;
    const mine = ++runToken;
    overlay.hideBubble();
    stopSpeak();                     // ban dich cu sap bien mat, dung doc no nua
    if (extensionGone()) { overlay.renderError(RELOAD_MSG); return; }
    overlay.renderLoading(text);
    // Chay song song voi lan dich: khi ket qua ve thi da biet co giong nao,
    // khong phai cho them mot vong nua moi ve duoc nut Doc.
    const langsReady = ensureTtsLangs();

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
    await langsReady;
    if (mine !== runToken) return;
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
    // Tai lieu offscreen bao tien do doc, service worker chuyen tiep sang day.
    if (msg?.type === "tts-state") {
      if (msg.state === "stopped") overlay.setReading(null);
      else if (msg.state === "error") overlay.setReadError(overlay.reading, msg.error);
      // "loading"/"playing" da duoc phan anh ngay luc bam, khong can lam gi.
      return;
    }
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
    stopSpeak();
    ac.abort();
    try { chrome.runtime.onMessage.removeListener(onRuntimeMessage); } catch { /* da chet */ }
    overlay.destroy();
    delete window.__dichOfflineCleanup;
  };
})();
