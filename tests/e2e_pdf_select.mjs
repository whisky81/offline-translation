// Boi den trong lop van ban pdf.js, canh chinh voi canvas, va cuon khong
// duoc lam mat ban dich. Tach khoi e2e_pdf.mjs vi gop chung mot phien thi
// the dich dang mo se che dung vung chu sap keo qua.
//
// node tests/e2e_pdf_select.mjs <cdpPort> <extensionId> <pdfUrl>
import { Page, emit, sleep } from "./cdp.mjs";

const [port, EXT, PDF] = process.argv.slice(2);
const out = { ok: false };

/** Cuon mot span vao giua man hinh roi tra ve toa do de keo chuot.
 *  Loc theo khung nhin la khong du: sau khi cuon, span co the nam ngoai va
 *  moi phep thu sau do se roi vao cho trong. */
async function spanToDrag(page, index = 1) {
  const ok = await page.eval(`(()=>{
    const sp=[...document.querySelectorAll('.textLayer span')]
      .filter(e=>e.textContent.trim().length>10);
    const s=sp[${index}] || sp[0];
    if(!s) return false;
    s.scrollIntoView({block:'center'});
    return true;})()`);
  if (!ok) return null;
  await sleep(500);
  const raw = await page.eval(`JSON.stringify((()=>{
    const sp=[...document.querySelectorAll('.textLayer span')]
      .filter(e=>e.textContent.trim().length>10);
    const s=sp[${index}] || sp[0];
    const r=s.getBoundingClientRect();
    return {x:r.left+2,y:r.top+r.height/2,x2:r.left+Math.min(150,r.width-4)};})())`);
  return raw ? JSON.parse(raw) : null;
}

try {
  const page = await Page.open(port);
  await page.goto(`chrome-extension://${EXT}/viewer.html?file=${encodeURIComponent(PDF)}`);
  const rendered = await page.waitFor(
    "document.querySelector('.page') && document.querySelectorAll('.textLayer span').length",
    { tries: 30, every: 600 });
  if (!rendered) throw new Error("PDF khong render xong trong thoi gian cho");

  out.textLayers = await page.eval("document.querySelectorAll('.textLayer').length");
  out.endOfContent = await page.eval("document.querySelectorAll('.endOfContent').length");
  out.spans = await page.eval("document.querySelectorAll('.textLayer span').length");

  // Lop chu vo hinh co trung khop voi chu ve tren canvas khong: doc thang pixel
  // de tim mep phai cua ink roi so voi mep phai cua span.
  out.alignment = JSON.parse(await page.eval(`JSON.stringify((()=>{
    const pg = document.querySelector('.page');
    const canvas = pg.querySelector('canvas');
    const spans = [...pg.querySelectorAll('.textLayer span')].filter(s=>s.textContent.trim().length>5);
    if (!canvas || !spans.length) return null;
    const ratio = canvas.width / canvas.getBoundingClientRect().width;
    const cr = canvas.getBoundingClientRect();
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    const rows = [];
    for (const s of spans.slice(0, 3)) {
      const r = s.getBoundingClientRect();
      const top = Math.max(0, Math.round((r.top - cr.top) * ratio));
      const h = Math.max(1, Math.round(r.height * ratio));
      const img = ctx.getImageData(0, top, canvas.width, h).data;
      let ink = -1;
      for (let y = 0; y < h; y++) {
        for (let x = canvas.width - 1; x > ink; x--) {
          const i = (y * canvas.width + x) * 4;
          if (img[i] < 200 || img[i+1] < 200 || img[i+2] < 200) { ink = x; break; }
        }
      }
      if (ink < 0) continue;
      const inkCss = cr.left + ink / ratio;
      rows.push({ span: Math.round(r.right), ink: Math.round(inkCss),
                  gap: Math.round(r.right - inkCss) });
    }
    return rows;})())`) || "null");

  // Keo qua nhieu dong: chu lay duoc phai lien mach
  const multi = JSON.parse(await page.eval(`JSON.stringify((()=>{
    const sp=[...document.querySelectorAll('.textLayer span')].filter(e=>e.textContent.trim().length>10);
    if (sp.length < 5) return null;
    const a=sp[2].getBoundingClientRect(), b=sp[6].getBoundingClientRect();
    return {x1:a.left+2,y1:a.top+a.height/2,x2:b.left+180,y2:b.top+b.height/2};})())`) || "null");
  if (!multi) throw new Error("tep thu qua it dong");

  await page.mouse("mousePressed", multi.x1, multi.y1);
  await sleep(150);
  out.selectingDuringDrag = await page.eval("!!document.querySelector('.textLayer.selecting')");
  for (let k = 1; k <= 10; k++) {
    await page.s.send("Input.dispatchMouseEvent", { type: "mouseMoved",
      x: multi.x1 + (multi.x2 - multi.x1) * k / 10,
      y: multi.y1 + (multi.y2 - multi.y1) * k / 10, button: "left", buttons: 1 });
    await sleep(40);
  }
  await page.mouse("mouseReleased", multi.x2, multi.y2);
  await sleep(600);
  out.selectingAfterRelease = await page.eval("!!document.querySelector('.textLayer.selecting')");

  const text = await page.eval("String(window.getSelection())");
  out.lineCount = text.split("\n").filter((l) => l.trim()).length;
  const nums = [...text.matchAll(/line (\d+)/g)].map((m) => +m[1]);
  out.lineNumbers = nums;
  out.contiguous = nums.length >= 3 && nums.every((n, i) => i === 0 || n === nums[i - 1] + 1);

  // Bam dich, cho ban dich THAT (khong phai chi cho the hien ra), roi cuon
  const bubble = await page.boxOf("btn");
  out.bubbleShown = Boolean(bubble);
  if (bubble) {
    await page.click(bubble.cx, bubble.cy);
    for (let i = 0; i < 25; i++) {
      const t = await page.textIn("out");
      if (t && t !== "…") break;
      await sleep(400);
    }
    out.translationText = await page.textIn("out");
    out.cardBeforeScroll = await page.isShown("card");
    await page.wheel(120, 400, 140);
    await sleep(900);
    out.cardAfterScroll = await page.isShown("card");
    out.bubbleAfterScroll = await page.isShown("btn");
    await page.key("Escape");
    await sleep(400);
    out.cardAfterEscape = await page.isShown("card");
    const card = await page.nodeByClass("card");
    if (card) {
      const at = (await page.s.send("DOM.getAttributes", { nodeId: card.nodeId })).result?.attributes || [];
      for (let i = 0; i < at.length; i += 2) if (at[i] === "style") out.cardStyleAfterEscape = at[i + 1];
    }
  }

  // Bam Esc NGAY TRONG LUC dang dich: ket qua khong duoc tu bat len lai
  const again = await spanToDrag(page, 1);
  if (again) {
    await page.drag(again.x, again.y, again.x2, again.y, 3, 100);
    const b2 = await page.boxOf("btn");
    if (b2) {
      await page.click(b2.cx, b2.cy, 60);
      await sleep(60);
      await page.key("Escape");
      await sleep(3500);
      out.cardAfterEscapeMidFlight = await page.isShown("card");
    }
  }

  // Nap content.js lan hai: ban cu phai tu don, khong nhan doi UI
  out.hostsBefore = await page.eval("document.querySelectorAll('#dich-offline-root').length");
  // Nap lai CA BO theo dung thu tu, giong luc trang khoi tao.
  await page.eval(`(async()=>{
    for (const f of ['content/placement.js','content/selection.js','content/ui.js','content/main.js']) {
      await new Promise(r=>{const sc=document.createElement('script');
        sc.src=f; sc.onload=r; sc.onerror=r; document.head.appendChild(sc);});
    }})()`);
  await sleep(800);
  out.hostsAfterReinject = await page.eval("document.querySelectorAll('#dich-offline-root').length");
  out.cleanupExposed = await page.eval("typeof window.__dichOfflineCleanup");

  const again2 = await spanToDrag(page, 0);
  if (again2) {
    await page.drag(again2.x, again2.y, again2.x2, again2.y, 3, 100);
    out.hostsAfterUse = await page.eval("document.querySelectorAll('#dich-offline-root').length");
    out.bubbleAfterReinject = await page.isShown("btn");
  }

  out.ok = true;
  page.close();
} catch (e) {
  out.error = String(e?.message || e);
}
emit(out);
