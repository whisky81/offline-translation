// UI tieng Viet: khong ngoai le luc nap, trang thai dang dich, doi chieu, lich su.
// node tests/e2e_webui.mjs <cdpPort> <baseUrl>
import { Page, emit, sleep } from "./cdp.mjs";

const [port, BASE_URL] = process.argv.slice(2);
const out = { ok: false, consoleErrors: [] };
const $ = (id) => `document.getElementById('${id}')`;

try {
  const page = await Page.open(port);
  await page.goto(BASE_URL, 1500);
  await page.eval("(()=>{try{localStorage.clear()}catch{}})()");
  page.clearEvents();
  await page.s.send("Page.reload", { ignoreCache: true });
  await sleep(3500);

  out.consoleErrors = page.consoleErrors();
  out.bootFinished = Boolean(await page.eval(`${$("status")}.textContent`));
  out.defaultSource = await page.eval(`${$("src")}.value`);
  out.defaultEngine = await page.eval(`${$("engine")}.value`);
  out.swapDisabledAtStart = await page.eval(`${$("swap")}.disabled`);

  const type = (t) => page.eval(`(()=>{const i=${$("input")};
    i.value=${JSON.stringify(t)}; i.dispatchEvent(new Event('input',{bubbles:true}));})()`);

  await type("The server runs entirely on your own machine and never sends data out.");
  await sleep(500);
  out.busyWhileTranslating = await page.eval(`${$("output")}.classList.contains('busy')`);
  out.busyLabel = await page.eval(`${$("timing")}.textContent`);
  await sleep(3200);
  out.busyCleared = !(await page.eval(`${$("output")}.classList.contains('busy')`));
  out.translation = await page.eval(`${$("output")}.textContent`);
  out.engineUsed = await page.eval(`${$("timing")}.textContent`);
  out.swapEnabledAfter = !(await page.eval(`${$("swap")}.disabled`));

  await page.eval(`(()=>{const s=${$("src")}; s.value='vi'; s.dispatchEvent(new Event('change'));})()`);
  await sleep(700);
  out.sameLangOptionDisabled = await page.eval(
    `[...${$("tgt")}.options].find(o=>o.value==='vi')?.disabled`);
  out.targetMovedOff = await page.eval(`${$("tgt")}.value`);

  await page.eval(`(()=>{const t=${$("tgt")};
    [...t.options].forEach(o=>o.disabled=false); t.value='vi';})()`);
  await type("Hôm nay trời rất đẹp và tôi muốn đi dạo quanh hồ.");
  await sleep(3200);
  out.flipNote = await page.eval(`${$("timing")}.textContent`);
  out.flipResult = await page.eval(`${$("output")}.textContent`);
  out.historyCount = await page.eval(`${$("histcount")}.textContent`);
  out.clearHistEnabled = !(await page.eval(`${$("clearhist")}.disabled`));

  out.ok = true;
  page.close();
} catch (e) {
  out.error = String(e?.message || e);
}
emit(out);
