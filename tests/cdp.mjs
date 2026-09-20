// Tien ich dieu khien Chrome DevTools Protocol, dung chung cho cac driver e2e.
//
// Truoc day bon driver deu tu viet lai `conn`, `findCls`, `txt`, cach bam chuot,
// cach doc box model — bon ban sao hoi khac nhau. Gop vao day de sua mot cho.

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Mo mot phien CDP toi mot target. Tra ve doi tuong co send/events/close. */
export function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  const events = [];
  const ready = new Promise((r) => ws.addEventListener("open", r));
  ws.addEventListener("message", (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id != null && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    else if (msg.method) events.push(msg);
  });
  const send = async (method, params = {}) => {
    await ready;
    const mid = ++id;
    return new Promise((r) => { pending.set(mid, r); ws.send(JSON.stringify({ id: mid, method, params })); });
  };
  return { send, events, close: () => ws.close() };
}

export async function targets(port) {
  return (await (await fetch(`http://127.0.0.1:${port}/json`)).json());
}

export async function firstPage(port) {
  return (await targets(port)).find((t) => t.type === "page");
}

export async function serviceWorker(port) {
  return (await targets(port)).find((t) => t.type === "service_worker");
}

/** Tim moi node mang mot class, xuyen ca shadow root dong (pierce). */
export function findByClass(node, cls, acc = []) {
  const attrs = node.attributes || [];
  for (let i = 0; i < attrs.length; i += 2) {
    if (attrs[i] === "class" && attrs[i + 1].split(/\s+/).includes(cls)) acc.push(node);
  }
  for (const kid of node.children || []) findByClass(kid, cls, acc);
  for (const sr of node.shadowRoots || []) findByClass(sr, cls, acc);
  return acc;
}

/** Gom toan bo text node ben trong mot node (ke ca trong shadow root). */
export function textOf(node, acc = []) {
  if (node.nodeType === 3 && node.nodeValue) acc.push(node.nodeValue);
  for (const kid of node.children || []) textOf(kid, acc);
  for (const sr of node.shadowRoots || []) textOf(sr, acc);
  return acc;
}

/** Lop tien ich gan voi mot trang: danh gia JS, tim node, bam chuot. */
export class Page {
  constructor(session) { this.s = session; }

  static async open(port) {
    const t = await firstPage(port);
    if (!t) throw new Error("khong tim thay target kieu page");
    const p = new Page(connect(t.webSocketDebuggerUrl));
    for (const d of ["Page", "Runtime", "DOM", "Log"]) await p.s.send(`${d}.enable`);
    return p;
  }

  close() { this.s.close(); }

  async goto(url, settleMs = 0) {
    await this.s.send("Page.navigate", { url });
    if (settleMs) await sleep(settleMs);
  }

  /** Danh gia bieu thuc trong MAIN world cua trang. */
  async eval(expression) {
    const r = await this.s.send("Runtime.evaluate",
      { expression, returnByValue: true, awaitPromise: true });
    if (r.result?.exceptionDetails) {
      throw new Error("eval loi: " + (r.result.exceptionDetails.exception?.description
        || r.result.exceptionDetails.text || "").slice(0, 200));
    }
    return r.result?.result?.value;
  }

  /** Cho den khi bieu thuc tra ve gia tri that (hoac het gio). */
  async waitFor(expression, { tries = 20, every = 500 } = {}) {
    for (let i = 0; i < tries; i++) {
      try { if (await this.eval(expression)) return true; } catch { /* trang chua san sang */ }
      await sleep(every);
    }
    return false;
  }

  async document() {
    return (await this.s.send("DOM.getDocument", { depth: -1, pierce: true })).result.root;
  }

  async nodeByClass(cls) {
    return findByClass(await this.document(), cls)[0] || null;
  }

  /** Hop bao cua phan tu, hoac null neu no khong duoc hien thi. */
  async boxOf(cls) {
    const n = await this.nodeByClass(cls);
    if (!n) return null;
    const m = (await this.s.send("DOM.getBoxModel", { nodeId: n.nodeId })).result?.model;
    if (!m) return null;
    const [x1, y1, x2, , , y3] = m.border;
    return { x: x1, y: y1, right: x2, bottom: y3,
             cx: (x1 + x2) / 2, cy: (y1 + y3) / 2,
             width: m.width, height: m.height };
  }

  async isShown(cls) { return Boolean(await this.boxOf(cls)); }

  /** Text ben trong phan tu dau tien mang class do. */
  async textIn(cls) {
    const n = await this.nodeByClass(cls);
    return n ? textOf(n).join("").trim() : "";
  }

  async mouse(type, x, y, { clickCount = 1 } = {}) {
    await this.s.send("Input.dispatchMouseEvent", {
      type, x, y, button: "left",
      // Nha chuot phai bao buttons: 0, neu khong trinh duyet coi nhu van dang giu.
      buttons: type === "mouseReleased" ? 0 : 1,
      clickCount,
    });
  }

  /** Keo chuot tu (x1,y1) den (x2,y2) qua nhieu buoc, giong nguoi that. */
  async drag(x1, y1, x2, y2, steps = 8, stepMs = 45) {
    await this.mouse("mousePressed", x1, y1);
    for (let k = 1; k <= steps; k++) {
      await this.s.send("Input.dispatchMouseEvent", {
        type: "mouseMoved", x: x1 + (x2 - x1) * k / steps, y: y1 + (y2 - y1) * k / steps,
        button: "left", buttons: 1 });
      await sleep(stepMs);
    }
    await this.mouse("mouseReleased", x2, y2);
    await sleep(400);
  }

  async click(x, y, holdMs = 150) {
    await this.mouse("mousePressed", x, y);
    await sleep(holdMs);
    await this.mouse("mouseReleased", x, y);
  }

  async wheel(x, y, deltaY) {
    await this.s.send("Input.dispatchMouseEvent", { type: "mouseWheel", x, y, deltaX: 0, deltaY });
  }

  async key(key, code = key) {
    const vk = key === "Escape" ? 27 : 0;
    for (const type of ["keyDown", "keyUp"]) {
      await this.s.send("Input.dispatchKeyEvent", { type, key, code, windowsVirtualKeyCode: vk });
    }
  }

  /** Loi va canh bao muc error da ghi nhan tu luc bat Log. */
  consoleErrors() {
    return this.s.events
      .filter((e) => e.method === "Runtime.exceptionThrown"
        || (e.method === "Log.entryAdded" && e.params.entry.level === "error"))
      .map((e) => JSON.stringify(e.params).slice(0, 200));
  }

  clearEvents() { this.s.events.length = 0; }
}

/** In ket qua ra stdout duoi dang MOT dong JSON de phia Python doc. */
export function emit(out) {
  console.log(JSON.stringify(out));
  process.exit(0);
}
