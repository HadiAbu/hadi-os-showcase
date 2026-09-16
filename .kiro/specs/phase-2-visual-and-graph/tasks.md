# Phase 2 — Visual identity + knowledge graph + telemetry — Tasks

Status: draft for review · Date: 2026-09-08

Execution order top to bottom. Each task cites the requirements it satisfies, the files it touches,
and how it is verified. Backend logic is TDD. `[ ]` todo · `[~]` in progress · `[x]` done.
Commit at the end of each milestone.

---

## M0 — Design system foundation

- [x] **0.1 Tokens.** Folded into `src/index.css` (Tailwind 4 is CSS-first — no `tokens.css`, no
  config file): `:root` holds the raw `design.md` palette + graph node colours + `color-scheme:dark`
  + the shadcn token contract mapped onto it (`--primary`→`--aqua`, `--card`→`--surface`, …);
  `@theme inline` exposes both sets as utilities (`bg-surface`, `text-muted-fg`, `border-hairline`,
  `bg-aqua`, `bg-node-*`, `--radius` scale, `--font-sans/-mono`). `@import 'tw-animate-css'` for
  shadcn animations. Google Fonts `<link>` (Hanken Grotesk + JetBrains Mono) in `index.html`.
  `@/*` path alias added to `tsconfig` + `vite.config` (+ `@types/node`). _Verify:_ ✅ `npm run
  build` clean; `/styleguide` route shows the swatches + primitives on the palette in a browser.
  (REQ-1)
- [x] **0.2 shadcn/ui.** `components.json` (new-york, cssVariables, `@` aliases); `src/lib/utils.ts`
  (`cn`); `npx shadcn add button input select tabs dialog card badge dropdown-menu tooltip sonner`
  → 10 primitives in `src/components/ui/`, themed from the tokens (no CSS appended — my `index.css`
  already declares the vars). Deps: `class-variance-authority`, `clsx`, `tailwind-merge`,
  `lucide-react`, `tw-animate-css`, the Radix packages. `src/pages/Styleguide.tsx` at `/styleguide`
  is the dev reference for the rest of the redesign. _Verify:_ ✅ tsc-strict clean on all ui files;
  Button (all variants) / Badge / Card / Tabs / Input render correctly dark + aqua in a browser.
  (REQ-2)

_Commit: "design system: tokens + shadcn foundation"._

---

## M1 — Shell + entry screens

- [x] **1.1 Nav shell.** `components/NavRail.tsx` — dark `--rail`, aqua logo mark, 8 items
  (adds **Graph** + **Usage**) with inline SVG icons, active = aqua text + `inset` aqua border +
  tint, account/sign-out footer. `App.tsx` `Shell` uses it; `RequireAuth` / `RequireAuthOnly` /
  onboarding gate unchanged; `/graph` + `/usage` wired to `Stub` placeholders. _Verify:_ ✅ nav
  renders on the dark shell in a browser, active state correct, all routes reachable. (REQ-2, 3)
- [x] **1.2 Login / Register / Onboarding.** `components/AuthShell.tsx` (centred, logo). Login +
  Register on shadcn `Input` / `Button` + tokens (aqua focus ring, aqua CTA). Onboarding: dark
  centred layout, aqua progress bar, shadcn `Input`/`Textarea`, multi-select as aqua toggle chips;
  all logic (`key={q.id}`, `style_samples` handling, submit) unchanged. `textarea` + `label`
  shadcn primitives added. _Verify:_ ✅ register → onboard (step / multi-select / repeatable render)
  → Chat, in a browser. (REQ-3)

_Commit: "redesign: shell + auth + onboarding"._

---

## M2 — Rebuild feature screens

- [x] **2.1 Chat.** `pages/Chat.tsx` on tokens + shadcn — dark `--rail` conversation rail (aqua
  active), thread with aqua user bubbles / `--raised` assistant bubbles, inline `ToolChip`
  (bordered, aqua pulse while running, `--danger` on error), `ThinkingPulse`, "what it knows"
  sidebar (`--surface` focus card, amber review nudge). `lib/sse.ts` stream + `booted` run-once
  guard + tool-event dedup unchanged. _Verify:_ ✅ `npm run build` clean; browser check deferred
  to M8 walkthrough. (REQ-3)
- [x] **2.2 Context.** `pages/Context.tsx` on shadcn `Tabs` (Entries / Review / Style), amber
  count pill on the Review trigger; category-grouped entries in `--surface` cards with SVG pin
  (aqua when pinned) / edit / archive; review cards on `--warn` tint with Approve / Approve
  edited / Discard; style-guide + samples editor on `Textarea`/`Input`. All API logic
  (`/context/*`, `refreshReviewCount`) unchanged. _Verify:_ ✅ build clean. (REQ-3)
- [x] **2.3 Objectives + Projects.** Both on tokens + shadcn `Select`/`Input`/`Button`/`Badge`.
  Objectives: P-badge, aqua title toggle, per-row status `Select`, nested `ActionList` with
  status selects + `--warn` "suggested" tag; add form with horizon / priority / project
  `Select` (sentinel `__none__` for "no project"). Projects: status `Select`, expandable rows
  (SVG-free ▲/▼ kept), `ProjectEditor` with `Textarea`s; repo fields marked "(Phase 3)".
  `load`/`create`/`setStatus`/PATCH logic unchanged. _Verify:_ ✅ build clean. (REQ-3)
- [x] **2.4 Settings.** `pages/Settings.tsx` — model chooser as radio rows (Server default /
  presets / Custom) on `--aqua`-bordered selection, account email, `Button variant="outline"`
  sign-out. `PRESETS` / `apply()` (archive on `''`, else POST `misc/chat_model`) unchanged.
  _Verify:_ ✅ build clean. (REQ-3)

_Commit: "redesign: chat, context, objectives, projects, settings"._

---

## M3 — tool_invocations

- [x] **3.1 Schema.** `migrations.py` + `tool_invocations` (idempotent `IF NOT EXISTS` DDL,
  `(user_id, created_at)` + `(conversation_id)` indexes). `test_migrations.py` `EXPECTED_TABLES`
  extended. _Verify:_ ✅ `test_all_tables_created` / `test_rerun_is_idempotent` pass. (REQ-15)
- [x] **3.2 Capture.** `services/tool_log.py` — `record_invocations(conv_id, user_id, message_id,
  calls)` writes one row per call with `VALUE_MAX`(4096)+`…` truncation of args/result;
  `touches_from(calls)` → `(entity_type, entity_id)` for successful
  `create_*`/`update_*`/`add_action`/`upsert_context_entry` calls (errored / read-only / no-id
  tools yield nothing). `chat_agent.run_turn` collects `{assistant_idx, tool_name, args, result,
  is_error}` per call during the loop; the success persist loop writes the rows for each saved
  assistant `tool_use` message. Refusal (`content_filter`) and exception paths `return` before
  persist → nothing written. No SSE change. _Verify (TDD):_ ✅ `test_tool_log.py` (5) +
  `test_chat.py` (4) — 1 row per call, `message_id` links a persisted tool_use row, truncation,
  `is_error` flag, zero rows on a refusal turn; full suite 124 pass. (REQ-4, REQ-16)

_Commit: "chat: record tool_invocations"._

---

## M4 — Knowledge graph (data)

- [x] **4.1 entity_links.** `migrations.py` + `entity_links` (natural-key UNIQUE, `(user_id)`
  index); `models/graph.py` (`GraphNode/Link/Out`, `LinkCreate/Out`); `services/graph_links.py`
  CRUD — `create_link` checks both endpoints via a per-type table lookup → `UnknownEntity`,
  idempotent on the natural key; `delete_link` user-scoped. `api/routes/graph.py`
  `GET/POST/DELETE /api/graph/links` (POST maps `UnknownEntity` → 422, DELETE → 204/404).
  Registered in `main.py`. _Verify (TDD):_ ✅ `test_graph.py` (integration) — CRUD round-trip,
  unknown id → 422, user-scoped (B can't see/delete/reference A's), 401 without a token. (REQ-5, 14)
- [x] **4.2 Graph assembly.** `services/graph.py` `build_graph(user_id)` — five node queries
  (objective `active`; project `active`/`paused`; context `!= archived`; action `todo`/`doing`;
  conversation `archived=0` + `EXISTS` a message); link rules `has_action`, `for_project`,
  `context_of` (goal→top-5 objectives by priority, project_context→active projects), `touched`
  (via `tool_log.touches_from` over `tool_invocations` grouped by conversation), explicit
  (`entity_links`, `related` order-normalised); dedup in a set; drop links whose endpoints
  aren't both nodes; `NODE_CAP=250` keeps objectives+projects then fills by recency, sets
  `truncated`. `GET /api/graph`. _Verify (TDD):_ ✅ `test_graph.py` (unit, 8) — type membership +
  filters; each edge rule; symmetric normalisation; dangling drop; cap → `truncated` + 250 +
  no dangling; no LLM call. Full suite 138 pass. (REQ-6, 16)

_Commit: "graph: entity_links + assembly endpoint"._

---

## M5 — Knowledge graph (UI)

- [x] **5.1 GraphCanvas.** `components/graph/GraphCanvas.tsx` (2D + d3-force) with
  `GraphCanvasLazy` (`React.lazy` + `Suspense`) so `react-force-graph` never enters the main
  bundle; `GraphCanvas3D.tsx` is a further nested `lazy` so `three` (~1 MB) loads only on the 3D
  toggle. Node colour by `type` from `lib/graph.NODE_COLOR`, aqua links, `cooldownTicks` bounded,
  drag on; custom `nodeCanvasObject` paints the dot + label and dims non-highlighted nodes.
  `prefers-reduced-motion` (`lib/useReducedMotion`) → `staticLayout()` pre-runs d3-force 300
  ticks, pins every node, `cooldownTicks=0`, and hides the 3D toggle. _Verify:_ ✅ Docker +
  browser — seeded graph renders on the void field, 2D↔3D toggles (3D chunk fetched on demand),
  labels/colours correct; `npm run build` splits `GraphCanvas` (66 kB gz) + `GraphCanvas3D`
  (344 kB gz) out of `index` (unchanged). (REQ-7, REQ-9)
- [x] **5.2 GraphPanel + Dashboard slot.** `components/graph/GraphPanel.tsx` — fetches
  `/api/graph`, card with header (Rescan, 2D/3D toggle, Fullscreen link, "showing 250 of many" on
  `truncated`), `GraphLegend` footer, error/empty/loading states, absolute selected-node detail
  popover with "Open <screen> →" via `NODE_ROUTE`. Mounted at the top of `pages/Dashboard.tsx`
  (M7 7.2 restructures the page graph-forward around it). _Verify:_ ✅ Docker + browser — panel
  renders on the Dashboard with nodes/edges + legend, Rescan refetches; the still-light Phase-1
  cards below it are untouched (M7). (REQ-7)
- [x] **5.3 Fullscreen route.** `pages/Graph.tsx` at `/graph` (wired in `App.tsx`, replaces the
  Stub) — full-viewport `flex h-screen` layout, measured canvas height, per-type filter chips
  (drop the type's nodes + dangling links client-side), search box → `highlightIds` set (lit +
  labelled, rest dimmed to 12 %), 2D/3D toggle, `GraphLegend` footer, node-detail popover. _Verify:_
  ✅ Docker + browser — filter hides Context nodes; search "ship" lights the objective and dims the
  rest, edges become visible; 3D loads. (REQ-8)

_Commit: "graph: canvas, dashboard panel, fullscreen route"._

---

## M6 — Telemetry endpoints

- [x] **6.1 Usage.** `services/usage.py` — `usage(user_id, window)` (`7d`/`30d`/`all` → cutoff),
  aggregates `messages.usage_json` into `tokens` / `by_day` / `by_model` (pct) / `by_conversation`
  (top 10, titled), `tool_calls_total` + `by_name` from `tool_invocations` in the window,
  `estimated_cost_usd` + `cost_known` from `RATES` (USD per 1M in/out; Groq models 0). `models/
  usage.py` (`UsageOut` + parts). `GET /api/usage?window=` (registered in `main.py`; bad window →
  422). _Verify (TDD):_ ✅ `test_usage.py` (8) — window cutoffs, sums, `by_day`, `by_model` pct +
  order, `by_conversation` titles, tool counts, cost sum + `cost_known` false on an unpriced
  model, empty-window zeroes, RATES shape. (REQ-10, 16)
- [x] **6.2 Context stats.** `services/context_stats.py` — `by_status` (all), `by_category`
  (non-archived), `growth` (30 daily non-archived-by-day-end counts — approximate, archives carry
  no date), `stale` = active with `updated_at` older than 45d. `models/context.ContextStatsOut`.
  `GET /api/context/stats`. _Verify (TDD):_ ✅ `test_context_stats.py` (3) — status/category
  counts, 45d stale cutoff, 30-point non-decreasing growth. (REQ-12, 16)
- [x] **6.3 Auth/degradation.** `test_telemetry.py` — `/api/usage` + `/api/context/stats` → 401
  without a token, user-scoped (B sees only its own zeroes), window validation.
  `test_degradation.py` extended: `/api/graph`, `/api/graph/links`, `/api/usage`,
  `/api/context/stats` all 200 with **no** `LLM_API_KEY`. _Verify (TDD):_ ✅ full suite 155 pass,
  zero network. (REQ-13, 14)

_Commit: "telemetry: usage + context stats endpoints"._

---

## M7 — Telemetry UI + Dashboard rebuild

- [x] **7.1 Usage screen.** `lib/usage.ts` (types, `fetchUsage`, `compactTokens`, `costLabel`).
  `components/charts/{Sparkline,BarChart}.tsx` — inline SVG / flex, single aqua hue, no chart lib.
  `pages/Usage.tsx` at `/usage` (wired in `App.tsx`, replaces the Stub) — window `Tabs`
  (7d/30d/all), headline total + `costLabel` + in/out split + tool/conversation counts,
  `TOKENS PER DAY` `BarChart`, `By model` %-bars, `Tool calls` list, `Top conversations` list;
  empty states throughout. _Verify:_ ✅ Docker + browser — real data renders, window switch
  refetches (header + chart re-label), single-day bar sized sanely. (REQ-11)
- [x] **7.2 Dashboard.** `pages/Dashboard.tsx` rebuilt on tokens, graph-forward per
  `design/Main.dc.html`: header + date · row 1 `grid-cols-[1.55fr_1fr]` — `GraphPanel height=460`
  left, `Focus now` (keeps `Markdownish`, refresh, stale badge) / `Momentum` (2×2 `--raised`
  tiles) / `<UsageCard>` right · row 2 `grid-cols-[1.3fr_1fr]` — `Objective progress` (aqua bars)
  + `Changed this week`. `components/usage/UsageCard.tsx` — week total (mono) + `Sparkline` +
  top-3 model bars + `costLabel` + tool/convo counts + "Details ↗" to `/usage`. `Stub` removed
  from `App.tsx`. _Verify:_ ✅ Docker + browser — matches the canvas, all data live (2.4k tok from
  a real turn), graph panel + legend render. (REQ-7, 11)

_Commit: "redesign: dashboard (graph-forward) + usage screen"._

---

## M8 — Verification

- [x] **8.1 Full test run.** ✅ `pytest -q` — 155 pass, zero network. `npm run build` clean
  (`GraphCanvas` 66 kB gz + `GraphCanvas3D` 344 kB gz code-split out of `index` 168 kB gz).
- [x] **8.2 Browser walkthrough** (Docker stack + Playwright, fresh user `m8walk@`):
  register → onboard (all 10 questions, every input type) → Chat; a streamed turn rendered the
  `✓ list_projects` chip and **wrote a `tool_invocations` row** (confirmed on `/usage`:
  "1 tool calls · list_projects 1"); Dashboard renders graph-forward with live data (graph edges,
  Momentum, `UsageCard` 2.5k tok); `/graph` — Context filter hides those nodes, search "phase"
  lights the objective + dims the rest and reveals its edge; 2D↔3D toggles (3D chunk on demand);
  `/usage` window switch refetches; all 8 screens on the token system.
  **Fixed en route:** cold page loads intermittently bounced to `/login` — the `AuthProvider`
  bootstrap and the 401 interceptor each fired `/auth/refresh`, and with single-use refresh
  tokens the loser 401'd and dropped the session. `lib/api.ts` now coalesces both onto one
  in-flight promise; re-verified with ~8 back-to-back hard navigations, one `/auth/refresh` each,
  no bounce. _Node-click → screen_: the popover + `NODE_ROUTE` `<Link>` wiring is identical in
  `GraphPanel` and `Graph`; the harness can't drive `react-force-graph`'s canvas hit-test with
  synthetic events, so it's verified by code rather than a click in this pass.
- [x] **8.3 Docs.** ✅ `.kiro/steering/tech.md` (design system + `react-force-graph`/`three`/
  `d3-force` code-split, single-flight refresh, a "Telemetry & knowledge graph" section covering
  `tool_invocations`/`entity_links`/`build_graph`/`RATES`/`context_stats`, degradation row);
  `structure.md` (phase-2 spec dir, `graph.py`/`usage.py` routes, five new services + their
  boundaries, `components/{ui,graph,charts,usage}`, `index.css` tokens); this file's DoD.

_Commit: "phase 2 — verified; docs"._

---

## Definition of done (Phase 2) — ✅ met 2026-09-08

- ✅ Every task `[x]` with its verification passing.
- ✅ `pytest -q` — 155 pass, zero network; `npm run build` clean.
- ✅ Every screen is on the Turso token system + shadcn; no Phase-1 light styling remains; the
  Dashboard is graph-forward per `design/Main.dc.html`.
- ✅ `GET /api/graph` returns a correct node/edge set; the Dashboard panel and `/graph` render it.
  Node-click → screen wiring verified by code (see 8.2 note).
- ✅ `GET /api/usage` and `/api/context/stats` return correct figures; `/usage` and the Dashboard
  card show them; a `tool_invocations` row is written per tool call (confirmed live).
- ✅ All Phase-2 endpoints work with no `LLM_API_KEY`.
- ✅ Walked end-to-end in a browser against the Docker stack (fresh user).
- Bonus fix: single-flight `/auth/refresh` in `lib/api.ts` — cold loads no longer race the
  session away.
