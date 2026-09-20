// Vi tri popup o bon goc man hinh, va the phai song sot khi nha chuot cham.
// node tests/e2e_placement.mjs <cdpPort> <pageUrl>
import { Page, emit, sleep } from "./cdp.mjs";

const [port, PAGE_URL] = process.argv.slice(2);
const VW = 1000, VH = 700;
const out = { ok: false, corners: {} };
const inside = (b) => b.x >= -1 && b.y >= -1 && b.right <= VW + 1 && b.bottom <= VH + 1;

try {
  const page = await Page.open(port);
  await page.s.send("Emulation.setDeviceMetricsOverride",
    { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
  await page.goto(PAGE_URL, 3000);

  await page.eval(`(()=>{
    document.querySelectorAll('.corner').forEach(e=>e.remove());
    for (const [id,css] of [['tl','top:4px;left:4px'],['tr','top:4px;right:4px'],
                            ['bl','bottom:4px;left:4px'],['br','bottom:4px;right:4px']]) {
      const d=document.createElement('div'); d.className='corner'; d.id='c-'+id;
      d.style.cssText='position:fixed;z-index:1;font:14px system-ui;background:#ffd;padding:2px 4px;'+css;
      d.textContent='Good morning everyone, how are you today?';
      document.body.appendChild(d);}})()`);
  await sleep(400);

  for (const id of ["tl", "tr", "bl", "br"]) {
    const v = JSON.parse(await page.eval(`JSON.stringify((()=>{
      const e=document.getElementById('c-${id}'); const r=e.getBoundingClientRect();
      return {x:r.left+2,y:r.top+r.height/2,x2:r.right-2};})())`));
    await page.drag(v.x, v.y, v.x2, v.y, 3, 120);
    await sleep(400);

    const bubble = await page.boxOf("btn");
    const rec = { bubbleShown: Boolean(bubble) };
    if (bubble) {
      rec.bubbleInside = inside(bubble);
      // Giu chuot 400ms: du lau de ban dich ve TRUOC khi nha. Day chinh la
      // tinh huong tung lam the bien mat (mouseup roi xuong trang ben duoi).
      await page.click(bubble.cx, bubble.cy, 400);
      await sleep(2800);
      const card = await page.boxOf("card");
      rec.cardShown = Boolean(card);
      if (card) {
        rec.cardInside = inside(card);
        rec.cardBox = [Math.round(card.x), Math.round(card.y),
                       Math.round(card.width), Math.round(card.height)];
      }
    }
    out.corners[id] = rec;
    await page.key("Escape");
    await sleep(300);
  }
  out.ok = true;
  page.close();
} catch (e) {
  out.error = String(e?.message || e);
}
emit(out);
