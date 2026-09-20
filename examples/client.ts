/**
 * Client LibreTranslate cho web / desktop app (Electron, Tauri, Node 18+, trinh duyet).
 * Khong phu thuoc thu vien ngoai — chi dung fetch.
 *
 * May chu da bat CORS `Access-Control-Allow-Origin: *`, nen goi truc tiep
 * tu frontend chay o origin khac (vd http://localhost:5173) van duoc.
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
  baseUrl?: string;
  apiKey?: string;
  timeoutMs?: number;
}

export class LibreTranslateError extends Error {}

export class LibreTranslate {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly timeoutMs: number;

  constructor(opts: LibreTranslateOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? "http://127.0.0.1:5000").replace(/\/+$/, "");
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
}

// --- vi du chay truc tiep: npx tsx examples/client.ts -------------------
if (typeof process !== "undefined" && import.meta.url === `file://${process.argv[1]}`) {
  const lt = new LibreTranslate();
  const langs = await lt.languages();
  console.log("Ngon ngu:", langs.map((l) => l.code).join(", "));
  console.log(await lt.translate("Runs entirely on your own machine.", "vi", "en"));
  console.log(await lt.translateBatch(["Open", "Close", "Retry"], "vi", "en"));
}
