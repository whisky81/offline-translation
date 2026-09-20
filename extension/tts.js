// Lop doc thanh tieng. Khong biet gi ve DOM cua trang.
//
// Vi sao khong dung speechSynthesis cua trinh duyet: Chrome/Brave tren Linux
// khong kem giong nao (getVoices() tra ve mang rong), nen nut Doc se im lang.
// Tong hop o may chu Piper qua /api3 thi o dau cung nghe duoc.
//
// TEP NAY CO HAI BAN GIONG HET NHAU:
//     web/html/js/tts.js   — UI web, cung origin nen base la "/api3"
//     extension/tts.js     — extension, base la "http://127.0.0.1:5001/api3"
// Vi the 'base' la tham so chu khong phai hang so, va tests/test_tts_static.py
// so sanh tung byte hai tep de chung khong the troi ra khoi nhau.

const DEFAULT_BASE = "/api3";

// Mot doan ~320 ky tu tong hop het khoang 1 giay va doc het khoang 15 giay,
// nen chi can cat nho the nay la viec tai luon chay truoc viec phat.
const MAX_CHUNK = 320;

export class TtsError extends Error {}

/**
 * Cat van ban thanh cac doan doc duoc, uu tien ranh gioi cau.
 *
 * Vi sao phai cat: tong hop 2000 ky tu mat ~10 giay. Bam Doc roi ngoi cho 10
 * giay thi nguoi dung tuong hong. Cat ra thi tieng bat dau sau ~0.3 giay, va
 * doan sau duoc tai trong luc doan truoc dang phat.
 */
export function chunk(text, max = MAX_CHUNK) {
  const out = [];
  // Giu lai dau cau: '.', '!', '?' va xuong dong deu la cho ngat tu nhien.
  const sentences = text.match(/[^.!?\n]+[.!?]*\n*|\n+/g) || [];
  let buf = "";

  const flush = () => { if (buf.trim()) out.push(buf.trim()); buf = ""; };

  for (const s of sentences) {
    if (buf && buf.length + s.length > max) flush();
    if (s.length <= max) { buf += s; continue; }
    // Mot cau dai hon ca doan cho phep (van ban khong co dau cham). Cat o
    // khoang trang cuoi cung truoc gioi han de khong dut giua tu.
    flush();
    let rest = s;
    while (rest.length > max) {
      const cut = rest.lastIndexOf(" ", max);
      const at = cut > max * 0.5 ? cut : max;   // khong co khoang trang -> cat cung
      out.push(rest.slice(0, at).trim());
      rest = rest.slice(at);
    }
    buf = rest;
  }
  flush();
  return out.filter(Boolean);
}

/** Goi /api3/speak mot lan. Tra ve Blob am thanh. */
async function fetchClip(text, { base, lang, speed, signal }) {
  let res;
  try {
    res = await fetch(`${base}/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q: text, lang, speed }),
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new TtsError(`không gọi được máy đọc (${err.message})`);
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { msg = (await res.json()).error || msg; } catch { /* khong phai JSON */ }
    throw new TtsError(msg);
  }
  return res.blob();
}

export async function ttsAvailable(base = DEFAULT_BASE) {
  try {
    const res = await fetch(`${base}/health`);
    if (!res.ok) return null;
    const h = await res.json();
    return h.voices > 0 ? h : null;
  } catch { return null; }
}

/**
 * Phat lan luot cac doan, tai truoc doan ke tiep.
 *
 * Chi mot lan doc chay tai mot thoi diem. Goi play() lan nua se dung lan cu —
 * nguoi dung bam Doc o o khac thi ho muon nghe cai moi, khong phai nghe chong.
 */
export class Reader {
  constructor({ base = DEFAULT_BASE, onState } = {}) {
    this.base = base;
    this.onState = onState || (() => {});
    this.audio = null;
    this.token = 0;          // tang len la moi viec cua lan truoc bi bo
    this.ctl = null;         // AbortController cua request dang bay
    this.url = null;         // blob URL dang phat, phai thu hoi sau khi dung
  }

  get playing() { return Boolean(this.audio) && !this.audio.paused; }

  #cleanupUrl() {
    if (this.url) { URL.revokeObjectURL(this.url); this.url = null; }
  }

  /**
   * Bo moi viec dang chay.
   *
   * `notify` = false khi mot lan doc MOI sap bat dau ngay sau do. Neu van bao
   * "stopped", ben goi se tuong lan doc moi da ket thuc va tat den nut ngay
   * truoc khi tieng dau tien kip phat.
   */
  #halt(notify) {
    this.token++;
    this.ctl?.abort();
    this.ctl = null;
    if (this.audio) { this.audio.pause(); this.audio.removeAttribute("src"); }
    this.#cleanupUrl();
    if (notify) this.onState({ state: "stopped" });
  }

  stop() { this.#halt(true); }

  /** Phat mot Blob den het. Tra ve false neu lan doc nay da bi huy. */
  #playBlob(blob, mine) {
    return new Promise((resolve, reject) => {
      if (mine !== this.token) return resolve(false);
      this.#cleanupUrl();
      this.url = URL.createObjectURL(blob);
      this.audio ||= new Audio();
      const a = this.audio;
      a.onended = () => resolve(true);
      // Loi phat lai (codec hong, blob rong) khong nem exception ma bao qua
      // su kien 'error' — khong bat thi Promise treo mai mai.
      a.onerror = () => reject(new TtsError("trình duyệt không phát được đoạn âm thanh này"));
      a.src = this.url;
      a.play().catch(reject);
    });
  }

  async play(text, { lang, speed = 1.0 } = {}) {
    this.#halt(false);
    const mine = ++this.token;
    const parts = chunk(text);
    if (!parts.length) { this.onState({ state: "stopped" }); return; }

    this.ctl = new AbortController();
    const { signal } = this.ctl;
    const get = (i) => {
      const p = fetchClip(parts[i], { base: this.base, lang, speed, signal });
      // Doan tai truoc co the KHONG BAO GIO duoc await: nguoi dung bam Dung
      // giua chung thi vong lap thoat ra va bo lai no dang bay. Khi do
      // ctl.abort() lam no bi tu choi, va mot promise bi tu choi ma khong ai
      // bat se noi len console thanh "Uncaught (in promise)".
      // .catch() rong o day danh dau no la da xu ly; promise goc van nem loi
      // binh thuong cho cho nao that su await no.
      p.catch(() => {});
      return p;
    };

    try {
      this.onState({ state: "loading", index: 0, total: parts.length });
      let next = get(0);
      for (let i = 0; i < parts.length; i++) {
        const blob = await next;
        if (mine !== this.token) return;
        // Bat doan ke tiep chay NGAY, truoc khi phat doan nay: tong hop nhanh
        // hon phat khoang 10 lan nen tu doan thu hai tro di se khong con cho.
        next = i + 1 < parts.length ? get(i + 1) : null;
        this.onState({ state: "playing", index: i, total: parts.length });
        if (!(await this.#playBlob(blob, mine))) return;
      }
      if (mine !== this.token) return;
      this.#cleanupUrl();
      this.onState({ state: "stopped" });
    } catch (err) {
      if (err.name === "AbortError" || mine !== this.token) return;
      this.#cleanupUrl();
      this.onState({ state: "error", error: err.message });
    } finally {
      if (mine === this.token) this.ctl = null;
    }
  }
}
