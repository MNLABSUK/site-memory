// Injected into the page: caption bar, title cards, fake cursor, typing helpers.
(() => {
  if (window.__rec) return;
  const css = document.createElement("style");
  css.textContent = `
  #__cap{position:fixed;left:calc(50% + 116px);bottom:20px;transform:translateX(-50%);z-index:9999;max-width:980px;width:calc(100% - 232px - 60px);box-sizing:border-box;
    background:rgba(8,10,13,.92);border:1px solid rgba(255,208,0,.55);border-radius:14px;padding:12px 20px;color:#fff;
    font:600 19px/1.35 Inter,system-ui,sans-serif;box-shadow:0 12px 40px rgba(0,0,0,.5);transition:opacity .35s;text-align:center}
  #__cap small{display:block;margin-top:3px;font:500 14px/1.3 Inter,system-ui,sans-serif;color:#c9d1db}
  #__cap .k{color:#ffd000}
  #__card{position:fixed;inset:0;z-index:10000;background:radial-gradient(1200px 600px at 30% 20%,#1b2330,#0b0e12);display:flex;align-items:center;justify-content:center;
    transition:opacity .6s;color:#e9edf2;font-family:Inter,system-ui,sans-serif;text-align:center}
  #__card .in{max-width:980px;padding:0 40px}
  #__card h1{font:800 64px/1.05 Archivo,Inter,sans-serif;margin:18px 0 10px;letter-spacing:-.01em}
  #__card h2{font:600 26px/1.35 Inter,sans-serif;color:#c9d1db;margin:0 0 26px}
  #__card .pill{display:inline-block;margin:6px;padding:9px 16px;border-radius:999px;border:1px solid #2a313b;background:#161b22;font:600 17px Inter,sans-serif}
  #__card .pill b{color:#76b900}
  #__card .hv{color:#ffd000}
  #__card .prob{display:flex;gap:18px;justify-content:center;margin:26px 0 8px}
  #__card .prob div{flex:1;max-width:400px;background:#161b22;border:1px solid #2a313b;border-radius:16px;padding:18px 20px;text-align:left;font:500 19px/1.4 Inter,sans-serif}
  #__card .prob b{display:block;color:#ffd000;font:700 13px Inter;letter-spacing:.12em;text-transform:uppercase;margin-bottom:6px}
  #__cur{position:fixed;z-index:9998;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:rgba(255,208,0,.35);
    border:2px solid #ffd000;box-shadow:0 0 0 4px rgba(255,208,0,.12);transition:left .55s cubic-bezier(.4,.1,.2,1),top .55s cubic-bezier(.4,.1,.2,1),transform .15s;pointer-events:none}
  #__cur.down{transform:scale(.7)}
  .__hl{outline:3px solid #ffd000 !important;outline-offset:3px;border-radius:10px;transition:outline-color .3s}`;
  document.head.appendChild(css);
  const cap = document.createElement("div"); cap.id = "__cap"; cap.style.opacity = 0; document.body.appendChild(cap);
  const cur = document.createElement("div"); cur.id = "__cur"; cur.style.left = "640px"; cur.style.top = "400px"; document.body.appendChild(cur);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const el = (sel) => (typeof sel === "string" ? document.querySelector(sel) : sel);
  window.__rec = {
    caption(html, sub) { cap.innerHTML = html + (sub ? `<small>${sub}</small>` : ""); cap.style.opacity = html ? 1 : 0; },
    card(html) { let c = document.getElementById("__card"); if (!c) { c = document.createElement("div"); c.id = "__card"; document.body.appendChild(c); }
      c.style.opacity = 1; c.innerHTML = `<div class="in">${html}</div>`; },
    async hideCard() { const c = document.getElementById("__card"); if (!c) return; c.style.opacity = 0; await sleep(650); c.remove(); },
    async moveTo(sel) { const e = el(sel); if (!e) throw new Error("no element " + sel);
      e.scrollIntoView({ block: "center", behavior: "smooth" }); await sleep(450);
      const r = e.getBoundingClientRect(); cur.style.left = r.left + Math.min(r.width / 2, 60) + "px"; cur.style.top = r.top + r.height / 2 + "px"; await sleep(600); return e; },
    async click(sel) { const e = await this.moveTo(sel); cur.classList.add("down"); await sleep(140); cur.classList.remove("down"); e.click(); await sleep(250); return true; },
    async type(sel, text, cps = 38) { const e = await this.moveTo(sel); e.focus(); e.value = "";
      for (let i = 0; i < text.length; i++) { e.value += text[i]; e.dispatchEvent(new Event("input", { bubbles: true })); await sleep(1000 / cps); } return true; },
    async scrollBy(y, ms = 900) { const start = window.scrollY, t0 = performance.now();
      while (true) { const k = Math.min(1, (performance.now() - t0) / ms); window.scrollTo(0, start + y * (0.5 - Math.cos(Math.PI * k) / 2)); if (k >= 1) break; await sleep(16); } },
    async scrollEl(sel, y, ms = 900) { const e = el(sel); const start = e.scrollTop, t0 = performance.now();
      while (true) { const k = Math.min(1, (performance.now() - t0) / ms); e.scrollTop = start + y * (0.5 - Math.cos(Math.PI * k) / 2); if (k >= 1) break; await sleep(16); } },
    hl(sel, on = true) { const e = el(sel); if (e) e.classList.toggle("__hl", on); return !!e; },
  };
})();
