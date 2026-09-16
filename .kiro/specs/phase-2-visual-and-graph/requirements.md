# Phase 2 — Visual identity + knowledge graph + telemetry — Requirements

Status: draft for review · Date: 2026-09-08

Builds on Phase 1 (chat core). EARS keywords: **WHEN** (event), **WHILE** (state), **IF/THEN**
(conditional), unconditional **THE SYSTEM SHALL**. IDs (`REQ-N`) are cited by `tasks.md`.

---

## 1. Design system

### REQ-1 — Token layer
- THE SYSTEM SHALL define the palette from `.kiro/steering/design.md` as CSS custom properties on a
  single root stylesheet: `--bg` `--rail` `--surface` `--surface-raised` `--void` `--border`
  `--accent` `--accent-hi` `--accent-ink` `--text` `--text-muted` `--text-faint` `--warn` `--danger`,
  the five graph node colours, the radius scale, and the two font families.
- THE SYSTEM SHALL render dark-only in Phase 2 (`color-scheme: dark`; no light theme). A theme
  toggle is out of scope.
- THE SYSTEM SHALL load Hanken Grotesk + JetBrains Mono with `system-ui` / `ui-monospace` fallbacks.

### REQ-2 — Component layer
- THE SYSTEM SHALL adopt **shadcn/ui** for reusable primitives (button, input, select, tabs, dialog,
  card, badge, dropdown-menu, tooltip, sonner/toast), themed from the REQ-1 tokens.
- WHEN a screen is rebuilt, THE SYSTEM SHALL replace its hand-rolled Tailwind markup with the
  token system + shadcn primitives; no screen SHALL keep the Phase-1 light styling.
- THE information architecture (routes, nav items, screen responsibilities) SHALL be unchanged from
  Phase 1, except the nav SHALL gain **Graph** and **Usage** entries.

### REQ-3 — Redesign fidelity
- Rebuilt screens SHALL match the approved design canvas (`design/*.dc.html`) in layout, spacing,
  colour, and density, adapted to real data and real interaction.
- THE SYSTEM SHALL keep every Phase-1 behaviour: auth flow, onboarding gate + wizard, streaming
  chat with tool chips, context review queue, objectives/actions/projects CRUD, dashboard
  aggregation, the model chooser.

---

## 2. `tool_invocations` capture

### REQ-4 — Record every agent tool call
- WHEN the chat turn engine executes an agent tool, THE SYSTEM SHALL insert one `tool_invocations`
  row: `user_id`, `conversation_id`, `message_id` (the assistant `tool_use` row), `tool_name`,
  `arguments_json`, `result_json` (truncated to a cap), `is_error`, `created_at`.
- THE SYSTEM SHALL write these rows as part of the same success-path persistence as the chat
  messages (not persisted when the turn errors before completion).
- THE `tool_invocations` write SHALL NOT change the chat SSE contract or user-visible behaviour.

---

## 3. Knowledge graph — data

### REQ-5 — Explicit links
- THE SYSTEM SHALL provide `entity_links` (`id`, `user_id`, `from_type`, `from_id`, `to_type`,
  `to_id`, `kind`, `created_at`) with `*_type` ∈ {`objective`,`action`,`project`,`context`,
  `conversation`}, and CRUD scoped to the user: `GET /api/graph/links`, `POST /api/graph/links`,
  `DELETE /api/graph/links/{id}`.
- WHEN a link references an id the user does not own, THE SYSTEM SHALL reject with `422`.

### REQ-6 — Graph assembly
- THE SYSTEM SHALL provide `GET /api/graph` returning `{nodes: [...], links: [...]}` for the user:
  - **nodes**: every `active` objective, every `active`/`paused` project, every non-`archived`
    context entry, every `todo`/`doing` action, and every non-archived conversation with ≥1 message.
    Each node: `{id, type, label, meta}` where `type` is the five-value set and `meta` carries a
    small type-specific payload (priority, status, category…).
  - **links** (deduplicated, each `{source, target, kind}`):
    - `objective → action` for each action's parent (`kind: "has_action"`)
    - `objective ↔ project` for each objective's `project_id` (`kind: "for_project"`)
    - `context → objective` / `context → project` — heuristic: a `goal_context` entry links to every
      active objective, a `project_context` entry to every active project (`kind: "context_of"`)
    - `conversation → {objective|action|project|context}` for every entity a `tool_invocations` row
      in that conversation created or updated (`kind: "touched"`)
    - every `entity_links` row (`kind` = its stored `kind`)
- THE graph SHALL be computed from stored rows only — no LLM call.
- THE SYSTEM SHALL cap the result (e.g. 250 nodes) and, WHEN capped, include the highest-priority /
  most-recent nodes and set a `truncated` flag.

---

## 4. Knowledge graph — UI

### REQ-7 — Dashboard panel
- THE Dashboard SHALL render the graph as a **graph-forward panel** (tall, left column) per the
  canvas, with Focus / Momentum / Usage stacked beside it and objective-progress + changes below.
- THE panel SHALL render an interactive force-directed graph via `react-force-graph` on the `--void`
  field: aqua edges, nodes coloured by `type`, node labels for the highest-degree nodes, a legend.
- WHEN a node is clicked, THE panel SHALL show that entity's detail (title, type, quick links) and
  offer to open its screen.
- THE panel SHALL have a "Rescan" affordance that refetches `GET /api/graph`, and a control to open
  the fullscreen view.

### REQ-8 — Fullscreen route
- THE SYSTEM SHALL provide `/graph` — the same graph filling the viewport, with filter toggles per
  node type and a search box that highlights matching nodes.

### REQ-9 — Degradation & performance
- WHILE `prefers-reduced-motion` is set, THE graph SHALL render as a static 2D layout with no
  animation/physics.
- IF `GET /api/graph` returns 0 nodes, THE panel SHALL show an empty state ("nothing connected yet").
- THE 3D renderer SHALL be code-split so it does not load on screens that don't show the graph.

---

## 5. Usage telemetry

### REQ-10 — Usage aggregation
- THE SYSTEM SHALL provide `GET /api/usage?window=7d|30d|all` returning, for the user:
  - `tokens`: `{prompt, completion, total}` summed from `messages.usage_json` in the window
  - `by_day`: `[{date, total_tokens}]`
  - `by_model`: `[{model, total_tokens, pct}]`
  - `by_conversation`: top 10 `[{conversation_id, title, total_tokens}]`
  - `tool_calls`: total and `[{tool_name, count}]` from `tool_invocations`
  - `estimated_cost_usd`: from a per-model rate table in code (Groq models = 0); `0` when every
    model in the window has no rate entry, with a `cost_known` flag
- THE figures SHALL come from stored rows only — no LLM call.

### REQ-11 — Usage screen + panel
- THE SYSTEM SHALL provide `/usage` — window selector, a headline total, a `by_day` sparkline/bar,
  the `by_model` and `by_conversation` breakdowns, and the tool-call list.
- THE Dashboard SHALL show a compact Usage card: this-week total tokens, a sparkline, top model,
  estimated cost.
- Charts SHALL follow the `dataviz` skill for form and colour.

---

## 6. Context stats

### REQ-12 — Context stats endpoint
- THE SYSTEM SHALL provide `GET /api/context/stats` returning: counts by `status`
  (`active`/`proposed`/`archived`), counts by `category`, `growth` `[{date, active_count}]` over the
  last 30 days (from `created_at`/`updated_at`), and `stale` — `active` entries whose `updated_at` is
  older than 45 days, `[{id, category, key, updated_at}]`.
- THE Context screen SHALL surface the `proposed` count (as today) and a small "N stale entries"
  affordance linking to a filtered view.

---

## 7. Non-functional

### REQ-13 — Degradation unchanged
- WITH no `LLM_API_KEY`, all Phase-2 endpoints (`/api/graph`, `/api/usage`, `/api/context/stats`,
  `entity_links` CRUD) SHALL work — none call the LLM. Only the Phase-1 AI endpoints stay `503`.

### REQ-14 — Security
- All new endpoints SHALL require a valid access token, be scoped by `user_id`, use parameterised
  SQL and Pydantic bodies, and never expose another user's rows (cross-user id → `404`/`422`).
- `tool_invocations.arguments_json` / `result_json` SHALL be truncated on write so a large tool
  payload cannot bloat the row unboundedly.

### REQ-15 — Migrations
- `run_migrations()` SHALL create `tool_invocations` and `entity_links` idempotently on startup, as
  additive `CREATE TABLE IF NOT EXISTS` — no change to existing tables.

### REQ-16 — Tests
- Unit: graph assembly (node/edge rules, dedup, cap+truncated), usage aggregation math (windows,
  by_model pct, cost table), context stats (stale cutoff), the cost rate table.
- Integration: `tool_invocations` written on a stubbed tool-calling turn; `GET /api/graph` shape
  from seeded rows incl. one `entity_links` and one conversation-touch edge; `GET /api/usage` and
  `/api/context/stats` figures; all four new endpoints `401` without a token and user-scoped.
- Tests SHALL NOT make network calls.
- Frontend: `npm run build` clean; the rebuilt screens walked in a browser against the Docker stack
  (as in Phase 1's verification).

---

## Open questions

1. Conversation-touch edges depend on `tool_invocations`, which only starts recording in Phase 2 —
   older conversations will have none. Acceptable (the graph fills in as the system is used)? Propose: yes.
2. Context heuristic edges (`goal_context` → *all* active objectives) could be noisy with many
   objectives. Cap at the top N by priority? Propose: link to top 5 by priority.
3. shadcn/ui pulls in Radix + a few deps and a `components/ui/` tree — acceptable footprint, or
   prefer to keep hand-rolling against the tokens? Propose: adopt shadcn (accessibility + speed).
4. `/graph` and `/usage` as top-level routes vs. tabs on the Dashboard? Propose: top-level routes,
   with compact panels mirrored on the Dashboard.
