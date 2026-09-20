// Service worker. Moi loi goi mang deu o day, khong o content script.
//
// Ly do: content script chay theo origin cua TRANG. Trang https:// goi
// http://127.0.0.1 se vuong mixed-content va Private Network Access.
// Service worker chay theo origin cua extension, co host_permissions,
// nen goi thang duoc va khong phu thuoc trang dang mo la http hay https.

import { getSettings, ttsLanguages, translate } from "./common.js";

const MENU_ID = "dich-offline";
const MENU_PDF = "dich-offline-pdf";

// Trinh doc PDF san cua Chromium khong cho content script cham vao noi dung,
// nen tren PDF ta mo bang trinh doc rieng (viewer.html) — o do lop chu la DOM
// that va cai nut boi-den-de-dich hoat dong binh thuong.
const PDF_PATTERNS = ["*://*/*.pdf", "*://*/*.PDF", "file:///*.pdf", "file:///*.PDF"];

export function viewerUrlFor(fileUrl) {
  return chrome.runtime.getURL(`viewer.html?file=${encodeURIComponent(fileUrl)}`);
}

/** Khi extension duoc cai/nap lai, Chrome KHONG tu chen content script vao cac
 *  tab dang mo — script cu o do se bao "Extension context invalidated".
 *  Chen lai cho nhung tab ma ta co quyen (localhost va file://). Cac trang khac
 *  thi content script se bao nguoi dung tai lai trang. */
async function reinjectContentScripts() {
  const patterns = chrome.runtime.getManifest().host_permissions || [];
  let tabs = [];
  try { tabs = await chrome.tabs.query({ url: patterns }); } catch { return; }
  for (const tab of tabs) {
    if (tab.id == null) continue;
    try {
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
    } catch { /* trang khong cho chen (chrome://, store...) — bo qua */ }
  }
}

// chrome.storage.session bi xoa moi khi extension nap lai hoac trinh duyet
// khoi dong lai — dung dung de "chi chen lai mot lan cho moi lan nap".
// Service worker co the ngu/day nhieu lan, khong nen chen lai moi lan day.
(async () => {
  try {
    const { injectedOnce } = await chrome.storage.session.get("injectedOnce");
    if (injectedOnce) return;
    await chrome.storage.session.set({ injectedOnce: true });
    await reinjectContentScripts();
  } catch { /* khong sao neu that bai */ }
})();

chrome.runtime.onStartup.addListener(reinjectContentScripts);

chrome.runtime.onInstalled.addListener(() => {
  reinjectContentScripts();
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_ID,
      title: "Dịch đoạn đang chọn",
      contexts: ["selection"],
    });
    chrome.contextMenus.create({
      id: MENU_PDF,
      title: "Mở PDF bằng trình đọc có dịch",
      contexts: ["page", "frame"],
      documentUrlPatterns: PDF_PATTERNS,
    });
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === MENU_ID && tab?.id != null) {
    chrome.tabs.sendMessage(tab.id, { type: "translate-selection" }).catch(() => {});
  }
  if (info.menuItemId === MENU_PDF) {
    const target = info.frameUrl || info.pageUrl;
    if (target) chrome.tabs.create({ url: viewerUrlFor(target) });
  }
});

chrome.commands.onCommand.addListener((cmd) => {
  if (cmd !== "translate-selection") return;
  chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
    if (tab?.id != null) {
      chrome.tabs.sendMessage(tab.id, { type: "translate-selection" }).catch(() => {});
    }
  });
});

// ---- doc thanh tieng --------------------------------------------------
// Am thanh khong the phat o day: service worker cua MV3 khong co DOM. Ta mo
// mot tai lieu offscreen (offscreen.html) va no lo phan phat.
const OFFSCREEN_PAGE = "offscreen.html";

async function ensureOffscreen() {
  if (!chrome.offscreen) {
    throw new Error("trình duyệt này không hỗ trợ phát âm thanh nền (cần Chrome 116+)");
  }
  if (await chrome.offscreen.hasDocument()) return;
  try {
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_PAGE,
      reasons: ["AUDIO_PLAYBACK"],
      justification: "Phát bản đọc của đoạn văn bản đang chọn.",
    });
  } catch (err) {
    // Hai lan bam Doc that nhanh se cung chay toi day. Chrome chi cho mot tai
    // lieu offscreen, va loi do vo hai — cai dau da tao xong roi.
    if (!/single offscreen|already/i.test(String(err.message))) throw err;
  }
}

/** Tab nao dang nghe. Giu trong storage.session vi service worker co the ngu
 *  giua chung lan doc, va bien trong bo nho se mat theo. */
const rememberTtsTab = (id) => chrome.storage.session.set({ ttsTabId: id });

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.target === "offscreen") return false;   // khong phai viec cua ta

  if (msg?.type === "tts-speak") {
    (async () => {
      try {
        const s = await getSettings();
        if (sender.tab?.id != null) await rememberTtsTab(sender.tab.id);
        await ensureOffscreen();
        await chrome.runtime.sendMessage({
          target: "offscreen", type: "tts-play",
          base: `${s.base}/api3`, q: msg.q, lang: msg.lang, speed: msg.speed ?? 1,
        });
        sendResponse({ ok: true });
      } catch (err) {
        sendResponse({ ok: false, error: String(err.message || err) });
      }
    })();
    return true;
  }

  if (msg?.type === "tts-stop") {
    (async () => {
      try {
        if (chrome.offscreen && await chrome.offscreen.hasDocument()) {
          await chrome.runtime.sendMessage({ target: "offscreen", type: "tts-stop" });
        }
      } catch { /* chua tung phat lan nao — coi nhu da dung */ }
      sendResponse({ ok: true });
    })();
    return true;
  }

  if (msg?.type === "tts-langs") {
    (async () => {
      // Moi tab deu hoi cau nay. Nho lai trong phien de khong goi may chu
      // mot lan cho moi trang duoc mo.
      const hit = await chrome.storage.session.get("ttsLangs");
      if (Array.isArray(hit.ttsLangs)) {
        sendResponse({ ok: true, languages: hit.ttsLangs });
        return;
      }
      const s = await getSettings();
      const languages = await ttsLanguages(s.base);
      // Chi nho khi that su co giong: may doc con dang khoi dong thi lan sau
      // phai hoi lai, khong khoa cung ket qua rong.
      if (languages.length) await chrome.storage.session.set({ ttsLangs: languages });
      sendResponse({ ok: true, languages });
    })();
    return true;
  }

  // Tai lieu offscreen bao tien do. No khong goi thang toi content script duoc
  // (chrome.runtime.sendMessage khong toi content script), nen ta chuyen tiep.
  if (msg?.type === "tts-state") {
    (async () => {
      const { ttsTabId } = await chrome.storage.session.get("ttsTabId");
      if (ttsTabId != null) {
        chrome.tabs.sendMessage(ttsTabId, { type: "tts-state", ...msg }).catch(() => {
          /* tab da dong hoac da chuyen trang */
        });
      }
    })();
    return false;
  }

  return false;
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== "translate") return false;
  (async () => {
    try {
      const settings = { ...(await getSettings()), ...(msg.override || {}) };
      sendResponse({ ok: true, ...(await translate(msg.q, settings)) });
    } catch (err) {
      sendResponse({ ok: false, error: String(err.message || err) });
    }
  })();
  return true;            // giu kenh mo cho phan hoi bat dong bo
});
