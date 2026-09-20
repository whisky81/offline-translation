// Nut Doc tren the dich cua extension.
//
// Duong di day du: content script -> service worker -> tai lieu offscreen ->
// phat -> bao nguoc ve service worker -> chuyen tiep sang tab -> doi nhan nut.
// Dut mot mat xich nao thi nhan nut se ket o "Dung" mai mai.
//
// node tests/e2e_tts_card.mjs <cdpPort> <pageUrl>
import { Page, emit, sleep, targets } from "./cdp.mjs";

const [port, PAGE_URL] = process.argv.slice(2);
const VW = 1100, VH = 800;
const out = { ok: false, consoleErrors: [] };

/** Tim node theo thuoc tinh, xuyen ca shadow root dong. */
function findByAttr(node, name, value, acc = []) {
  const a = node.attributes || [];
  for (let i = 0; i < a.length; i += 2) {
    if (a[i] === name && (value == null || a[i + 1] === value)) acc.push(node);
  }
  for (const k of node.children || []) findByAttr(k, name, value, acc);
  for (const sr of node.shadowRoots || []) findByAttr(sr, name, value, acc);
  return acc;
}

const textOfNode = (n, acc = []) => {
  if (n.nodeType === 3 && n.nodeValue) acc.push(n.nodeValue);
  for (const k of n.children || []) textOfNode(k, acc);
  for (const sr of n.shadowRoots || []) textOfNode(sr, acc);
  return acc;
};

try {
  const page = await Page.open(port);
  await page.s.send("Emulation.setDeviceMetricsOverride",
    { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
  await page.goto(PAGE_URL, 3000);

  // Bo dem cua may doc TRUOC khi bat dau: neu sau nay no tang, nghia la mot
  // yeu cau doc that su den duoc may chu — bang chung manh hon nhan nut.
  const cacheItems = async () =>
    JSON.parse(await page.eval(
      `fetch('/api3/info').then(r=>r.json()).then(j=>JSON.stringify(j.cache.items))`));
  out.cacheBefore = await cacheItems();

  // Mot doan tieng Anh moi tinh moi lan chay, de khong an vao bo dem.
  const phrase = `Reading aloud test number ${Date.now() % 100000}, spoken by the local reader.`;
  await page.eval(`(()=>{
    document.querySelectorAll('.ttsfix').forEach(e=>e.remove());
    const d=document.createElement('div'); d.className='ttsfix';
    d.style.cssText='position:fixed;top:120px;left:20px;width:520px;z-index:1;'
      +'background:#ffd;color:#000;padding:6px;font:15px system-ui';
    d.textContent=${JSON.stringify(phrase)};
    document.body.appendChild(d);})()`);
  await sleep(400);

  const r = JSON.parse(await page.eval(`JSON.stringify((()=>{
    const e=document.querySelector('.ttsfix'); const b=e.getBoundingClientRect();
    return {x:b.left+3,y:b.top+b.height/2,x2:b.right-3};})())`));
  await page.drag(r.x, r.y, r.x2, r.y, 4, 110);
  await sleep(500);

  const bubble = await page.boxOf("btn");
  out.bubbleShown = Boolean(bubble);
  if (!bubble) throw new Error("khong thay nut nho sau khi boi den");
  await page.click(bubble.cx, bubble.cy, 350);
  await sleep(4000);

  const card = await page.boxOf("card");
  out.cardShown = Boolean(card);

  const readButtons = async () => {
    const doc = await page.document();
    return findByAttr(doc, "data-read").map((n) => {
      const a = n.attributes || [];
      const get = (k) => { for (let i = 0; i < a.length; i += 2) if (a[i] === k) return a[i + 1]; };
      return { side: get("data-read"), hidden: get("hidden") != null,
               label: textOfNode(n).join("").trim(), nodeId: n.nodeId };
    });
  };

  out.buttonsOnCard = (await readButtons()).map(({ nodeId, ...b }) => b);

  // Doc BAN DICH (tieng Viet) — day la nut nguoi dung bam nhieu nhat.
  const target = (await readButtons()).find((b) => b.side === "out" && !b.hidden);
  out.foundReadButton = Boolean(target);
  if (!target) throw new Error("khong thay nut doc ban dich tren the");

  const m = (await page.s.send("DOM.getBoxModel", { nodeId: target.nodeId })).result?.model;
  const [bx, by, bx2, , , by3] = m.border;
  await page.click((bx + bx2) / 2, (by + by3) / 2, 120);
  await sleep(900);

  out.labelWhileReading = (await readButtons()).find((b) => b.side === "out")?.label;

  // Tai lieu offscreen phai duoc tao — khong co no thi khong the co tieng.
  const list = await targets(port);
  out.offscreenTarget = list.filter((t) => t.url.includes("offscreen.html"))
                            .map((t) => t.type);

  // Cho het bai roi kiem tra nhan co tu tro ve khong. Day la doan duy nhat
  // chung minh duong bao nguoc (offscreen -> SW -> tab) con song.
  let restored = null;
  for (let i = 0; i < 30; i++) {
    await sleep(1000);
    const lab = (await readButtons()).find((b) => b.side === "out")?.label;
    if (lab && lab !== "Dừng") { restored = { after: i + 1, label: lab }; break; }
  }
  out.labelRestored = restored;
  out.cacheAfter = await cacheItems();
  out.serverGotRequest = out.cacheAfter > out.cacheBefore;

  out.consoleErrors = page.consoleErrors();
  out.ok = true;
  page.close();
} catch (e) {
  out.error = String(e?.message || e);
}
emit(out);
