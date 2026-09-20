// Nut Doc tren UI web: co hien khong, co goi /api3/speak khong, co phat that
// khong, va co bi CSP chan khong.
// node tests/e2e_tts_web.mjs <cdpPort> <baseUrl>
import { Page, emit, sleep } from "./cdp.mjs";

const [port, BASE_URL] = process.argv.slice(2);
const out = { ok: false, consoleErrors: [] };
const $ = (id) => `document.getElementById('${id}')`;

// Cai truoc khi trang chay: bat vi pham CSP, dem lan goi may doc, va bat moi
// lan phat. Khong lam the nay thi mot nut "Doc" bam vao khong ra tieng se van
// trong nhu dat, vi the <audio> khong nam trong DOM de ma soi.
const PROBE = `
window.__tts = { plays: [], csp: [], speaks: 0, ended: 0, playError: null };
document.addEventListener('securitypolicyviolation',
  e => window.__tts.csp.push(e.violatedDirective + ' <- ' + e.blockedURI));
const _play = HTMLMediaElement.prototype.play;
HTMLMediaElement.prototype.play = function () {
  window.__tts.plays.push(String(this.src).slice(0, 5));
  this.addEventListener('ended', () => window.__tts.ended++, { once: true });
  return _play.call(this).catch((e) => {
    window.__tts.playError = String(e && e.message || e);
    throw e;
  });
};
const _fetch = window.fetch;
window.__tts.calls = [];
window.fetch = function (...a) {
  if (!String(a[0]).includes('/api3/speak')) return _fetch.apply(this, a);
  window.__tts.speaks++;
  const t0 = Date.now();
  const rec = { ms: null, status: null, err: null };
  window.__tts.calls.push(rec);
  return _fetch.apply(this, a).then(
    (r) => { rec.ms = Date.now() - t0; rec.status = r.status; return r; },
    (e) => { rec.ms = Date.now() - t0; rec.err = String(e && e.message || e); throw e; });
};
`;

const probe = (k) => `window.__tts.${k}`;

/** Cuon nut vao giua man hinh roi tra ve tam cua no. Bat buoc: getBoundingClientRect
 *  cua mot phan tu nam duoi fold cho ra y > chieu cao khung nhin, va cu bam
 *  vao do thi khong trung gi ca — nut trong nhu hong. */
async function centerOf(page, id) {
  await page.eval(`document.getElementById('${id}').scrollIntoView({block:'center'})`);
  await sleep(150);
  return JSON.parse(await page.eval(
    `(()=>{const r=document.getElementById('${id}').getBoundingClientRect();
      return JSON.stringify({x:r.x+r.width/2, y:r.y+r.height/2, w:r.width, h:r.height})})()`));
}
const label = (id) => `${$(id)}.textContent`;

try {
  const page = await Page.open(port);
  await page.s.send("Page.addScriptToEvaluateOnNewDocument", { source: PROBE });
  await page.goto(BASE_URL, 1200);
  await page.eval("(()=>{try{localStorage.clear()}catch{}})()");
  page.clearEvents();
  await page.s.send("Page.reload", { ignoreCache: true });
  await sleep(3500);

  // --- may doc co duoc nhan ra khong ---
  out.rateVisible = !(await page.eval(`${$("rate")}.hidden`));
  out.readoutVisible = !(await page.eval(`${$("readout")}.hidden`));
  out.readinVisible = !(await page.eval(`${$("readin")}.hidden`));
  // Chua co chu -> phai tat, khong de bam vao roi bao loi.
  out.readoutDisabledWhenEmpty = await page.eval(`${$("readout")}.disabled`);

  const type = (t) => page.eval(`(()=>{const i=${$("input")};
    i.value=${JSON.stringify(t)}; i.dispatchEvent(new Event('input',{bubbles:true}));})()`);

  // --- dich mot cau roi doc ban dich ---
  await type("The reader runs on your own machine.");
  await page.waitFor(`${$("output")}.textContent.length > 3`, { tries: 20 });
  await sleep(400);
  out.translation = await page.eval(`${$("output")}.textContent`);
  out.readoutEnabledAfter = !(await page.eval(`${$("readout")}.disabled`));

  const { x, y, w, h } = await centerOf(page, "readout");
  out.readoutBox = { x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h) };
  out.viewport = await page.eval("JSON.stringify([innerWidth,innerHeight])");
  await page.click(x, y);
  await sleep(250);
  out.labelRightAfterClick = await page.eval(label("readout"));

  await page.waitFor(`${probe("plays")}.length > 0`, { tries: 60, every: 300 });
  out.speaks = await page.eval(probe("speaks"));
  out.plays = await page.eval(probe("plays"));
  out.playError = await page.eval(probe("playError"));
  out.labelWhilePlaying = await page.eval(label("readout"));
  out.blobUrlUsed = (out.plays || []).every((p) => p === "blob:");

  // --- bam lan nua = dung ---
  await page.click(x, y);
  await sleep(500);
  out.labelAfterStop = await page.eval(label("readout"));

  // --- van ban dai phai duoc cat thanh nhieu doan ---
  await page.eval(`${probe("speaks")} = 0`);
  const tag = Date.now() % 100000;
  await type(`Đoạn thử số ${tag}. ` + [...Array(12)].map((_, i) =>
    `Câu thứ ${i} của lần chạy ${tag} dài vừa đủ để buộc bộ đọc cắt ra nhiều đoạn.`).join(" "));
  await page.waitFor(`${$("readin")}.disabled === false`, { tries: 20 });
  const bi = await centerOf(page, "readin");
  await page.click(bi.x, bi.y);
  await page.waitFor(`${probe("speaks")} >= 2`, { tries: 40, every: 500 });
  out.chunkedSpeaks = await page.eval(probe("speaks"));
  out.readinLabelWhilePlaying = await page.eval(label("readin"));

  // dung lai cho gon
  await page.click(bi.x, bi.y);
  await sleep(300);

  out.calls = await page.eval(probe("calls"));
  out.cspViolations = await page.eval(probe("csp"));
  out.consoleErrors = page.consoleErrors();
  out.ok = true;
  page.close();
} catch (e) {
  out.error = String(e?.message || e);
}
emit(out);
