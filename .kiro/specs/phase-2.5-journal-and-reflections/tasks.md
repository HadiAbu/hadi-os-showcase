# Phase 2.5 — Journal & Reflections — Tasks

Status: ✅ shipped 2026-09-08 · built on branch `phase-2.5-journal-and-reflections`
(commits a2a33a4 J0 · ca5aeeb J1 · a06a8a4 J2 · cac0c6f R0 · 8695a99 R1 · 0280121 J3 ·
59958b3 R2 · V).

Execution order top to bottom. Each task cites the requirements it satisfies, the files it touches,
and how it is verified. Backend logic is TDD. `[ ]` todo · `[~]` in progress · `[x]` done.
Commit at the end of each milestone.

---

## J0 — Journal data layer

- [x] **0.1 Schema.** `migrations.py` + `journal_entries` (idempotent DDL, `(user_id, created_at)`
  index). `tests/integration/test_migrations.py` `EXPECTED_TABLES` extended. _Verify:_ table exists
  after startup; double-run no-op. (REQ-11)
- [x] **0.2 Store + models.** `models/journal.py` (`JournalCreate` / `JournalPatch` / `JournalOut`
  with the REQ-12 caps + the `mood` enum). `services/journal_store.py` — `list_entries`
  (`?objective_id`/`?project_id`), `get_entry`, `create_entry`, `patch_entry`, `delete_entry`;
  `tags` hydrate/serialise via `objectives_store.as_str_list`; foreign `linked_*` id →
  `LinkNotOwned`. _Verify (TDD):_ `test_journal_store.py` — CRUD, `tags` round-trip, `LinkNotOwned`
  on a foreign objective and project id, cross-user isolation. (REQ-1, 12)
- [x] **0.3 Routes.** `api/routes/journal.py` — `GET/POST /api/journal`, `GET/PATCH/DELETE
  /api/journal/{id}` (`LinkNotOwned` → 422, missing/other-user → 404, DELETE → 204). Registered in
  `main.py`. _Verify (TDD):_ `test_journal.py` — round-trip, filter param, cross-user `404`/`422`,
  `401` without a token. (REQ-2, 12)

_Commit: "journal: entries table + CRUD"._

---

## J1 — Style capture + "continue in my voice"

- [x] **1.1 Labelled style samples.** `services/style.py` + `upsert_labelled_sample(user_id, label,
  text)` / `delete_labelled_sample(user_id, label)`. `journal_store._sync_style_sample(entry)` —
  called from `create_entry` / `patch_entry` / `delete_entry`: upsert `journal:<id>` when
  `learn_from_style` and `len(body.strip()) >= 200`, else delete. _Verify (TDD):_ `test_journal_
  store.py` — sample created for a long entry, replaced on edit, removed on delete and on clearing
  `learn_from_style` or dropping below 200 chars. (REQ-5)
- [x] **1.2 Continue endpoint.** `POST /api/journal/{id}/continue` — 404 if missing; `503` if
  `not llm_client.available()`; else `style.get_style_guide` + the 3 most recent entries other than
  this one (first 800 chars each) as few-shot → `llm_client.one_shot` → `{"text": str}`, nothing
  persisted.
  _Verify (TDD):_ `test_journal.py` — `503` with `available` monkeypatched false; stubbed 200 with
  it true returning `text`. (REQ-6, 13)

_Commit: "journal: style-sample sync + continue-in-my-voice"._

---

## J2 — Journal in the knowledge graph

- [x] **2.1 Graph nodes + edges.** `services/graph.py` — add the `journal_entries` node query
  (non-empty `body`), `journal:<id>` nodes with `{mood, created_at}` meta and a `created_at`
  sortkey; `mentions` edges to `linked_objective_id` / `linked_project_id`; not in `_ALWAYS_KEEP`.
  _Verify (TDD):_ `test_graph.py` — a journal node appears; `mentions` edge to its objective; no
  dangling edge when the target is filtered out. (REQ-4)
- [x] **2.2 Frontend node type.** `lib/graph.ts` — `journal` in `EntityType` / `NODE_TYPES` /
  `NODE_COLOR` (`--node-jrnl`) / `NODE_LABEL` / `NODE_ROUTE` (`/journal`). `index.css` +
  `--node-jrnl: #e0a3c7` and its `@theme` mapping. _Verify:_ `npm run build`; `/graph` legend +
  filter show "Journal" (browser, in V). (REQ-4)

_Commit: "graph: journal nodes + mentions edges"._

---

## R0 — Reflection signals (deterministic)

- [x] **0.1 Stopwords + signals.** `services/_stopwords.py` (~120 common English words).
  `services/insights.py` `compute_signals(user_id)` → `{momentum, drift, themes, counts,
  generated_at}` per `design.md` §4.1 — all `db_execute` + Python, no LLM. _Verify (TDD):_
  `test_insights.py` — momentum 30/60d counts + `stalled` at 21d; drift only on ≥2 journal
  mentions + zero action progress; theme 1-/2-gram counts, prior-window comparison, stopword +
  short-token filtering; `counts` correct; empty-input yields empty groups. (REQ-7, 14)

_Commit: "insights: deterministic signal computation"._

---

## R1 — Reflection generation + lifecycle

- [x] **1.1 Schema + models.** `migrations.py` + `reflections` (`(user_id, status, created_at)`
  index); `EXPECTED_TABLES` extended. `models/reflections.py` — `ReflectionOut`, `ReflectionPatch`
  (`status` enum), `GenerateOut` (`{reflections, reason}`). _Verify:_ migration idempotent. (REQ-11)
- [x] **1.2 generate().** `insights.generate(user_id)` — compute signals; empty-input → `reason`,
  no rows; else 3–5 reflections: one `llm_client.one_shot` call parsed to `{kind, body,
  evidence_json}` when `available()`, templated one-per-signal-group fallback on no-key or parse
  failure; insert `reflections` rows (`active`), return them. _Verify (TDD):_ `test_insights.py` —
  stubbed LLM writes rows with evidence ids preserved; `available()` false writes templated rows;
  empty-input path returns `reason` and writes nothing. (REQ-8, 13, 14)
- [x] **1.3 Routes.** `api/routes/reflections.py` — `POST /api/reflections/generate`,
  `GET /api/reflections?status=` (default `active`+`pinned`, newest first),
  `PATCH /api/reflections/{id}` (`status`, 404 if missing). Registered in `main.py`.
  `test_degradation.py` extended — journal CRUD, `/reflections/generate`, `GET/PATCH /reflections`,
  `GET /api/graph` all `200` with no `LLM_API_KEY`. _Verify (TDD):_ `test_reflections.py` —
  generate round-trip (stubbed + no-key), `GET` excludes `dismissed`, `PATCH` lifecycle, second
  user sees none, `401` without a token. (REQ-9, 12, 13)

_Commit: "reflections: generate + lifecycle endpoints"._

---

## J3 — Journal screen

- [x] **3.1 Journal page.** `lib/journal.ts` (types + `fetchEntries`/`createEntry`/`patchEntry`/
  `deleteEntry`/`continueEntry`). `pages/Journal.tsx` at `/journal` (route in `App.tsx`) —
  Chat-style `bg-rail` list + `<JournalEditor>`. `components/journal/JournalEditor.tsx` (title
  `Input`, body `Textarea`, `<MoodChips>`, tag input, objective/project `Select`s,
  `learn_from_style` toggle, "Continue in my voice" `Button` when available). `components/journal/
  MoodChips.tsx`. Debounced 800 ms autosave (first save `POST` → swap id in, then `PATCH`);
  `booted` ref stops empty-row creation; "saved · HH:MM" line. `NavRail` gains **Journal**.
  _Verify:_ `npm run build`; browser walkthrough in V. (REQ-3)

_Commit: "journal: screen + editor"._

---

## R2 — Reflections screen + Dashboard teaser

- [x] **2.1 Reflections page.** `lib/reflections.ts` (types + `fetchReflections`/`generate`/
  `patchReflection`). `pages/Reflections.tsx` at `/reflections` (route in `App.tsx`) — "Generate"
  `Button` (spinner; `reason` → muted line), list grouped by `created_at` date newest-first.
  `components/reflections/ReflectionCard.tsx` — `kind`-coloured rule, body, evidence chips
  (`<Link>` to `/objectives` / `/journal`), pin / dismiss `PATCH`. `NavRail` gains
  **Reflections** (between Usage and Settings). _Verify:_ browser in V. (REQ-10)
- [x] **2.2 Dashboard teaser.** `pages/Dashboard.tsx` — a one-line "latest reflection →" under
  `<UsageCard>` (newest `active`/`pinned` body truncated; muted "No reflections yet →" when empty),
  linking `/reflections`. _Verify:_ browser in V. (REQ-10)

_Commit: "reflections: screen + dashboard teaser"._

---

## V — Verification

- [x] **V.1 Full test run.** `pytest -q` green, zero network. `npm run build` clean.
- [x] **V.2 Browser walkthrough** (Docker + Playwright, user `m8walk@`): ✅ `/journal` — wrote an
  entry, autosave fired ("saving…" → list updated), mood chip set; ✅ "Continue in my voice"
  appended two paragraphs from a real Groq call; ✅ `/graph` renders the entry as a pink `journal`
  node (legend + filter present); ✅ `/reflections` Generate → a `momentum` and a `theme` card
  grouped by date with evidence chips, pin works; ✅ Dashboard `ReflectionTeaser` shows the latest.
  **Fixed en route:** `GET /api/graph` 500'd once a journal node existed — `models/graph.EntityType`
  Literal was missing `"journal"` (the J2 unit test hit `build_graph` directly, not the response
  model). Added `"journal"` + a `test_graph.py` integration case that seeds an entry and asserts
  the serialised node.
- [x] **V.3 Docs.** ✅ `.kiro/steering/tech.md` (a "Journal & reflections" section — tables,
  style-sample label sync, `insights` signals + templated fallback + the LLM-voice follow-up note,
  degradation row); `structure.md` (phase-2.5 spec dir, `journal.py`/`reflections.py` routes,
  `journal_store`/`insights`/`_stopwords` services + boundaries, `components/{journal,reflections}`,
  pages list, `--node-jrnl`); `roadmap.md` status line; this file.

_Commit: "phase 2.5 — verified; docs"._

---

## Definition of done (Phase 2.5) — ✅ met 2026-09-08

- ✅ Every task `[x]` with its verification passing.
- ✅ `pytest -q` — 194 pass, zero network; `npm run build` clean.
- ✅ Journal CRUD works; a ≥ 200-char entry appears in `style_samples` and tracks edits / opt-out /
  delete; entries render as `journal` graph nodes with `mentions` edges.
- ✅ `POST /api/reflections/generate` writes a dated batch; templated bodies without a key (and,
  currently, often with one — see the follow-up note); `GET`/`PATCH` lifecycle works;
  `/reflections` groups by date; the Dashboard teaser shows the latest.
- ✅ "Continue in my voice" returns generated text with a key (real Groq call in V.2), is hidden
  without one.
- ✅ Every new endpoint requires auth, is user-scoped, and (except `/continue`) works with no
  `LLM_API_KEY`.
- ✅ Walked end-to-end in a browser against the Docker stack.

**Follow-up (Phase 3):** the reflection *voice* path relies on the model returning the requested
JSON; `gpt-oss-120b` frequently doesn't, so it falls back to templated bodies. Prompt / JSON-mode
tuning is a contained refinement — the fallback path is correct and covered by tests.
