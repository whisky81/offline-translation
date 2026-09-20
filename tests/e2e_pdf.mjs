// Luong dich trong trinh doc PDF: mo tep, boi den, bam nut, doc ban dich.
// node tests/e2e_pdf.mjs <cdpPort> <extensionId> <pdfUrl>
import { Page, emit, sleep } from "./cdp.mjs";

const [port, EXT, PDF] = process.argv.slice(2);
const out = { ok: false };

try {
  const page = await Page.open(port);
  await page.goto(`chrome-extension://${EXT}/viewer.html?file=${encodeURIComponent(PDF)}`);
  const rendered = await page.waitFor(
    "document.querySelector('.page') && document.querySelectorAll('.textLayer span').length",
    { tries: 30, every: 600 });
  if (!rendered) throw new Error("PDF khong render xong trong thoi gian cho");

  out.pages = await page.eval("document.querySelectorAll('.page').length");
  out.spans = await page.eval("document.querySelectorAll('.textLayer span').length");
  out.text = await page.eval("(document.querySelector('.textLayer')?.textContent||'').slice(0,80)");
  out.tip = await page.eval("document.getElementById('tip').textContent");
  out.consoleErrors = page.consoleErrors().length;
  // Ke ca canh bao: trang loi cua extension khong duoc day warning tu pdf.js.
  out.consoleWarnings = page.s.events.filter(
    (e) => e.method === "Log.entryAdded" && e.params.entry.level === "warning").length;

  // pdf.js can WebAssembly de giai ma anh JBIG2 / JPEG2000 trong PDF quet.
  // CSP mac dinh cua MV3 (script-src 'self') chan WebAssembly.
  out.wasmAllowed = await page.eval(`(async()=>{
    try { await WebAssembly.instantiate(new Uint8Array([0,97,115,109,1,0,0,0])); return true; }
    catch { return false; }})()`);

  const span = await page.eval(`JSON.stringify((()=>{
    const s=[...document.querySelectorAll('.textLayer span')].find(e=>e.textContent.trim().length>10);
    if(!s) return null; const r=s.getBoundingClientRect();
    return {x:r.left+1,y:r.top+r.height/2,x2:r.right-1};})())`);
  if (span) {
    const v = JSON.parse(span);
    await page.drag(v.x, v.y, v.x2, v.y, 3, 120);
    await sleep(500);
    out.selected = await page.eval("String(window.getSelection())");

    const bubble = await page.boxOf("btn");
    out.bubbleShown = Boolean(bubble);
    if (bubble) {
      await page.click(bubble.cx, bubble.cy);
      for (let i = 0; i < 24; i++) {
        await sleep(500);
        const txt = await page.textIn("out");
        if (txt && txt !== "…") {
          out.translation = txt;
          out.isError = Boolean(await page.nodeByClass("err"));
          out.meta = await page.textIn("foot");
          break;
        }
      }
    }
  }
  out.ok = true;
  page.close();
} catch (e) {
  out.error = String(e?.message || e);
}
emit(out);
