/**
 * Client cho may chu dich + may doc, dung cho web / desktop app
 * (Electron, Tauri, Node 18+, trinh duyet). Khong phu thuoc thu vien ngoai.
 *
 * Stack chi cong bo MOT cong ra host: nginx tren 127.0.0.1:5001.
 *     /api   -> LibreTranslate (moi cap ngon ngu)
 *     /api2  -> EnViT5         (chi en<->vi, dich sat hon)
 *     /api3  -> Piper          (doc thanh tieng, tra ve WAV)
 *
 * LUU Y VE CORS: may chu KHONG gui Access-Control-Allow-Origin. Do la co y —
 * mot may chu tren loopback ma mo CORS thi bat ky trang web nao ban ghe tham
 * cung goi duoc no tu trinh duyet cua ban. He qua cho app cua ban:
 *   - frontend phuc vu tu chinh :5001 (cung origin) -> chay binh thuong
 *   - dev server o origin khac (vd :5173) -> phai proxy /api* sang :5001
 *   - Electron/Tauri/Node -> khong dinh CORS, goi thang duoc
 */

export interface Language {
  code: string;
  name: string;
  targets: string[];
}

export interface DetectResult {
  language: string;
  confidence: number;
}

export interface LibreTranslateOptions {
  /** Goc cua nginx, vd "http://127.0.0.1:5001". */
  webUrl?: string;
  /** Ghi de duong dan day du toi LibreTranslate (mac dinh `${webUrl}/api`). */
  baseUrl?: string;
  /** Ghi de duong dan day du toi may doc (mac dinh `${webUrl}/api3`). */
  ttsUrl?: string;
  apiKey?: string;
  timeoutMs?: number;
}

export interface Voice {
  id: string;
  lang: string;
  locale: string;
  quality: string;
  sample_rate: number;
  speakers: number;
}

export class LibreTranslateError extends Error {}

export class LibreTranslate {
  private readonly baseUrl: string;
  private readonly ttsUrl: string;
  private readonly apiKey?: string;
  private readonly timeoutMs: number;

  constructor(opts: LibreTranslateOptions = {}) {
    const web = (opts.webUrl ?? "http://127.0.0.1:5001").replace(/\/+$/, "");
    this.baseUrl = (opts.baseUrl ?? `${web}/api`).replace(/\/+$/, "");
    this.ttsUrl = (opts.ttsUrl ?? `${web}/api3`).replace(/\/+$/, "");
    this.apiKey = opts.apiKey;
    this.timeoutMs = opts.timeoutMs ?? 120_000;
  }

  private async request<T>(path: string, body?: unknown): Promise<T> {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), this.timeoutMs);
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method: body ? "POST" : "GET",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body
          ? JSON.stringify(this.apiKey ? { ...(body as object), api_key: this.apiKey } : body)
          : undefined,
        signal: ctl.signal,
      });
      if (!res.ok) {
        throw new LibreTranslateError(`HTTP ${res.status}: ${await res.text()}`);
      }
      return (await res.json()) as T;
    } catch (err) {
      if (err instanceof LibreTranslateError) throw err;
      throw new LibreTranslateError(
        `Khong goi duoc ${this.baseUrl} — may chu dang chay chua? (${String(err)})`,
      );
    } finally {
      clearTimeout(timer);
    }
  }

  languages(): Promise<Language[]> {
    return this.request<Language[]>("/languages");
  }

  detect(q: string): Promise<DetectResult[]> {
    return this.request<DetectResult[]>("/detect", { q });
  }

  /** Dich 1 chuoi. */
  async translate(
    q: string,
    target: string,
    source = "auto",
    format: "text" | "html" = "text",
  ): Promise<string> {
    const r = await this.request<{ translatedText: string }>("/translate", {
      q, source, target, format,
    });
    return r.translatedText;
  }

  /** Dich nhieu chuoi trong 1 request — nhanh hon han goi tung cai. */
  async translateBatch(
    q: string[],
    target: string,
    source = "auto",
    format: "text" | "html" = "text",
  ): Promise<string[]> {
    const r = await this.request<{ translatedText: string[] }>("/translate", {
      q, source, target, format,
    });
    return r.translatedText;
  }

  /** Giong doc dang co. Mang rong nghia la may doc chua bat. */
  async voices(): Promise<Voice[]> {
    try {
      const res = await fetch(`${this.ttsUrl}/voices`);
      return res.ok ? ((await res.json()) as Voice[]) : [];
    } catch {
      return [];
    }
  }

  /**
   * Doc mot doan thanh tieng. Tra ve Blob am thanh (WAV), khong phai JSON.
   *
   * Voi doan dai, dung cat nho theo cau va phat noi tiep: tong hop nhanh hon
   * phat khoang 10 lan, nen doan sau luon tai kip, va tieng bat dau sau
   * ~1 giay thay vi ~10 giay. Xem `web/html/js/tts.js` cho ban day du.
   */
  async speak(q: string, lang = "vi", speed = 1.0): Promise<Blob> {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), this.timeoutMs);
    try {
      const res = await fetch(`${this.ttsUrl}/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q, lang, speed }),
        signal: ctl.signal,
      });
      if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { msg = ((await res.json()) as { error?: string }).error ?? msg; } catch { /* */ }
        throw new LibreTranslateError(msg);
      }
      return await res.blob();
    } catch (err) {
      if (err instanceof LibreTranslateError) throw err;
      throw new LibreTranslateError(`Khong goi duoc may doc ${this.ttsUrl} (${String(err)})`);
    } finally {
      clearTimeout(timer);
    }
  }
}

// --- vi du chay truc tiep: npx tsx examples/client.ts -------------------
if (typeof process !== "undefined" && import.meta.url === `file://${process.argv[1]}`) {
  const lt = new LibreTranslate();
  const langs = await lt.languages();
  console.log("Ngon ngu:", langs.map((l) => l.code).join(", "));
  console.log(await lt.translate("Runs entirely on your own machine.", "vi", "en"));
  console.log(await lt.translateBatch(["Open", "Close", "Retry"], "vi", "en"));

  const voices = await lt.voices();
  if (voices.length) {
    console.log("Giong doc:", voices.map((v) => `${v.id} [${v.lang}]`).join(", "));
    const wav = await lt.speak("Xin chào, đây là máy đọc chạy trên máy bạn.", "vi");
    console.log(`Da doc thanh ${wav.size} byte WAV`);
  } else {
    console.log("May doc chua bat (khong sao — dich van chay).");
  }
}
