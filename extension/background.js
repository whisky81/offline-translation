// Service worker. Moi loi goi mang deu o day, khong o content script.
//
// Ly do: content script chay theo origin cua TRANG. Trang https:// goi
// http://127.0.0.1 se vuong mixed-content va Private Network Access.
// Service worker chay theo origin cua extension, co host_permissions,
// nen goi thang duoc va khong phu thuoc trang dang mo la http hay https.

import { getSettings, translate } from "./common.js";

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
