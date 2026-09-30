// Minimal CDP screenshotter (no npm deps; Node 22+ has WebSocket built in).
// Usage: node scripts/screenshot.mjs shots.json
// shots.json: [{"out": "screenshots/x.png", "url": "http://127.0.0.1:43167/#route", "width": 390, "height": 844,
//               "scale": 2, "mobile": true, "ready": "document.querySelector('.stop')"}]
import { spawn } from "node:child_process";
import { writeFileSync, readFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PORT = 9339;
const shots = JSON.parse(readFileSync(process.argv[2], "utf8"));
const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${mkdtempSync(join(tmpdir(), "cdp-"))}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ver;
for (let i = 0; i < 50 && !ver; i++) { try { ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json(); } catch { await sleep(200); } }
try {
  for (const s of shots) {
    const t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json();
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    await new Promise((r) => (ws.onopen = r));
    let id = 0; const pending = new Map();
    ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
    const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
    await send("Emulation.setDeviceMetricsOverride", { width: s.width, height: s.height, deviceScaleFactor: s.scale || 1, mobile: !!s.mobile });
    await send("Page.enable");
    await send("Page.navigate", { url: s.url });
    let ok = false;
    for (let i = 0; i < 100 && !ok; i++) {
      await sleep(250);
      const r = await send("Runtime.evaluate", { expression: `!!(${s.ready})`, returnByValue: true });
      ok = r.result && r.result.result && r.result.result.value === true;
    }
    await sleep(s.settle || 700);
    const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    writeFileSync(s.out, Buffer.from(shot.result.data, "base64"));
    console.log(ok ? "ok   " : "TIMEOUT", s.out);
    ws.close();
  }
} finally { chrome.kill(); }
