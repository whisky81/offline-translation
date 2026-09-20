// Phat am thanh thay cho service worker.
//
// Vi sao can ca mot tai lieu rieng:
//   - Service worker cua MV3 khong co DOM -> khong co Audio(), khong phat duoc.
//   - Content script thi co DOM, nhung the <audio> nam trong trang nen chiu CSP
//     cua TRANG. Mot trang dat "default-src 'self'" se chan blob: va nut Doc
//     im lang ma khong bao gi.
// Tai lieu offscreen chay theo origin cua extension: khong dinh CSP cua trang,
// va co host_permissions nen goi thang 127.0.0.1 duoc.

import { Reader } from "./tts.js";

const reader = new Reader({
  onState: (s) => {
    // Bao nguoc ve service worker de no chuyen tiep cho tab dang mo the.
    chrome.runtime.sendMessage({ type: "tts-state", ...s }).catch(() => {
      /* service worker dang ngu va khong ai nghe — khong sao */
    });
  },
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  // Chi nhan thu goi dich danh cho minh. Khong loc thi tai lieu nay se
  // cuop ca cac thu no gui di (tts-state) va cac thu cua service worker.
  if (msg?.target !== "offscreen") return false;

  if (msg.type === "tts-play") {
    reader.base = msg.base;
    // KHONG await: mot doan dai co the phat hang phut, ma kenh sendResponse
    // dong lai truoc do tu lau. Tra loi ngay, tien do di bang tts-state.
    reader.play(msg.q, { lang: msg.lang, speed: msg.speed });
    sendResponse({ ok: true });
    return false;
  }
  if (msg.type === "tts-stop") {
    reader.stop();
    sendResponse({ ok: true });
    return false;
  }
  return false;
});
