# New work declaration

Site Memory is a new app built for the Nebius × NVIDIA Global AI Hackathon 2026 (Personal AI track). All of the Site Memory code was written from **30 September 2026** onwards, after the **26 August 2026** start of the submission window. It reuses a small number of patterns from Michael Napier's earlier **Trade Memory** engine (`Open-Agent/trade-memory`, last modified 16–17 September 2026, built for a different hackathon), and the launcher pattern from his other Nebius entry, **Desk Gate**. Trade Memory itself was not modified.

## Reused (adapted, not copied verbatim)

| From | What | Where it lives now |
|---|---|---|
| Trade Memory `memory.py` | Storage core: thread lock, atomic JSON flush (write `.tmp`, then replace), load-or-seed / reset-to-seed, snapshot, activity log, session "last focus" | `site_memory/memory.py` (`MemoryStore` core section) |
| Trade Memory `memory.py` recall | Token-matching recall over the store, used to find what the user means | `MemoryStore.resolve_property`, `MemoryStore.search` |
| Trade Memory morning digest | "Rank what matters for the day + one-line summary" digest shape | `MemoryStore.route` + `agent.nightly` (now a route/job briefing, not a money digest) |
| Trade Memory `nebius_client.py` + `config.py` | httpx POST to Token Factory `/chat/completions`, bearer key from `.env`, JSON-fence parsing, fallback to local heuristics labelled `dry-run-fallback`, `get_settings()` | `site_memory/nebius_client.py`, `site_memory/config.py`, `site_memory/dry_run.py` |
| Trade Memory approve / leave / later gate | Human decision + decision record + history pattern | `MemoryStore.decide` (generalised to proposals, plus **edit**) |
| Trade Memory UI shell | Vanilla-JS single page with `api()` / `esc()` / `toast()` helpers, header status chip, "thinking" dots, drawer | `web/static/app.js` (drawer became a bottom sheet) |
| Desk Gate `start-desk-gate.command` | nohup + pid file + `lsof` port check launcher | `start-site-memory.command` |
| Trade Memory | MIT licence text, pytest fixture pattern (temp store) | `LICENSE`, `tests/conftest.py` |

## New since 26 August 2026 (everything else)

- **Domain and data model:** properties, source notes, cited facts (asset / access / cable / customer / warranty / service / general), jobs, flags. Trade Memory's clients / chases / invoices model is not used.
- **Secrets vault:** on-device secret detection (`redact.py`), Fernet-encrypted vault (`vault.py`), sealed secrets inside pending proposals, reveal-and-log, redact-a-fact-into-the-vault, and an outbound privacy guard that checks every request against all vault plaintexts.
- **Arrival brief:** address resolution, cited bullets, note-id validation, a lexical grounding check that drops unsupported lines, deduplication, rule-based safety net for conflicts / stale / due items, brief cache keyed on the facts.
- **Conflict and staleness engine:** same-item disagreement detection across notes, 18-month staleness, service and warranty windows.
- **Forget / redact** for facts and whole notes.
- **Nightly route briefing** with Nemotron 3 Super and a built-in daily scheduler.
- **Apprentice Skills:** learn a skill from notes and edits, propose the next version, version history with diffs, edit signals captured from your changes, markdown skill files on disk (hand edits become new versions), attach to property or job type, plain-text checklist export without codes, no-op proposal detection and diff-checked change claims.
- **Review gate** generalised to three proposal kinds (memory, new skill, skill update) with approve / **edit** / later / leave, and editable fact lists.
- **Nemotron usage:** JSON mode, thinking off, per-task models (Nano 30B at the door, Super 120B for the nightly pass and skills), UK date re-anchoring.
- **New UI:** mobile-first graphite and hi-vis design (not Desk Gate's cream/navy), bottom tab bar, bottom sheets, citation chips, diff views, PWA manifest.
- **New API routes** (`/api/arrive`, `/api/capture`, `/api/review/{id}`, `/api/route/nightly`, `/api/skills/*`, `/api/vault/*`). There is no `/api/decide` or `/api/followup`.
- **New demo data** (MN Labs Installs, invented Merseyside / Wirral addresses) and a **new test suite** (28 tests including privacy interception).

## Polish pass, 1 October 2026

- Every screen now shows an error card with **Try again** instead of a spinner when a request fails or times out (75 s UI timeout; the server gives up on a slow Nemotron call at 55 s and falls back to local heuristics first).
- **Public demo mode** (`site_memory/demo.py`, `SITE_MEMORY_DEMO=1`): per-visitor and global rate limits on Nemotron calls, scheduled reset of the shared demo data, a demo banner, `Dockerfile` + `render.yaml`.
- **Find manual + firmware** (`site_memory/lookup.py`): optional Tavily web search on an asset's make and model only, summarised into cited tips by Nemotron.
- Nightly model now defaults to Nemotron 3 Super even without `.env`; 9 new tests (36 pass, 1 live test skipped by default).

## Clearly different from Desk Gate

Site Memory has no invoices, chasing, money, inbox or overdue £ bar. It uses a different visual identity, different route names, different demo data and a different problem: property knowledge and skills, not getting paid.
