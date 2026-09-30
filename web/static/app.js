/* Site Memory UI: vanilla JS, no build step. */
(() => {
  const $ = (id) => document.getElementById(id);
  const S = { status: null, properties: [], propById: {}, notes: {}, facts: {}, reviewStatus: "pending", skills: [], lastBrief: null };

  // ------------------------------------------------------------ helpers
  async function api(path, opts = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), opts.timeout || 75000);
    let res;
    try {
      res = await fetch(path, { headers: { "Content-Type": "application/json" }, signal: ctrl.signal, ...opts });
    } catch (e) {
      throw new Error(e.name === "AbortError"
        ? "Nemotron took too long to answer. Try again."
        : (S.status && S.status.demo ? "Can't reach the Site Memory demo server. Check your connection, then refresh."
          : "Can't reach Site Memory. Double-click start-site-memory.command, then refresh."));
    } finally { clearTimeout(timer); }
    if (!res.ok) {
      let msg = res.statusText || `Server error ${res.status}`;
      try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : (j.detail && j.detail[0] && j.detail[0].msg) || msg; } catch (_) {}
      throw new Error(msg);
    }
    const ct = res.headers.get("content-type") || "";
    return ct.includes("json") ? res.json() : res.text();
  }
  const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });
  const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  function toast(msg, err) {
    const t = $("toast"); t.textContent = msg; t.className = "toast" + (err ? " err" : "");
    clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), 2800);
  }
  function fmtDate(iso, withDay) {
    if (!iso) return "";
    const d = new Date(iso.length <= 10 ? iso + "T12:00:00" : iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString("en-GB", withDay ? { weekday: "short", day: "numeric", month: "short" } : { day: "numeric", month: "short", year: "numeric" });
  }
  function fmtTime(iso) {
    const d = new Date(iso); if (isNaN(d)) return "";
    return d.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  }
  const shortModel = (m) => (m || "").replace(/^nvidia\//, "").replace("NVIDIA-", "").replace("nemotron-3-super-120b-a12b", "Nemotron 3 Super 120B").replace("Nemotron-3-Nano-30B-A3B", "Nemotron 3 Nano 30B");
  function srcLabel(src, model) {
    if (src === "nebius") return `<span class="src">● ${esc(shortModel(model))}</span> <span>via Nebius Token Factory</span>`;
    if (src === "dry-run-fallback") return `<span class="src dry">● Local heuristics</span> <span>Token Factory unreachable</span>`;
    if (src === "seed-demo") return `<span class="src dry">● Seeded example</span>`;
    return `<span class="src dry">● Dry-run</span> <span>no NEBIUS_API_KEY set</span>`;
  }
  // An error card with a retry button, so a failed load never leaves a spinner behind.
  function failCard(el, msg, retry) {
    el.innerHTML = `<div class="card err-card"><b>That didn't work.</b><p class="muted">${esc(msg)}</p>${retry ? `<button class="btn" type="button">Try again</button>` : ""}</div>`;
    const b = el.querySelector("button"); if (b && retry) b.onclick = retry;
  }
  const where = () => (S.status && S.status.demo ? "on the server" : "on this Mac");
  const thinking = (label) => `<div class="card thinking"><span class="dots"><i></i><i></i><i></i></span><span>${esc(label)}</span></div>`;
  const ICON = {
    risk: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
    conflict: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
    access: '<path d="M15 7a4 4 0 1 1-3.9 4.9L3 20v-3l2-2v-2h2l2.2-2.2"/><circle cx="16" cy="8" r="1"/>',
    customer: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    kit: '<rect x="3" y="7" width="13" height="10" rx="2"/><path d="m16 11 5-3v8l-5-3"/>',
    due: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M9 2h6"/>',
    job: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.1-.4-.4-2.1Z"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    list: '<path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    back: '<path d="m15 18-6-6 6-6"/>',
  };
  const ico = (k) => `<svg viewBox="0 0 24 24">${ICON[k] || ICON.kit}</svg>`;
  const cite = (nid, pid) => `<button class="cite" type="button" data-note="${esc(nid)}" data-pid="${esc(pid || "")}" title="Show source note">${esc(nid)}</button>`;
  const cites = (list, pid) => (list || []).map((n) => cite(n, pid)).join("");

  function md(text) {
    const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>").replace(/`(.+?)`/g, "<code>$1</code>");
    let html = "", inList = false;
    for (const raw of (text || "").split("\n")) {
      const line = raw.trim();
      const close = () => { if (inList) { html += "</ul>"; inList = false; } };
      if (!line) { close(); continue; }
      let m;
      if ((m = line.match(/^(#{1,3})\s+(.*)$/))) { close(); const lvl = m[1].length === 1 ? "h2" : "h3"; html += `<${lvl}>${inline(m[2])}</${lvl}>`; continue; }
      if ((m = line.match(/^(?:[-*]\s*\[( |x|X)\]|[-*]|\d+[.)])\s+(.*)$/))) {
        if (!inList) { html += "<ul>"; inList = true; }
        html += `<li class="${m[1] && m[1].trim() ? "done" : ""}"><i class="box"></i><span>${inline(m[2])}</span></li>`; continue;
      }
      close(); html += `<p>${inline(line)}</p>`;
    }
    if (inList) html += "</ul>";
    return html;
  }

  // ------------------------------------------------------------ sheet
  function openSheet(html) { $("sheetBody").innerHTML = html; $("sheet").classList.remove("hidden"); $("sheetBackdrop").classList.remove("hidden"); }
  function closeSheet() { $("sheet").classList.add("hidden"); $("sheetBackdrop").classList.add("hidden"); }
  $("sheetBackdrop").addEventListener("click", closeSheet);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });

  async function ensureNotes(pid) {
    if (!pid) return;
    const b = await api(`/api/properties/${pid}`);
    b.notes.forEach((n) => (S.notes[n.id] = { date: n.recorded_at, text: n.text, pid }));
    b.facts.forEach((f) => (S.facts[f.id] = f));
  }
  async function openNote(nid, pid) {
    if (!S.notes[nid] && pid) await ensureNotes(pid);
    const n = S.notes[nid];
    if (!n) return toast("That note has been forgotten.", true);
    const facts = Object.values(S.facts).filter((f) => f.note_id === nid && f.status === "active");
    openSheet(`<h3>Source note <span class="cite">${esc(nid)}</span></h3>
      <p class="muted">Recorded ${esc(fmtDate(n.date))}</p>
      <div class="quote">${esc(n.text)}</div>
      ${facts.length ? `<p class="field-label">Facts from this note</p><div class="rows">${facts.map((f) => `<div class="row-item"><div><div class="t">${esc(f.label)}</div><div class="d">${esc(f.value)}</div></div></div>`).join("")}</div>` : ""}
      <div class="actions"><button class="btn danger" data-forget-note="${esc(nid)}" data-pid="${esc(n.pid || pid || "")}">Forget this note + its facts</button><button class="btn ghost" data-close>Close</button></div>`);
  }
  function openFact(fid) {
    const f = S.facts[fid]; if (!f) return;
    const dates = [f.installed && `Installed ${fmtDate(f.installed)}`, f.warranty_until && `Warranty until ${fmtDate(f.warranty_until)}`, f.service_due && `Service due ${fmtDate(f.service_due)}`].filter(Boolean).join(" · ");
    openSheet(`<h3>${esc(f.kind)} · ${esc(f.label)}</h3>
      <div class="quote"><b>${esc(f.value)}</b>${f.make || f.model ? `<br>${esc([f.make, f.model].filter(Boolean).join(" "))}` : ""}${f.location ? `<br><span class="muted">${esc(f.location)}</span>` : ""}${dates ? `<br><span class="muted">${esc(dates)}</span>` : ""}</div>
      <p class="muted">From ${cite(f.note_id, f.property_id)} recorded ${esc(fmtDate(f.recorded_at))}.</p>
      ${S.status && S.status.lookup && f.kind === "asset" && (f.make || f.model) ? `<div id="lookupOut"><button class="btn wide" data-lookup="${esc(fid)}">Find manual + firmware</button><p class="muted" style="font-size:13px;margin:6px 0 0">Tavily web search, summarised by Nemotron. Only "${esc([f.make, f.model].filter(Boolean).join(" "))}" is sent: never the address, notes or codes.</p></div>` : ""}
      <div class="actions">
        <button class="btn" data-redact="${esc(fid)}">${ico("lock")} Redact into vault</button>
        <button class="btn danger" data-forget="${esc(fid)}">Forget this fact</button>
        <button class="btn ghost" data-close>Close</button>
      </div>
      <p class="muted" style="font-size:13px">Forget removes it from every brief and every AI prompt. Redact keeps it, encrypted, in the vault ${where()} only.</p>`);
  }

  document.addEventListener("click", async (e) => {
    const t = e.target.closest("button, [data-note], [data-fact]");
    if (!t) return;
    try {
      if (t.dataset.note) { e.preventDefault(); return openNote(t.dataset.note, t.dataset.pid); }
      if (t.dataset.fact) return openFact(t.dataset.fact);
      if ("close" in t.dataset) return closeSheet();
      if (t.dataset.forget) { await post(`/api/facts/${t.dataset.forget}/forget`); closeSheet(); toast("Forgotten. It won't appear in briefs or prompts."); return refreshCurrent(); }
      if (t.dataset.redact) { await post(`/api/facts/${t.dataset.redact}/redact`); closeSheet(); toast("Moved into the encrypted vault."); return refreshCurrent(); }
      if (t.dataset.forgetNote) { await post(`/api/notes/${t.dataset.forgetNote}/forget`); closeSheet(); toast("Note and its facts forgotten."); return refreshCurrent(); }
      if (t.dataset.reveal) return reveal(t);
      if (t.dataset.lookup) return runLookup(t.dataset.lookup);
      if (t.dataset.checklist) return openChecklist(t.dataset.checklist, t.dataset.pid);
      if (t.dataset.brief) { location.hash = `#arrive/${t.dataset.brief}`; return; }
    } catch (err) { toast(err.message, true); }
  });

  async function runLookup(fid) {
    const box = $("lookupOut"); if (!box) return;
    box.innerHTML = thinking("Searching the web with Tavily, then asking Nemotron…");
    try {
      const r = await post(`/api/facts/${fid}/lookup`);
      if (!r.ok) { failCard(box, r.message, () => runLookup(fid)); return; }
      const link = (i) => { const x = r.results[i - 1]; return x ? `<a class="cite" href="${esc(x.url)}" target="_blank" rel="noopener">[${i}]</a>` : ""; };
      box.innerHTML = `<div class="card tight lookup"><p class="field-label">Manual + firmware · "${esc(r.query)}"</p>
        ${r.summary ? `<p>${esc(r.summary)}</p>` : ""}
        ${r.tips.length ? `<ul class="prep">${r.tips.map((t) => `<li>${esc(t.text)} ${link(t.source)}</li>`).join("")}</ul>` : ""}
        <div class="rows">${r.results.slice(0, 4).map((x) => `<div class="row-item"><div><div class="t"><a href="${esc(x.url)}" target="_blank" rel="noopener">[${x.i}] ${esc(x.title)}</a></div><div class="d">${esc(new URL(x.url).hostname)}</div></div></div>`).join("")}</div>
        <div class="provenance"><span class="src">● Tavily search</span><span>${r.tavily_ms || 0} ms</span>${r.source ? srcLabel(r.source, r.model) : ""}${r.cached ? "<span>cached</span>" : ""}</div></div>`;
      loadStatus().catch(() => {});
    } catch (err) { failCard(box, err.message, () => runLookup(fid)); }
  }

  async function reveal(btn) {
    const row = btn.closest(".vault-row"); const val = row.querySelector(".val");
    if (btn.dataset.shown) { val.textContent = "••••"; delete btn.dataset.shown; btn.textContent = "Reveal"; return; }
    const r = await post(`/api/vault/${btn.dataset.reveal}/reveal`);
    val.textContent = r.value; btn.dataset.shown = "1"; btn.textContent = "Hide";
    setTimeout(() => { if (btn.dataset.shown) { val.textContent = "••••"; delete btn.dataset.shown; btn.textContent = "Reveal"; } }, 15000);
  }

  async function openChecklist(sid, pid) {
    const txt = await api(`/api/skills/${sid}/checklist${pid ? `?property_id=${pid}` : ""}`);
    openSheet(`<h3>Checklist for a sub or apprentice</h3><pre id="clText">${esc(txt)}</pre>
      <div class="actions"><button class="btn hivis" id="clCopy">Copy</button><a class="btn" id="clDl" download="${esc(sid)}-checklist.txt">Download .txt</a><button class="btn ghost" data-close>Close</button></div>
      <p class="muted" style="font-size:13px">Codes are never printed on checklists.</p>`);
    $("clDl").href = URL.createObjectURL(new Blob([txt], { type: "text/plain" }));
    $("clCopy").onclick = async () => { try { await navigator.clipboard.writeText(txt); toast("Copied"); } catch (_) { toast("Select the text to copy", true); } };
  }

  // ------------------------------------------------------------ status
  async function loadStatus() {
    const s = await api("/api/status"); S.status = s;
    const pill = $("statusPill");
    pill.className = "status-pill " + (s.mode === "nemotron-live" ? "live" : "dry");
    pill.querySelector("span").textContent = s.mode === "nemotron-live" ? "Nemotron live" : "Dry-run";
    const b = $("reviewBadge"); b.textContent = s.stats.pending; b.classList.toggle("hidden", !s.stats.pending);
    const banner = $("demoBanner");
    if (banner) {
      banner.classList.toggle("hidden", !s.demo);
      if (s.demo) banner.innerHTML = `<b>Public demo</b> · invented MN Labs sample data · resets every ${esc(s.demo.reset_every_min)} min (next ${esc(fmtTime(s.demo.next_reset_at).split(", ").pop())}) · please don't type real addresses or codes`;
    }
    $("navFoot").innerHTML = `<b>${s.stats.properties}</b> properties · <b>${s.stats.assets}</b> assets<br><b>${s.stats.skills}</b> skills · <b>${s.stats.vault}</b> codes in vault<br>${esc(s.business)} · v${esc(s.version)}`;
    return s;
  }
  $("statusPill").addEventListener("click", () => {
    const s = S.status; if (!s) return;
    const l = s.last_llm;
    openSheet(`<h3>AI + privacy</h3>
      <div class="rows">
        <div class="row-item"><div><div class="t">Mode</div><div class="d">${s.mode === "nemotron-live" ? "Live: Nebius Token Factory" : "Dry-run: local heuristics (set NEBIUS_API_KEY in .env)"}</div></div></div>
        <div class="row-item"><div><div class="t">Door-step model</div><div class="d mono">${esc(s.model)}</div></div></div>
        <div class="row-item"><div><div class="t">Skills model</div><div class="d mono">${esc(s.skills_model)}</div></div></div>
        <div class="row-item"><div><div class="t">Nightly model</div><div class="d mono">${esc(s.nightly_model)} · ${s.nightly_at === "off" ? "automatic run off" : `runs itself at ${esc(s.nightly_at)}`}</div></div></div>
        <div class="row-item"><div><div class="t">Last live call</div><div class="d">${l ? `${esc(l.task)} · ${esc(shortModel(l.model))} · ${l.latency_ms} ms · ${l.prompt_tokens || "?"}→${l.completion_tokens || "?"} tokens · ${esc(fmtTime(l.at))}` : "None yet"}</div></div></div>
      </div>
      <div class="privacy"><svg viewBox="0 0 24 24">${ICON.lock}</svg><span>${s.demo ? `This is the <b>public demo</b>: shared MN Labs sample data that resets every ${esc(s.demo.reset_every_min)} minutes, with rate limits. Installed on your own Mac, memory lives in <b>data/</b> and never leaves it.` : `Memory lives in <b>data/</b> on this Mac.`} Codes are encrypted in a separate vault and stripped from every prompt before it leaves the machine. Nothing is saved to memory or skills without your approval.</span></div>
      <div class="actions"><button class="btn danger" id="resetDemo">Reset demo data</button><button class="btn ghost" data-close>Close</button></div>`);
    $("resetDemo").onclick = async () => {
      if (!confirm("Reset all demo data? Your captures will be lost.")) return;
      try { await post("/api/demo/reset"); closeSheet(); toast("Demo data restored"); await boot(); } catch (err) { toast(err.message, true); }
    };
  });

  // ------------------------------------------------------------ router
  function route() {
    const h = (location.hash || "#arrive").slice(1);
    const [path, qs] = h.split("?");
    const [view, arg] = path.split("/");
    const params = new URLSearchParams(qs || "");
    const v = ["arrive", "capture", "route", "skills", "review"].includes(view) ? view : "arrive";
    document.querySelectorAll(".view").forEach((el) => el.classList.toggle("on", el.id === `view-${v}`));
    document.querySelectorAll(".nav-item").forEach((el) => el.classList.toggle("on", el.dataset.view === v));
    window.scrollTo(0, 0);
    S.current = { v, arg, params };
    return render(v, arg, params);
  }
  function refreshCurrent() {
    const c = S.current || {};
    loadStatus().catch(() => {});
    if (c.v === "arrive" && S.lastBrief && S.lastBrief.property) return runBrief({ property_id: S.lastBrief.property.id });
    return render(c.v, c.arg, c.params || new URLSearchParams());
  }
  async function render(v, arg, params) {
    try {
      if (v === "arrive") return renderArrive(arg, params);
      if (v === "capture") return renderCapture(params);
      if (v === "route") return renderRoute();
      if (v === "skills") return arg ? renderSkill(arg) : renderSkills();
      if (v === "review") return renderReview(arg);
    } catch (err) { toast(err.message, true); }
  }
  window.addEventListener("hashchange", route);

  // ------------------------------------------------------------ ARRIVE
  async function loadProperties() {
    const r = await api("/api/properties"); S.properties = r.properties; S.propById = Object.fromEntries(r.properties.map((p) => [p.id, p]));
  }
  async function renderArrive(arg, params) {
    const rt = await api("/api/route");
    const jobPids = rt.route.jobs.map((j) => j.property.id);
    const chips = [
      ...rt.route.jobs.map((j) => `<button class="chip job" data-brief="${j.property.id}">${esc(j.property.address)}<small>${esc(j.job.time)}</small></button>`),
      ...S.properties.filter((p) => !jobPids.includes(p.id)).map((p) => `<button class="chip" data-brief="${p.id}">${esc(p.address)}<small>${esc(p.town)}</small></button>`),
    ];
    $("arriveChips").innerHTML = chips.join("");
    const q = params.get("q");
    if (arg) return runBrief({ property_id: arg });
    if (q) { $("arriveInput").value = q; return runBrief({ query: q }); }
    if (!S.lastBrief) $("arriveOut").innerHTML = `<div class="card empty"><b>Pull up at a job and ask.</b>Type the address, or tap one of tomorrow's stops above. Every line in the brief links back to the note it came from.</div>`;
  }
  $("arriveForm").addEventListener("submit", (e) => {
    e.preventDefault(); const q = $("arriveInput").value.trim(); if (!q) return;
    history.replaceState(null, "", `#arrive?q=${encodeURIComponent(q)}`); runBrief({ query: q });
  });
  async function runBrief(body) {
    $("arriveOut").innerHTML = thinking("Reading your notes for this address…");
    let b;
    try { b = await post("/api/arrive", body); }
    catch (err) { failCard($("arriveOut"), err.message, () => runBrief(body)); return; }
    S.lastBrief = b;
    if (!b.resolved) {
      $("arriveOut").innerHTML = `<div class="card"><b>${esc(b.message)}</b><div class="chip-row small">${(b.candidates.length ? b.candidates : S.properties).map((p) => `<button class="chip" data-brief="${p.id}">${esc(p.address)}, ${esc(p.town)}</button>`).join("")}</div><a class="btn wide" href="#capture">Capture a first note</a></div>`;
      return;
    }
    Object.entries(b.notes).forEach(([id, n]) => (S.notes[id] = { ...n, pid: b.property.id }));
    Object.values(b.sections).flat().forEach((f) => (S.facts[f.id] = f));
    if (!body.query) $("arriveInput").value = `${b.property.address}, ${b.property.town}`;
    $("arriveOut").innerHTML = briefHTML(b);
    const rf = $("briefRefresh"); if (rf) rf.onclick = () => runBrief({ property_id: b.property.id, refresh: true });
  }
  function factRows(list, flags) {
    const conflictIds = new Set(flags.filter((f) => f.type === "conflict").flatMap((f) => f.fact_ids));
    const staleIds = new Set(flags.filter((f) => f.type === "stale").flatMap((f) => f.fact_ids));
    if (!list.length) return `<p class="muted">Nothing recorded yet.</p>`;
    return `<div class="rows">${list.map((f) => {
      const dates = [f.warranty_until && `Warranty <b>${esc(fmtDate(f.warranty_until))}</b>`, f.service_due && `Service <b>${esc(fmtDate(f.service_due))}</b>`, f.installed && `Fitted ${esc(fmtDate(f.installed))}`].filter(Boolean).join(" · ");
      const makeModel = [f.make, f.model].filter(Boolean).join(" ");
      return `<div class="row-item ${conflictIds.has(f.id) ? "conflicted" : ""} ${staleIds.has(f.id) ? "staled" : ""}">
        <div><div class="t">${esc(f.label)}</div><div class="d">${esc(makeModel || f.value)}${f.location ? ` · ${esc(f.location)}` : ""}</div>${dates ? `<div class="dates">${dates}</div>` : ""}</div>
        <div class="row-actions">${cite(f.note_id, f.property_id)}<button class="icon-btn" data-fact="${esc(f.id)}" aria-label="Forget or redact">${ico("more")}</button></div>
      </div>`;
    }).join("")}</div>`;
  }
  function briefHTML(b) {
    const p = b.property, s = b.summary, pid = p.id;
    const assets = b.sections.asset;
    const nConf = b.flags.filter((f) => f.type === "conflict" || f.type === "stale").length;
    const bullets = s.bullets.map((x) => `<li class="t-${esc(x.tag)}"><span class="tag-ico">${ico(x.tag)}</span><div>${esc(x.text)} ${cites(x.cites, pid)}${x.from_rules ? `<span class="rules">rule</span>` : ""}</div></li>`).join("");
    const flags = b.flags.map((f) => `<div class="flag ${esc(f.type)}"><div><div class="kind">${esc(f.type.replace("_", " "))}</div><div>${esc(f.message)} ${cites(f.note_ids, pid)}</div></div></div>`).join("");
    const secrets = b.secrets.map((x) => `<div class="vault-row"><span class="lbl">${ico("lock")} ${esc(x.label)}</span><span class="val">••••</span><button class="btn sm" data-reveal="${esc(x.id)}">Reveal</button></div>`).join("");
    const skills = b.skills.map((k) => `<button class="skill-chip" data-checklist="${esc(k.id)}" data-pid="${esc(pid)}" title="${esc(k.why)}">${ico("list")} ${esc(k.title)} <span class="ver">v${k.version}</span></button>`).join("");
    const jobs = b.jobs.map((j) => `<div class="row-item"><div><div class="t">${esc(fmtDate(j.date, true))} · ${esc(j.time)}</div><div class="d">${esc(j.title)}</div></div><span class="jt-chip">${esc(j.job_type)}</span></div>`).join("");
    const people = [...b.sections.customer, ...b.sections.access];
    const other = [...b.sections.cable, ...b.sections.general, ...b.sections.warranty, ...b.sections.service];
    return `
      <div class="card">
        <div class="prop-head"><div><div class="addr">${esc(p.address)}</div><div class="sub">${esc(p.town)} ${esc(p.postcode)} · ${esc(p.kind || "")}</div><div class="sub">${esc(p.customer)}</div></div></div>
        <div class="stats"><span class="stat"><b>${new Set(assets.map((a) => a.key)).size}</b> assets</span>${nConf ? `<span class="stat warn"><b>${nConf}</b> to check</span>` : ""}<span class="stat vault"><b>${b.secrets.length}</b> in vault</span><span class="stat"><b>${Object.keys(b.notes).length}</b> source notes</span></div>
      </div>
      <div class="card brief">
        <h3>30-second brief</h3>
        <p class="headline">${esc(s.headline)}</p>
        <ul class="bullets">${bullets || "<li>No brief yet.</li>"}</ul>
        <div class="provenance">${srcLabel(s.source, s.model)}${s.latency_ms ? `<span>${(s.latency_ms / 1000).toFixed(1)}s</span>` : ""}${s.dropped_uncited ? `<span>${s.dropped_uncited} unsupported line${s.dropped_uncited > 1 ? "s" : ""} dropped</span>` : `<span>every line cited</span>`}${b.cached ? `<span>cached</span>` : ""}<span class="spacer"></span><button class="btn sm ghost" id="briefRefresh">Refresh</button></div>
      </div>
      ${flags ? `<div class="card"><h3>Check before you start</h3>${flags}</div>` : ""}
      ${skills || jobs ? `<div class="card"><h3>This visit</h3>${jobs}${skills ? `<div class="skill-chips">${skills}</div>` : ""}</div>` : ""}
      <div class="card"><h3>Kit on site</h3>${factRows(assets, b.flags)}</div>
      <div class="cols">
        <div class="card"><h3>Customer + access</h3>${factRows(people, b.flags)}</div>
        <div class="card"><h3>Cable routes + notes</h3>${factRows(other, b.flags)}</div>
      </div>
      <div class="card"><h3>Vault · never sent to the AI</h3>${secrets || `<p class="muted">No codes stored for this property.</p>`}</div>
      <div class="card"><h3>Source notes</h3><div class="rows">${Object.entries(b.notes).map(([id, n]) => `<div class="row-item"><div><div class="d">${esc(n.text)}</div><div class="dates">${esc(fmtDate(n.date))}</div></div><div class="row-actions">${cite(id, pid)}</div></div>`).join("")}</div></div>`;
  }

  // ------------------------------------------------------------ CAPTURE
  function renderCapture(params) {
    const sel = $("capProperty"); const cur = params.get("p") || sel.value || (S.lastBrief && S.lastBrief.property && S.lastBrief.property.id) || "";
    sel.innerHTML = `<option value="">Work it out from the note</option>` + S.properties.map((p) => `<option value="${p.id}">${esc(p.address)}, ${esc(p.town)}</option>`).join("") + `<option value="__new">New address…</option>`;
    sel.value = cur;
    $("capNew").classList.toggle("hidden", sel.value !== "__new");
    if (params.get("text")) { $("capText").value = params.get("text"); preview(); }
  }
  $("capProperty").addEventListener("change", () => $("capNew").classList.toggle("hidden", $("capProperty").value !== "__new"));
  $("capStarters").addEventListener("click", (e) => {
    const b = e.target.closest("[data-ins]"); if (!b) return;
    const ta = $("capText"); ta.value = (ta.value.trim() ? ta.value.trim() + " " : "") + b.dataset.ins; ta.focus(); preview();
  });
  let pvT;
  function preview() {
    clearTimeout(pvT);
    pvT = setTimeout(async () => {
      const text = $("capText").value; const box = $("capPrivacy");
      if (!text.trim()) { box.classList.remove("found"); box.querySelector("span").innerHTML = "Codes and passwords are split out <b>${where()}</b> before any AI call and encrypted. Nemotron never sees them."; return; }
      let r;
      try { r = await post("/api/capture/preview", { text }); } catch (_) { return; }
      box.classList.toggle("found", r.secrets.length > 0);
      box.querySelector("span").innerHTML = r.secrets.length
        ? `<b>${r.secrets.length} code${r.secrets.length > 1 ? "s" : ""} found</b> (${r.secrets.map(esc).join(", ")}): will be encrypted into the vault. Nemotron only sees <span class="mono">[vault: …]</span>.`
        : `No codes spotted. ${r.property && !$("capProperty").value ? `Looks like <b>${esc(r.property.address)}</b>.` : ""}`;
    }, 350);
  }
  $("capText").addEventListener("input", preview);
  $("capGo").addEventListener("click", async () => {
    const text = $("capText").value.trim(); if (text.length < 3) return toast("Type a note first", true);
    const sel = $("capProperty").value; const body = { text };
    if (sel && sel !== "__new") body.property_id = sel;
    if (sel === "__new") body.address = [$("capAddress").value, $("capTown").value].filter(Boolean).join(", ");
    const btn = $("capGo"); btn.disabled = true; $("capOut").innerHTML = thinking("Nemotron is sorting your note…");
    try {
      const r = await post("/api/capture", body);
      $("capText").value = ""; preview();
      $("capOut").innerHTML = `<p class="eyebrow">Waiting for your OK</p><div id="capProposal"></div>`;
      renderProposal(r.proposal, $("capProposal"));
      loadStatus();
    } catch (err) { failCard($("capOut"), err.message); toast(err.message, true); } finally { btn.disabled = false; }
  });

  // ------------------------------------------------------------ ROUTE
  async function renderRoute() {
    $("routeOut").innerHTML = thinking("Loading tomorrow…");
    try { const r = await api("/api/route"); drawRoute(r.route, r.nightly); }
    catch (err) { failCard($("routeOut"), err.message, renderRoute); }
  }
  function drawRoute(route, nightly) {
    $("routeTitle").textContent = fmtDate(route.date, true);
    $("routeLede").innerHTML = nightly
      ? `${esc(nightly.headline)}<br><span class="muted" style="font-size:13px">${srcLabel(nightly.source, nightly.model)} · generated ${esc(fmtTime(nightly.generated_at))}</span>`
      : `${route.jobs.length} job${route.jobs.length !== 1 ? "s" : ""}. Run the nightly pass for a Nemotron 3 Super prep briefing${S.status && S.status.nightly_at === "off" ? "." : ` (it also runs itself at ${esc(S.status ? S.status.nightly_at : "20:30")})`}.`;
    const nj = Object.fromEntries(((nightly && nightly.jobs) || []).map((j) => [j.job_id, j]));
    const stops = route.jobs.map((it) => {
      const j = it.job, p = it.property, pid = p.id; const n = nj[j.id];
      const prep = n && n.prep.length ? n.prep.map((x) => `<li>${esc(x.text)} ${cites(x.cites, pid)}</li>`).join("")
        : it.access.slice(0, 3).map((f) => `<li>${esc(f.value)} ${cite(f.note_id, pid)}</li>`).join("") + it.flags.slice(0, 2).map((f) => `<li>${esc(f.message)} ${cites(f.note_ids, pid)}</li>`).join("");
      const bring = n && n.bring && n.bring.length ? `<p class="muted" style="margin:10px 0 0;font-size:13px"><b style="color:var(--text)">Bring:</b> ${n.bring.map(esc).join(" · ")}</p>` : "";
      const skills = it.skills.map((k) => `<button class="skill-chip" data-checklist="${esc(k.id)}" data-pid="${esc(pid)}">${ico("list")} ${esc(k.title)} <span class="ver">v${k.version}</span></button>`).join("");
      return `<div class="stop"><div class="time">${esc(j.time)}</div><div class="card">
        <div class="card-head" style="margin:0"><div><h4>${esc(p.address)}, ${esc(p.town)}</h4><div class="muted">${esc(j.title)}</div><span class="jt">${esc(j.job_type)}</span></div><button class="btn sm" data-brief="${esc(pid)}">Brief</button></div>
        <ul class="prep">${prep}</ul>${bring}
        ${skills ? `<div class="skill-chips">${skills}</div>` : ""}
        ${it.vault_count ? `<p class="muted" style="margin:10px 0 0;font-size:13px">${ico("lock")} ${it.vault_count} code${it.vault_count > 1 ? "s" : ""} in the vault for this address</p>` : ""}
      </div></div>`;
    }).join("");
    const due = route.due.map((d) => `<div class="due-row"><div><b>${esc(d.address)}</b><div class="muted">${esc(d.message)} ${cites(d.note_ids, d.property_id)}</div></div><span class="pill ${d.booked ? "ok" : "no"}">${d.booked ? "Booked" : "Not booked"}</span></div>`).join("");
    $("routeOut").innerHTML = `<div class="timeline">${stops || `<div class="card empty"><b>No jobs tomorrow.</b>Enjoy it.</div>`}</div>
      <div class="card"><h3>Falling due in the next 30 days</h3>${due || `<p class="muted">Nothing due.</p>`}</div>`;
  }
  $("nightlyBtn").addEventListener("click", async () => {
    const btn = $("nightlyBtn"); btn.disabled = true; btn.textContent = "Thinking…";
    $("routeOut").innerHTML = thinking("Nemotron 3 Super is planning tomorrow…");
    try { const r = await post("/api/route/nightly", {}); drawRoute(r.route, r.nightly); loadStatus(); toast("Route briefing ready"); }
    catch (err) { toast(err.message, true); failCard($("routeOut"), err.message, renderRoute); }
    finally { btn.disabled = false; btn.textContent = "Run nightly pass"; }
  });

  // ------------------------------------------------------------ SKILLS
  async function renderSkills() {
    let r;
    try { r = await api("/api/skills"); } catch (err) { failCard($("skillsOut"), err.message, renderSkills); return; }
    S.skills = r.skills;
    const jts = [...new Set(r.skills.flatMap((s) => s.job_types).concat(["cctv-install", "alarm-service", "alarm-install", "nvr-commission", "heating-fault", "ev-charger"]))];
    $("skillsOut").innerHTML = `
      <div class="card">
        <h3>Teach the apprentice</h3>
        <div class="learn">
          <input id="learnTopic" placeholder="e.g. Commissioning a Dahua NVR" value="" />
          <select id="learnJT"><option value="">Any job type</option>${jts.map((j) => `<option>${esc(j)}</option>`).join("")}</select>
          <button class="btn hivis" id="learnGo">Learn from my notes</button>
        </div>
        <p class="muted" style="margin:10px 0 0;font-size:13px">Nemotron reads your site notes and your past edits, drafts a skill file, and puts it in Review. Nothing is saved until you approve.</p>
      </div>
      <div class="skill-grid">${r.skills.map((s) => `<div class="skill-card" data-open-skill="${esc(s.id)}">
        <div style="display:flex;justify-content:space-between;gap:8px;align-items:start"><h4>${esc(s.title)}</h4><span class="ver">v${s.version}</span></div>
        <p>${esc(s.summary)}</p>
        <div class="skill-meta">${s.job_types.map((j) => `<span class="jt-chip">${esc(j)}</span>`).join("")}${s.property_ids.length ? `<span class="jt-chip">${s.property_ids.length} propert${s.property_ids.length > 1 ? "ies" : "y"}</span>` : ""}</div>
        <p style="font-size:12px">${s.versions.length} version${s.versions.length > 1 ? "s" : ""} · updated ${esc(fmtDate(s.updated_at))}</p>
      </div>`).join("")}</div>`;
    document.querySelectorAll("[data-open-skill]").forEach((el) => (el.onclick = () => (location.hash = `#skills/${el.dataset.openSkill}`)));
    $("learnGo").onclick = async () => {
      const topic = $("learnTopic").value.trim(); if (topic.length < 3) return toast("What should it learn?", true);
      const btn = $("learnGo"); btn.disabled = true; btn.textContent = "Learning…";
      try { const r = await post("/api/skills/learn", { topic, job_type: $("learnJT").value || null }); toast("Skill proposed. Review it."); location.hash = `#review/${r.proposal.id}`; }
      catch (err) { toast(err.message, true); } finally { btn.disabled = false; btn.textContent = "Learn from my notes"; }
    };
  }
  async function renderSkill(sid) {
    $("skillsOut").innerHTML = thinking("Opening skill…");
    let r;
    try { r = await api(`/api/skills/${sid}`); } catch (err) { failCard($("skillsOut"), err.message, () => renderSkill(sid)); return; }
    const s = r.skill;
    const vers = [...s.versions].reverse().map((v) => `<li class="${v.version === s.version ? "cur" : ""}" data-v="${v.version}"><span class="ver">v${v.version}</span><div><div>${esc(v.change_note)}<span class="src-tag ${esc(v.source)}">${esc(v.source === "nemotron" || v.source === "nebius" ? "Nemotron" : v.source === "edited" ? "your edit" : v.source === "edited-on-disk" ? "edited file" : v.source)}</span></div><div class="muted" style="font-size:12px">${esc(fmtDate(v.at))}</div></div></li>`).join("");
    const lastDiff = r.diffs.length ? r.diffs[r.diffs.length - 1] : null;
    $("skillsOut").innerHTML = `
      <button class="back" onclick="location.hash='#skills'">${ico("back")} All skills</button>
      <div class="card">
        <div class="card-head"><div><h2>${esc(s.title)}</h2><p class="muted" style="margin:4px 0 0">${esc(s.summary)}</p></div><span class="ver" style="font-size:14px">v${s.version}</span></div>
        <div class="skill-meta">${s.job_types.map((j) => `<span class="jt-chip">${esc(j)}</span>`).join("")}${s.property_ids.map((p) => `<span class="jt-chip">${esc((S.propById[p] || {}).address || p)}</span>`).join("")}</div>
        <div class="actions" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:14px">
          <button class="btn hivis" data-checklist="${esc(s.id)}">${ico("list")} Export checklist</button>
          <button class="btn" id="improveBtn">Suggest next version</button>
        </div>
      </div>
      <div class="cols">
        <div class="card md" id="skillBody">${md(s.body_md)}</div>
        <div>
          <div class="card"><h3>Versions</h3><ul class="versions">${vers}</ul></div>
          ${lastDiff ? `<div class="card"><h3>What changed v${lastDiff.from} → v${lastDiff.to}</h3><div class="diff">${diffHTML(lastDiff.lines)}</div></div>` : ""}
          <div class="card"><h3>Attach to</h3>
            <select id="attProp"><option value="">A property…</option>${S.properties.map((p) => `<option value="${p.id}" ${s.property_ids.includes(p.id) ? "disabled" : ""}>${esc(p.address)}</option>`).join("")}</select>
            <div style="display:flex;gap:8px;margin-top:8px"><input id="attJT" placeholder="or a job type, e.g. alarm-install" /><button class="btn" id="attGo">Attach</button></div>
            <p class="path" style="margin-top:12px">Skill file: ${esc(r.file)}</p>
          </div>
        </div>
      </div>`;
    document.querySelectorAll(".md li .box").forEach((b) => (b.onclick = () => b.parentElement.classList.toggle("done")));
    document.querySelectorAll(".versions li").forEach((li) => (li.onclick = () => { const v = s.versions.find((x) => x.version === +li.dataset.v); $("skillBody").innerHTML = md(v.body_md) + (v.version !== s.version ? `<p class="muted" style="margin-top:14px">Showing v${v.version}. Current is v${s.version}.</p>` : ""); }));
    $("attGo").onclick = async () => {
      const property_id = $("attProp").value || null, job_type = $("attJT").value.trim() || null;
      if (!property_id && !job_type) return toast("Pick a property or type a job type", true);
      try { await post(`/api/skills/${s.id}/attach`, { property_id, job_type }); toast("Attached"); renderSkill(s.id); }
      catch (err) { toast(err.message, true); }
    };
    $("improveBtn").onclick = async () => {
      const btn = $("improveBtn"); btn.disabled = true; btn.textContent = "Nemotron is reading your edits…";
      try {
        const r2 = await post(`/api/skills/${s.id}/improve`);
        if (r2.no_change) { toast(r2.message); return; }
        toast(`v${s.version + 1} proposed. Review it.`); location.hash = `#review/${r2.proposal.id}`;
      }
      catch (err) { toast(err.message, true); } finally { btn.disabled = false; btn.textContent = "Suggest next version"; }
    };
  }
  const diffHTML = (lines) => lines.map((l) => `<div class="${l.op === "+" ? "add" : l.op === "-" ? "del" : "ctx"}">${esc(l.text)}</div>`).join("") || `<div class="ctx">No changes</div>`;

  // ------------------------------------------------------------ REVIEW
  document.querySelectorAll("#reviewSeg button").forEach((b) => (b.onclick = () => {
    document.querySelectorAll("#reviewSeg button").forEach((x) => x.classList.toggle("on", x === b));
    S.reviewStatus = b.dataset.s; renderReview();
  }));
  async function renderReview(focusId) {
    const out = $("reviewOut");
    let r;
    try { r = await api(`/api/review?status=${encodeURIComponent(S.reviewStatus)}`); }
    catch (err) { failCard(out, err.message, () => renderReview(focusId)); return; }
    out.innerHTML = "";
    if (!r.proposals.length) out.innerHTML = `<div class="card empty"><b>${S.reviewStatus === "pending" ? "All clear." : "Nothing here."}</b>${S.reviewStatus === "pending" ? "Captures and new skills land here for your OK." : ""}</div>`;
    r.proposals.forEach((p) => { const d = document.createElement("div"); out.appendChild(d); renderProposal(p, d); if (p.id === focusId) setTimeout(() => d.scrollIntoView({ behavior: "smooth", block: "start" }), 50); });
    const j = await api("/api/journal?limit=25").catch(() => ({ journal: [] }));
    $("journalOut").innerHTML = j.journal.map((x) => `<div class="j"><time>${esc(fmtTime(x.at))}</time><div><span class="a">${esc(x.action.replace(/_/g, " "))}</span>${esc(x.detail)}</div></div>`).join("");
  }

  const KINDS = ["asset", "access", "cable", "customer", "warranty", "service", "general"];
  function renderProposal(pr, el) {
    const done = ["approved", "edited", "left"].includes(pr.status);
    const pl = pr.final_payload || pr.payload;
    const state = { editing: false, payload: JSON.parse(JSON.stringify(pr.payload)) };
    const kindName = { memory: "Memory", skill_new: "New skill", skill_update: "Skill update" }[pr.kind];
    function body() {
      if (pr.kind === "memory") {
        const where = pr.property ? `${pr.property.address}, ${pr.property.town}` : (pl.new_property ? `New property: ${pl.new_property.address}` : "");
        const secrets = (pl.secret_labels || []).map((l) => `<div class="vault-row"><span class="lbl">${ico("lock")} ${esc(l)}</span><span class="muted" style="font-size:13px">encrypted → vault</span></div>`).join("");
        if (!state.editing) {
          return `<p class="muted" style="margin:0 0 10px">${esc(where)}</p><div class="quote" style="background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:12px;font-size:14px">${esc(pl.note_text)}</div>
            <div style="margin-top:10px">${(pl.facts || []).filter((f) => !f.drop).map((f) => `<div class="fact-view"><span class="kchip">${esc(f.kind)}</span><div><b>${esc(f.label)}</b>: ${esc(f.value)}${f.make || f.model ? ` <span class="muted">(${esc([f.make, f.model].filter(Boolean).join(" "))})</span>` : ""}${f.location ? ` <span class="muted">· ${esc(f.location)}</span>` : ""}${f.service_due ? ` <span class="muted">· service ${esc(fmtDate(f.service_due))}</span>` : ""}${f.warranty_until ? ` <span class="muted">· warranty ${esc(fmtDate(f.warranty_until))}</span>` : ""}</div></div>`).join("")}</div>${secrets}`;
        }
        const p = state.payload;
        return `<label class="field-label">Note (saved as the source for these facts)</label><textarea data-k="note_text" rows="3">${esc(p.note_text)}</textarea>
          ${p.new_property ? `<label class="field-label">New property address</label><input data-k="np_address" value="${esc(p.new_property.address)}" />` : ""}
          <label class="field-label">Facts</label>
          ${(p.facts || []).map((f, i) => `<div class="fact-edit ${f.drop ? "dropped" : ""}"><select data-i="${i}" data-f="kind">${KINDS.map((k) => `<option ${k === f.kind ? "selected" : ""}>${k}</option>`).join("")}</select><input data-i="${i}" data-f="label" value="${esc(f.label)}" /><input data-i="${i}" data-f="value" value="${esc(f.value)}" /><button class="icon-btn" data-drop="${i}" title="${f.drop ? "Keep" : "Drop"}">${ico("x")}</button></div>`).join("")}${secrets}`;
      }
      if (pr.kind === "skill_new") {
        if (!state.editing) return `<p class="muted" style="margin:0 0 10px">${esc(pl.summary || "")}${pl.learned_from && pl.learned_from.length ? ` · learned from ${cites(pl.learned_from)}` : ""}</p><div class="md card tight" style="margin:0;background:var(--bg)">${md(pl.body_md)}</div>`;
        return `<label class="field-label">Title</label><input data-k="title" value="${esc(state.payload.title)}" /><label class="field-label">Job types (comma separated)</label><input data-k="job_types" value="${esc((state.payload.job_types || []).join(", "))}" /><label class="field-label">Skill file (markdown)</label><textarea class="code-area" data-k="body_md">${esc(state.payload.body_md)}</textarea>`;
      }
      if (!state.editing) {
        const ch = (pl.changes || []).map((c) => `<li>${esc(c.change)} ${/^n-\d{4}$/.test(c.because || "") ? cite(c.because) : `<span class="muted">(${esc(c.because || "")})</span>`}</li>`).join("");
        return `<p class="muted" style="margin:0 0 10px">${esc(pl.change_note || "")}</p>${ch ? `<ul class="prep" style="margin:0 0 12px">${ch}</ul>` : ""}<div class="diff">${diffHTML(pr.diff || [])}</div>`;
      }
      return `<label class="field-label">Change note</label><input data-k="change_note" value="${esc(state.payload.change_note)}" /><label class="field-label">v${pl.from_version + 1} (markdown)</label><textarea class="code-area" data-k="body_md">${esc(state.payload.body_md)}</textarea>`;
    }
    function draw() {
      const decided = done ? `<div class="decided">${pr.status === "left" ? "Left" : pr.status === "edited" ? "<b>Approved with your edits</b>" : "<b>Approved</b>"} · ${esc(fmtTime(pr.decided_at))}</div>` : "";
      el.innerHTML = `<div class="card proposal ${esc(pr.kind)}">
        <div class="card-head" style="margin-bottom:6px"><span class="kind-tag">${esc(kindName)}${pr.status === "later" ? " · parked" : ""}</span><span class="src-tag ${esc(pr.source)}">${esc(pr.source === "nebius" ? shortModel(pr.model) : pr.source)}</span></div>
        <h4>${esc(pr.title)}</h4>
        ${pr.kind === "memory" && pr.summary ? `<p class="muted" style="margin:0 0 8px">${esc(pr.summary)}</p>` : ""}
        <div class="pbody">${body()}</div>
        ${done ? decided : `<div class="gate">
          <button class="btn hivis" data-act="${state.editing ? "edit" : "approve"}">${state.editing ? "Save edit + approve" : "Approve"}</button>
          <button class="btn" data-act="toggle">${state.editing ? "Cancel edit" : "Edit"}</button>
          <button class="btn" data-act="later">Later</button>
          <button class="btn ghost" data-act="leave">Leave</button></div>`}
      </div>`;
      el.querySelectorAll("[data-k]").forEach((inp) => (inp.oninput = () => {
        const k = inp.dataset.k;
        if (k === "job_types") state.payload.job_types = inp.value.split(",").map((x) => x.trim()).filter(Boolean);
        else if (k === "np_address") state.payload.new_property.address = inp.value;
        else state.payload[k] = inp.value;
      }));
      el.querySelectorAll("[data-f]").forEach((inp) => (inp.oninput = inp.onchange = () => { state.payload.facts[+inp.dataset.i][inp.dataset.f] = inp.value; }));
      el.querySelectorAll("[data-drop]").forEach((b) => (b.onclick = () => { const f = state.payload.facts[+b.dataset.drop]; f.drop = !f.drop; draw(); }));
      el.querySelectorAll("[data-act]").forEach((b) => (b.onclick = () => act(b.dataset.act)));
    }
    async function act(a) {
      if (a === "toggle") { state.editing = !state.editing; if (!state.editing) state.payload = JSON.parse(JSON.stringify(pr.payload)); return draw(); }
      el.querySelectorAll("button").forEach((b) => (b.disabled = true));
      try {
        const r = await post(`/api/review/${pr.id}`, { action: a, payload: a === "edit" ? state.payload : null });
        pr = r.proposal;
        const msg = { approve: "Approved and saved", edit: "Your edit saved", later: "Parked for later", leave: "Left. Nothing saved." }[a];
        toast(r.skill ? `${msg}: ${r.skill.title} v${r.skill.version}` : msg);
        await loadStatus(); await loadProperties();
        if (a === "later" || a === "leave" || S.current.v === "review") { if (S.current.v === "review") return renderReview(); }
        el.innerHTML = ""; renderProposal(pr, el);
      } catch (err) { toast(err.message, true); draw(); }
    }
    draw();
  }

  // ------------------------------------------------------------ boot
  async function boot() {
    try { await Promise.all([loadStatus(), loadProperties()]); S.lastBrief = null; await route(); }
    catch (err) { document.body.insertAdjacentHTML("afterbegin", `<div class="toast err">Can't reach the Site Memory server: ${esc(err.message)}</div>`); }
  }
  boot();
})();
