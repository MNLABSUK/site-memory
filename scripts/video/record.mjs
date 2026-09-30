// Screen-records the real Site Memory UI via Chrome DevTools screencast (no npm deps).
// node record.mjs <chromePath> <baseUrl> <outDir> [narr.json]
import { spawn } from "node:child_process";
import { writeFileSync, readFileSync, mkdirSync, mkdtempSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const [CHROME, BASE, OUT, NARR] = process.argv.slice(2);
const HERE = dirname(fileURLToPath(import.meta.url));
const script = JSON.parse(readFileSync(join(HERE, "script.json"), "utf8"));
const narr = NARR && existsSync(NARR) ? JSON.parse(readFileSync(NARR, "utf8"))
  : Object.fromEntries(Object.entries(script).map(([k, v]) => [k, v.split(/\s+/).length / 2.7]));
const OVERLAY = readFileSync(join(HERE, "overlay.js"), "utf8");
mkdirSync(join(OUT, "frames"), { recursive: true });
const PORT = 9400 + Math.floor(Math.random() * 400);
const chrome = spawn(CHROME, ["--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--force-color-profile=srgb",
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "rec-"))}`, "--window-size=1280,720", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ver; for (let i = 0; i < 60 && !ver; i++) { try { ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json(); } catch { await sleep(250); } }
const t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json();
const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map(); const frames = []; const events = []; let t0 = null;
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); return; }
  if (d.method === "Page.screencastFrame") {
    const { data, metadata, sessionId } = d.params; const n = frames.length;
    writeFileSync(join(OUT, "frames", `f${String(n).padStart(6, "0")}.jpg`), Buffer.from(data, "base64"));
    frames.push({ n, ts: metadata.timestamp });
    ws.send(JSON.stringify({ id: ++id, method: "Page.screencastFrameAck", params: { sessionId } }));
  }
};
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const now = () => Date.now() / 1000;
const mark = (name) => { events.push({ name, t: now() }); console.log(`[${(now() - t0).toFixed(1)}s] ${name}`); };
async function js(expr) {
  const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result && r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text);
  return r.result && r.result.result ? r.result.result.value : undefined;
}
async function waitFor(expr, timeout = 90000) { const s = Date.now(); while (Date.now() - s < timeout) { if (await js(`!!(${expr})`)) return true; await sleep(200); } throw new Error("timeout: " + expr); }
const R = (call) => js(`window.__rec.${call}`);
const q = (s) => JSON.stringify(s);
// Hold so the scene is at least as long as its narration (plus a breath).
async function holdScene(name, extra = 0.8) { const st = events.find((e) => e.name === name + ":start").t; const left = narr[name] + extra - (now() - st - compressed(st)); if (left > 0) await sleep(left * 1000); }
const fast = []; function compressed(since) { return fast.filter((f) => f.a >= since && f.b).reduce((s, f) => s + Math.max(0, (f.b - f.a) - 2.2), 0); }

await send("Page.enable"); await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 720, deviceScaleFactor: 1.5, mobile: false });
await send("Page.navigate", { url: BASE + "/#arrive" });
await waitFor(`document.querySelector('#arriveChips .chip')`);
await sleep(1200);
await js(OVERLAY);
await js(`document.fonts.ready.then(()=>true)`);
await R(`card(${q(`<div style="font:700 15px Inter;letter-spacing:.16em;color:#ffd000;text-transform:uppercase">MN Labs · Personal AI</div>
  <h1>Site Memory</h1><h2>A private, always-on memory of every property, plus an apprentice that writes down how you do the job.</h2>
  <div class="prob"><div><b>Problem 1</b>Installers forget site details: which NVR is in which loft, the key safe, the dog in the garden.</div>
  <div><b>Problem 2</b>Apprentices and subs don't have your know-how, and none of it is written down.</div></div>
  <div style="margin-top:22px"><span class="pill">Nebius <b style="color:#9fb4ff">Token Factory</b></span><span class="pill">NVIDIA <b>Nemotron 3 Nano</b></span><span class="pill">NVIDIA <b>Nemotron 3 Super</b></span></div>`)})`);
await send("Page.startScreencast", { format: "jpeg", quality: 90, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
t0 = now(); mark("s0:start");
await sleep(Math.max(narr.s0 + 1.2, 12) * 1000);
await R(`hideCard()`);

// ---- s1 capture
mark("s1:start");
await R(`caption(${q(`<span class="k">1 · Capture</span> a note after the job`)}, ${q("The key-safe code is sealed into the encrypted vault on the device. Nemotron never sees it.")})`);
await R(`click('a.nav-item[data-view="capture"]')`);
await waitFor(`document.querySelector('#capProperty option[value="p-02"]')`);
await js(`(()=>{const s=document.getElementById('capProperty'); s.value='p-02'; s.dispatchEvent(new Event('change')); return true})()`);
await R(`moveTo('#capProperty')`);
await R(`type('#capText', ${q("Swapped the doorbell for a Ring Video Doorbell Pro 2, hardwired off the chime transformer in the under-stairs cupboard. Spare key now in the key safe on the garage wall, key safe code 4827. Smoke alarms tested, next check due 14/03/2027.")}, 55)`);
await waitFor(`document.getElementById('capPrivacy').classList.contains('found')`, 8000);
await R(`hl('#capPrivacy')`); await sleep(2200); await R(`hl('#capPrivacy', false)`);
mark("s1:call");
await R(`click('#capGo')`);
await waitFor(`document.querySelector('#capProposal .proposal')`, 90000);
mark("s1:proposal");
await sleep(600);
await R(`moveTo('#capProposal .src-tag')`); await R(`hl('#capProposal .src-tag')`);
await R(`scrollBy(260)`);
await sleep(1500); await R(`hl('#capProposal .src-tag', false)`);
await holdScene("s1", -1.5);
await R(`click('#capProposal [data-act="approve"]')`);
await waitFor(`document.querySelector('#capProposal .decided')`, 20000);
await sleep(1600);

// ---- s2 arrive
mark("s2:start");
await R(`caption(${q(`<span class="k">2 · Arrival brief</span>: every line cites its source note`)}, ${q("Nemotron 3 Nano via Nebius Token Factory · unsupported lines are dropped")})`);
await R(`click('a.nav-item[data-view="arrive"]')`);
await sleep(700);
await js(`(()=>{document.getElementById('arriveOut').innerHTML=''; return true})()`);
await R(`type('#arriveInput', ${q("I'm at 14 Oak St, what do I need to know?")}, 30)`);
mark("s2:call");
await R(`click('#arriveForm button[type=submit]')`);
await waitFor(`document.querySelector('#arriveOut .brief .bullets li')`, 90000);
mark("s2:brief");
await sleep(900);
await R(`moveTo('#arriveOut .brief .provenance')`); await R(`hl('#arriveOut .brief .provenance')`);
await R(`scrollBy(230)`); await sleep(2200); await R(`hl('#arriveOut .brief .provenance', false)`);
await R(`click('#arriveOut .brief .bullets .cite')`);
await waitFor(`!document.getElementById('sheet').classList.contains('hidden')`, 10000);
await sleep(2600);
await R(`click('#sheet [data-close]')`);
await sleep(500);
const hasReveal = await js(`!!document.querySelector('#arriveOut [data-reveal]')`);
if (hasReveal) { await R(`click('#arriveOut [data-reveal]')`); await sleep(2400); }
await holdScene("s2");

// ---- s3 route
mark("s3:start");
await R(`caption(${q(`<span class="k">3 · Nightly route briefing</span> on Nemotron 3 Super`)}, ${q("Runs itself at 20:30 · prep per stop · warranties and services falling due")})`);
await R(`click('a.nav-item[data-view="route"]')`);
await waitFor(`document.querySelector('#routeOut .stop, #routeOut .card')`);
await sleep(1000);
const f3 = { a: null, b: null }; fast.push(f3);
await R(`click('#nightlyBtn')`); f3.a = now(); mark("s3:fast-start");
await waitFor(`document.querySelector('#routeLede .src') && !document.getElementById('nightlyBtn').disabled`, 120000);
f3.b = now(); mark("s3:fast-end");
await sleep(800);
await R(`moveTo('#routeLede .src')`); await R(`hl('#routeLede')`); await sleep(1800); await R(`hl('#routeLede', false)`);
await R(`scrollBy(380, 1600)`); await sleep(1200); await R(`scrollBy(420, 1600)`);
await holdScene("s3");

// ---- s4 skills
mark("s4:start");
await R(`caption(${q(`<span class="k">4 · Apprentice Skills</span>: versioned checklists learned from your notes and edits`)}, ${q("v1 → v2 → v3 with diffs · export for an apprentice or a sub (codes never printed)")})`);
await R(`click('a.nav-item[data-view="skills"]')`);
await waitFor(`document.querySelector('[data-open-skill="sk-03"]')`);
await sleep(1400);
await R(`click('[data-open-skill="sk-03"]')`);
await waitFor(`document.querySelector('.versions li')`);
await sleep(1000);
await R(`moveTo('.versions')`); await R(`hl('.versions')`); await sleep(1500); await R(`hl('.versions', false)`);
await R(`moveTo('.diff')`); await sleep(1600);
await R(`click('.btn.hivis[data-checklist="sk-03"]')`);
await waitFor(`document.getElementById('clText')`, 10000);
await sleep(1200); await R(`scrollEl('#clText', 200, 1500)`);
await holdScene("s4", 0);
await R(`click('#sheet [data-close]')`);
await sleep(600);

// ---- s5 improve -> review gate
mark("s5:start");
await R(`caption(${q(`<span class="k">5 · Review gate</span>: Nemotron 3 Super proposes v4, you decide`)}, ${q("Approve · Edit · Later · Leave · every decision journalled")})`);
const f5 = { a: null, b: null }; fast.push(f5);
await R(`click('#improveBtn')`); f5.a = now(); mark("s5:fast-start");
await waitFor(`location.hash.startsWith('#review') && document.querySelector('#reviewOut .proposal.skill_update')`, 120000);
f5.b = now(); mark("s5:fast-end");
await sleep(1200);
await R(`moveTo('#reviewOut .proposal.skill_update .diff')`); await sleep(2200);
await R(`click('#reviewOut .proposal.skill_update [data-act="approve"]')`);
await sleep(2000);
await R(`click('#reviewSeg button[data-s="approved,edited,left"]')`);
await waitFor(`document.querySelector('#reviewOut .decided')`, 10000);
await sleep(1200);
await R(`moveTo('#reviewOut .decided')`); await R(`hl('#reviewOut .proposal')`); await sleep(1600); await R(`hl('#reviewOut .proposal', false)`);
await R(`moveTo('#journalOut')`); await sleep(1200);
await holdScene("s5");

// ---- s6 status
mark("s6:start");
await R(`caption(${q(`Live on <span class="k">Nebius Token Factory</span> · NVIDIA <span class="k">Nemotron 3 Nano 30B</span> + <span class="k">Nemotron 3 Super 120B</span>`)}, ${q("OpenAI-compatible chat completions · JSON mode · codes stripped before every call")})`);
await js(`window.scrollTo(0,0)`);
await R(`click('#statusPill')`);
await waitFor(`!document.getElementById('sheet').classList.contains('hidden')`, 10000);
await sleep(800); await R(`hl('#sheet .rows')`);
await holdScene("s6");
await R(`hl('#sheet .rows', false)`);

// ---- s7 end card
mark("s7:start");
await R(`caption('')`);
await R(`card(${q(`<div style="font:700 15px Inter;letter-spacing:.16em;color:#ffd000;text-transform:uppercase">Personal AI · Nebius × NVIDIA Global AI Hackathon</div>
  <h1>Site Memory</h1><h2>Private property memory · cited arrival briefs · codes vault · nightly route briefing · Apprentice Skills · review gate</h2>
  <div><span class="pill">github.com/<b style="color:#ffd000">MNLABSUK/site-memory</b> · MIT</span></div>
  <div style="margin-top:10px"><span class="pill">Nebius <b style="color:#9fb4ff">Token Factory</b></span><span class="pill">NVIDIA <b>Nemotron 3 Nano</b> + <b>Super</b></span><span class="pill">Built by <b style="color:#ffd000">MN Labs</b></span></div>`)})`);
await sleep((narr.s7 + 2.2) * 1000);
mark("end");
await send("Page.stopScreencast");
await sleep(500);
writeFileSync(join(OUT, "timeline.json"), JSON.stringify({ t0, frames, events, fast }, null, 1));
console.log("frames:", frames.length, "duration:", (now() - t0).toFixed(1), "s");
ws.close(); chrome.kill(); process.exit(0);
