// Giao dien noi (nut nho + the ket qua) dung trong shadow DOM dong.
//
// Vi sao shadow DOM: phai chen UI len MOI trang web. Shadow root chan CSS cua
// trang lot vao va chan CSS cua ta pha trang. Dung mode "closed" de trang
// khong voi vao duoc.
(() => {
  "use strict";
  const NS = (window.DichOffline ||= {});
  const { placeBubble, placeCard, clampIntoView } = NS.placement;

  const LANGS = [["vi", "Tiếng Việt"], ["en", "Tiếng Anh"], ["zh", "Tiếng Trung"],
                 ["ja", "Tiếng Nhật"], ["ko", "Tiếng Hàn"]];

  const CSS = `
:host, * { box-sizing: border-box; }
.btn {
  position: fixed; z-index: 10;
  display: flex; align-items: center; gap: 6px;
  padding: 6px 10px; border-radius: 8px; cursor: pointer;
  font: 500 13px/1.2 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  background: #1f2937; color: #fff; border: 1px solid #374151;
  box-shadow: 0 4px 14px rgba(0,0,0,.28); user-select: none;
}
.btn:hover { background: #111827; }
.card {
  position: fixed; z-index: 10; width: min(380px, calc(100vw - 24px));
  background: #fff; color: #111827; border: 1px solid #e5e7eb; border-radius: 12px;
  box-shadow: 0 10px 34px rgba(0,0,0,.22);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  overflow: hidden;
}
@media (prefers-color-scheme: dark) {
  .card { background: #171a21; color: #e8eaed; border-color: #2a2f3a; }
  .head, .foot { border-color: #2a2f3a !important; }
  .src { color: #9aa3b2 !important; }
  select { background: #171a21; color: #e8eaed; border-color: #2a2f3a; }
}
.head {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; border-bottom: 1px solid #e5e7eb; font-size: 12px;
}
.head .grow { flex: 1; }
select {
  font: inherit; font-size: 12px; padding: 3px 6px; border-radius: 6px;
  border: 1px solid #e5e7eb; background: #fff; color: inherit;
}
.x {
  cursor: pointer; opacity: .6; padding: 0 5px; font-size: 15px; line-height: 1;
  background: none; border: 0; color: inherit; font-family: inherit;
}
.x:hover { opacity: 1; }
.btn:focus-visible, .x:focus-visible, .copy:focus-visible, select:focus-visible {
  outline: 2px solid #3b82f6; outline-offset: 2px;
}
.body { padding: 10px 12px; max-height: 320px; overflow: auto; }
.src { font-size: 12px; color: #6b7280; margin-bottom: 8px;
       max-height: 60px; overflow: auto; white-space: pre-wrap; }
.out { white-space: pre-wrap; overflow-wrap: anywhere; }
.err { color: #c81e1e; }
.foot {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 7px 12px; border-top: 1px solid #e5e7eb; font-size: 11.5px; opacity: .75;
}
.foot .grow { flex: 1; }
.copy {
  cursor: pointer; text-decoration: underline; background: none; border: 0;
  color: inherit; font: inherit; font-size: 11.5px; padding: 0;
}
/* Dang doc: bo gach chan, to dam, doi mau — de biet nut nao dang chay. */
.copy.on { text-decoration: none; font-weight: 700; color: #2563eb; }
@media (prefers-color-scheme: dark) { .copy.on { color: #5b8cff; } }
.spin {
  width: 13px; height: 13px; border: 2px solid currentColor; border-right-color: transparent;
  border-radius: 50%; display: inline-block; animation: sp .7s linear infinite;
}
@keyframes sp { to { transform: rotate(360deg); } }
`;

  /** Quan ly toan bo phan nhin thay. Khong goi mang, khong doc vung boi den. */
  class Overlay {
    constructor({ onTranslate, onTargetChange, onSpeak, onStopSpeak }) {
      this.onTranslate = onTranslate;
      this.onTargetChange = onTargetChange;
      this.onSpeak = onSpeak || (() => {});
      this.onStopSpeak = onStopSpeak || (() => {});
      this.host = null; this.root = null; this.bubble = null; this.card = null;
      this.rect = null;
      // null = chua hoi may doc; [] = co hoi va khong co giong nao.
      this.ttsLangs = null;
      this.reading = null;      // "src" | "out" khi dang doc
    }

    /** Ngon ngu may doc phuc vu duoc. Goi mot lan luc khoi tao. */
    setTtsLanguages(list) { this.ttsLangs = Array.isArray(list) ? list : []; }

    get element() { return this.host; }

    #ensureRoot() {
      if (this.root) return this.root;
      this.host = document.createElement("div");
      this.host.id = "dich-offline-root";
      this.host.style.cssText =
        "all:initial;position:fixed;top:0;left:0;width:0;height:0;z-index:2147483647";
      (document.body || document.documentElement).appendChild(this.host);
      this.root = this.host.attachShadow({ mode: "closed" });
      const style = document.createElement("style");
      style.textContent = CSS;
      this.root.appendChild(style);
      return this.root;
    }

    contains(event) {
      return Boolean(this.host && event.composedPath?.().includes(this.host));
    }

    showBubble(rect) {
      this.hideCard();
      this.rect = rect;
      const root = this.#ensureRoot();
      if (!this.bubble) {
        const b = document.createElement("div");
        b.className = "btn";
        b.setAttribute("role", "button");
        b.setAttribute("tabindex", "0");
        b.setAttribute("aria-label", "Dịch đoạn đang chọn");
        // SVG thay cho emoji: emoji phu thuoc font he thong, thieu font la ra o vuong.
        b.innerHTML = `<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
          <path fill="currentColor" d="M2 2h7v2H7.6A6.7 6.7 0 0 1 6.2 7.2c.5.5 1 .9 1.6 1.2l-.7 1.4a9 9 0 0 1-2-1.6 9.4 9.4 0 0 1-2.6 1.7l-.6-1.4a8 8 0 0 0 2.2-1.4A7 7 0 0 1 2.9 4.6h1.6c.2.6.5 1.1.9 1.6.5-.6.8-1.4 1-2.2H2V2Zm8.4 5h2.2L15 14h-1.6l-.5-1.5h-2.6L9.8 14H8.2l2.2-7Zm.4 4h1.6l-.8-2.4-.8 2.4Z"/>
        </svg><span>Dịch</span>`;
        // mousedown chu khong phai click: click se lam mat vung boi den truoc khi ta doc duoc.
        b.addEventListener("mousedown", (e) => {
          e.preventDefault(); e.stopPropagation(); this.onTranslate();
        });
        b.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this.onTranslate(); }
        });
        root.appendChild(b);
        this.bubble = b;
      }
      this.bubble.style.display = "flex";
      placeBubble(this.bubble, rect);
    }

    hideBubble() { if (this.bubble) this.bubble.style.display = "none"; }
    hideCard() { if (this.card) this.card.style.display = "none"; }
    get cardVisible() { return Boolean(this.card) && this.card.style.display !== "none"; }
    reclamp() { if (this.cardVisible) clampIntoView(this.card); }

    #card() {
      const root = this.#ensureRoot();
      if (!this.card) {
        const c = document.createElement("div");
        c.className = "card";
        c.setAttribute("role", "dialog");
        c.setAttribute("aria-label", "Bản dịch");
        c.setAttribute("aria-live", "polite");
        c.addEventListener("mousedown", (e) => e.stopPropagation());
        root.appendChild(c);
        this.card = c;
      }
      this.card.style.display = "block";
      // Dat tam ngoai man hinh: phai ve xong noi dung moi biet kich thuoc that.
      this.card.style.left = "-9999px";
      this.card.style.top = "0px";
      return this.card;
    }

    #finish(c) {
      c.querySelector("[data-x]")?.addEventListener("mousedown", () => this.hideCard());
      placeCard(c, this.rect);
    }

    renderLoading(text) {
      const c = this.#card();
      c.innerHTML = `
        <div class="head"><span class="grow">Đang dịch…</span><button class="x" data-x aria-label="Đóng">✕</button></div>
        <div class="body"><div class="src"></div><div class="out"><span class="spin"></span></div></div>`;
      c.querySelector(".src").textContent = text.slice(0, 300);
      this.#finish(c);
    }

    renderResult(res, sourceText, target) {
      const c = this.#card();
      c.innerHTML = `
        <div class="head">
          <span>Dịch sang</span><select data-lang></select>
          <span class="grow"></span><button class="x" data-x aria-label="Đóng">✕</button>
        </div>
        <div class="body"><div class="src"></div><div class="out"></div></div>
        <div class="foot"><span data-meta></span><span class="grow"></span>
          <button class="copy" data-read="src" hidden>Đọc gốc</button>
          <button class="copy" data-read="out" hidden>Đọc bản dịch</button>
          <button class="copy" data-copy>Chép</button></div>`;
      c.querySelector(".src").textContent = sourceText.slice(0, 300);
      c.querySelector(".out").textContent = res.text;
      c.querySelector("[data-meta]").textContent =
        `${res.engine}${res.detected ? " · nhận ra " + res.detected : ""} · ${res.ms} ms`
        + (res.note ? ` · ${res.note}` : "");

      c.querySelector("[data-copy]").addEventListener("mousedown", async (e) => {
        e.preventDefault();
        try { await navigator.clipboard.writeText(res.text); e.target.textContent = "Đã chép"; }
        catch { e.target.textContent = "Không chép được"; }
      });

      this.#wireRead(c, sourceText, res, target);

      const sel = c.querySelector("[data-lang]");
      for (const [code, name] of LANGS) sel.append(new Option(name, code));
      sel.value = target || "vi";
      sel.addEventListener("change", () => this.onTargetChange(sel.value, sourceText));
      this.#finish(c);
    }

    /** Hien nut Doc cho ben nao co giong. Ben khong co thi an han — mot nut
     *  bam vao chi de bao "chua co giong" thi khong nen ton cho. */
    #wireRead(c, sourceText, res, target) {
      if (!this.ttsLangs?.length) return;
      const base = (x) => (x || "").split("-")[0].toLowerCase();
      const sides = [["src", sourceText, base(res.source || res.detected)],
                     ["out", res.text, base(res.target || target)]];
      for (const [which, text, lang] of sides) {
        const btn = c.querySelector(`[data-read="${which}"]`);
        if (!btn || !text?.trim() || !lang || !this.ttsLangs.includes(lang)) continue;
        btn.hidden = false;
        btn.title = `Giọng ${lang}`;
        btn.addEventListener("mousedown", (e) => {
          e.preventDefault();
          if (this.reading === which) this.onStopSpeak();
          else this.onSpeak(which, text, lang);
        });
      }
    }

    /** Bao loi doc ngay tren nut. Khong dung renderError: no se xoa mat ban
     *  dich ma nguoi dung dang doc — mat nhieu hon duoc. */
    setReadError(which, message) {
      this.reading = null;
      const btn = this.card?.querySelector(`[data-read="${which}"]`);
      if (!btn) return;
      btn.textContent = "Không đọc được";
      btn.title = message || "";
      btn.classList.remove("on");
    }

    /** Doi nhan nut theo ben dang doc. `which` = null nghia la da dung. */
    setReading(which) {
      this.reading = which;
      if (!this.card) return;
      for (const btn of this.card.querySelectorAll("[data-read]")) {
        const mine = btn.dataset.read === which;
        btn.textContent = mine ? "Dừng"
          : btn.dataset.read === "src" ? "Đọc gốc" : "Đọc bản dịch";
        btn.classList.toggle("on", mine);
      }
    }

    renderError(message) {
      const c = this.#card();
      c.innerHTML = `
        <div class="head"><span class="grow">Không dịch được</span><button class="x" data-x aria-label="Đóng">✕</button></div>
        <div class="body"><div class="out err"></div></div>`;
      c.querySelector(".out").textContent = message;
      this.#finish(c);
    }

    destroy() {
      this.host?.remove();
      this.host = this.root = this.bubble = this.card = null;
    }
  }

  NS.ui = { Overlay, LANGS };
})();
