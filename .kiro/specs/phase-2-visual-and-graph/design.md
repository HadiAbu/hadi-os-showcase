# Phase 2 — Visual identity + knowledge graph + telemetry — Design

Status: draft for review · Date: 2026-09-08 · Satisfies `requirements.md` REQ-1…REQ-16

Read alongside `.kiro/steering/design.md` (palette, rules), `.kiro/steering/tech.md`, and
`.kiro/steering/structure.md`. This extends Phase 1; nothing here changes the chat loop, auth, or
the existing tables.

---

## 1. Architecture delta

No new long-running services. Three new read services + two new tables + one write path added to the
existing chat turn.

```
backend/app/
  db/migrations.py         + tool_invocations, entity_links
  services/
    graph.py               build_graph(user_id) -> {nodes, links, truncated}
    usage.py               usage(user_id, window) -> aggregates
    context_stats.py       stats(user_id) -> counts / growth / stale
    chat_agent.py          + persist a tool_invocations row per tool call (success path)
  api/routes/
    graph.py               GET /api/graph, links CRUD
    usage.py               GET /api/usage
    context.py             + GET /api/context/stats
  models/
    graph.py, usage.py     Pydantic response schemas

frontend/src/
  styles/tokens.css        the design.md palette as CSS vars (imported once)
  components/ui/*           shadcn primitives (generated, themed from tokens)
  components/graph/*        <GraphPanel> (lazy), <GraphCanvas> wrapping react-force-graph
  pages/                    rebuilt on the token system; + Graph.tsx, Usage.tsx
  lib/cost.ts              mirrors the backend rate table for display only
```

---

## 2. Data model (DDL — additive)

```sql
tool_invocations (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  conversation_id TEXT NOT NULL,
  message_id TEXT NOT NULL,            -- the assistant tool_use message row
  tool_name TEXT NOT NULL,
  arguments_json TEXT NOT NULL,        -- truncated to 4 KB
  result_json TEXT NOT NULL,          -- truncated to 4 KB
  is_error INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
-- index: (user_id, created_at), (conversation_id)

entity_links (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  from_type TEXT NOT NULL,             -- objective|action|project|context|conversation
  from_id TEXT NOT NULL,
  to_type TEXT NOT NULL,
  to_id TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'related',
  created_at TEXT NOT NULL,
  UNIQUE (user_id, from_type, from_id, to_type, to_id, kind)
);
-- index: (user_id)
```

Timestamps are microsecond ISO-8601 UTC (Phase-1 `utcnow_iso`). IDs UUID v4.

---

## 3. `tool_invocations` capture (`chat_agent.run_turn`)

Phase 1 already tracks `produced` (the assistant/tool message rows) and persists them on the
success path. Add: while iterating tool calls, collect
`{tool_name, args, result, is_error}` per call, tagged with the index of the assistant message they
belong to. In the success persist loop, after the assistant `tool_use` row is saved (its id known),
write one `tool_invocations` row per call for that message, with `arguments_json` /`result_json`
truncated to 4 KB (`value[:4096] + "…"`). Nothing is written on the error/refusal path (matches how
`produced` is discarded). No SSE change.

`services/tool_log.py` owns the insert + the "which entities did this call touch" derivation used by
the graph: for `create_*`/`update_*`/`add_action` calls, the returned `result_json` carries the
entity `id` and enough to know its type — record `(conversation_id, entity_type, entity_id)` touches
from that.

---

## 4. `services/graph.py`

`build_graph(user_id) -> {"nodes": [...], "links": [...], "truncated": bool}`

**Nodes** (one query per type, all filtered by `user_id`):
| type | source | included when | `meta` |
|---|---|---|---|
| `objective` | `objectives` | `status='active'` | `priority`, `horizon` |
| `project` | `projects` | `status IN ('active','paused')` | `status` |
| `context` | `context_entries` | `status != 'archived'` | `category`, `key` |
| `action` | `actions` | `status IN ('todo','doing')` | `objective_id`, `status` |
| `conversation` | `conversations` + a `messages` existence check | `archived=0` and has ≥1 message | `last_message_at` |

`{id: "<type>:<row id>", type, label, meta}` — the `<type>:` prefix keeps ids unique across tables.

**Links** — build a `set` of `(source, target, kind)` (order-normalised for symmetric kinds), then
emit:
- `has_action`: `objective:<oid> → action:<aid>` from `actions.objective_id`
- `for_project`: `objective:<oid> → project:<pid>` from `objectives.project_id`
- `context_of`: each `goal_context` entry → top-5-by-priority active objectives; each
  `project_context` entry → all active projects (REQ open-question 2)
- `touched`: `conversation:<cid> → <type>:<id>` from `tool_log` touch records
- explicit: every `entity_links` row → `from_type:from_id → to_type:to_id`, `kind` as stored
- drop links whose endpoints aren't both in the node set

**Cap**: if nodes > 250, keep objectives + projects + top context/action/conversation by
priority/recency to 250, set `truncated=True`, and drop dangling links.

`GET /api/graph` → `GraphOut`. Links CRUD in `api/routes/graph.py`, each validating that
`from_id`/`to_id` belong to the user (per-type ownership check) → `422` otherwise.

---

## 5. `services/usage.py`

`usage(user_id, window) -> UsageOut` — `window` ∈ `7d`/`30d`/`all` → a cutoff ISO string (or none).

- Pull `messages` rows (`role='assistant'`, `usage_json IS NOT NULL`, `created_at >= cutoff`) with
  their `model` and `conversation_id`; parse `usage_json`.
- `tokens` = sums; `by_day` = group by `date(created_at)`; `by_model` = group by `model` with
  `pct = round(model_total / total * 100)`; `by_conversation` = top 10 by total, joined to
  `conversations.title`.
- `tool_calls`: `COUNT(*)` and `GROUP BY tool_name` from `tool_invocations` in the window.
- `estimated_cost_usd`: `sum(prompt * rate.in + completion * rate.out)` over `by_model`, from
  `RATES` in `services/usage.py`:

  ```python
  RATES = {  # USD per 1M tokens (input, output); absent model => unknown
      "openai/gpt-oss-120b": (0.0, 0.0),
      "openai/gpt-oss-20b":  (0.0, 0.0),
      "qwen/qwen3.8-27b":    (0.0, 0.0),
      "gpt-4o-mini":         (0.15, 0.60),
      "claude-sonnet-5":     (3.0, 15.0),
  }
  ```
  `cost_known = every model in the window is in RATES`.

No LLM call. `GET /api/usage` → `UsageOut`.

---

## 6. `services/context_stats.py`

`stats(user_id) -> ContextStatsOut`: `by_status`, `by_category` (both `GROUP BY`), `growth` (per-day
`active` count over 30 days, derived from `created_at` ≤ day and not archived-before-day — approx:
count `active` with `created_at >= day-30`), `stale` = `active` entries with
`updated_at < now-45d`. `GET /api/context/stats`.

---

## 7. Frontend

### 7.1 Design system

- `styles/tokens.css` — `:root { color-scheme: dark; --bg: #0D1318; … }` exactly the `design.md`
  table, plus the graph node colours and radius scale. Imported once in `main.tsx`.
- `tailwind` config maps the tokens (`colors: { bg: 'var(--bg)', … }`) so utilities read them.
- shadcn/ui initialised with the dark theme pointing at the tokens; generate only the primitives
  listed in REQ-2 into `components/ui/`.
- Fonts via a `<link>` to Google Fonts in `index.html` (allowed; matches Phase-1 chat SSE approach
  of not adding runtime deps).

### 7.2 Screen rebuilds (match `design/*.dc.html`)

Order and shells:
1. `App.tsx` nav shell → the dark rail with the 8 items (adds Graph, Usage), SVG icons, the token
   surfaces. `RequireAuth` / onboarding gate unchanged.
2. Login / Register / Onboarding — restyled, same flows.
3. Chat — conversation rail, thread with tool chips + thinking pulse, "what it knows" sidebar.
4. Context — Entries / Review / Style tabs; entries grouped; review cards; **stale** affordance.
5. Objectives / Projects — restyled list + nested actions + forms.
6. Settings — restyled model chooser.
7. Dashboard — **graph-forward** layout (§7.3) + telemetry cards.

Every rebuilt screen keeps its Phase-1 data hooks and API calls; only markup/классы change.

### 7.3 Graph UI

- `components/graph/GraphPanel.tsx` — fetches `/api/graph`, renders `<GraphCanvas>` in a card, a
  legend, a "Rescan" button, a "Fullscreen" link to `/graph`, an empty state, a selected-node
  detail popover.
- `components/graph/GraphCanvas.tsx` — `React.lazy` wrapper around `react-force-graph-2d` /
  `-3d` (2D default; 3D behind a toggle and only when motion is allowed). Props: `data`,
  `onNodeClick`, `height`. Node colour by `type` from the token colours; link colour aqua at low
  opacity; `cooldownTicks` bounded; `enableNodeDrag` on.
- `pages/Graph.tsx` — full-viewport `<GraphCanvas>` + type-filter chips + a search box (highlights
  matching nodes, dims the rest).
- Under `prefers-reduced-motion`: pass a pre-computed static layout (`d3-force` run to convergence
  once, no animation) — `GraphCanvas` accepts `static` mode.

### 7.4 Usage UI

- `pages/Usage.tsx` — window selector (7d / 30d / all), headline total (mono), a `by_day` bar or
  area chart, `by_model` horizontal bars with %, `by_conversation` list, tool-call list. `dataviz`
  skill for the chart specs; single-hue (aqua) so no categorical palette needed.
- Dashboard Usage card — this-week total, sparkline, top model, `~$X` (or "cost n/a" when
  `!cost_known`).

---

## 8. Testing

Anthropic/LLM is not involved in any Phase-2 endpoint, so no stub needed for those. The chat-turn
`tool_invocations` test reuses Phase-1's `FakeChat`.

- **Unit** — `graph.build_graph` (each edge rule; dedup; node-set filtering; cap → `truncated` +
  no dangling links); `usage.usage` (window cutoffs; `by_model` pct; cost sum; `cost_known`);
  `usage.RATES` shape; `context_stats.stats` (stale cutoff at 45d; growth length 30).
- **Integration** — a stubbed tool-calling turn writes the expected `tool_invocations` rows (count,
  `tool_name`, truncation, none on refusal); `GET /api/graph` from seeded rows including one
  `entity_links` and one conversation-touch, asserting node types + that every link's endpoints are
  in `nodes`; `GET /api/usage?window=7d` figures from seeded `messages.usage_json`;
  `GET /api/context/stats` counts + stale; every new route `401` without a token and returns `[]`/
  zeroes for a second user.
- **Frontend** — `npm run build` clean; the Docker stack walked in a browser (register → onboard →
  chat → each rebuilt screen → graph panel renders + a node click → `/usage`), as Phase 1.

---

## 9. Deviations / notes

1. shadcn/ui adopted (REQ open-question 3) — `components/ui/` is generated code, kept in the repo.
2. `react-force-graph` ships 2D and 3D builds; Phase 2 ships **2D by default** (fast, always works)
   with an opt-in 3D toggle, rather than 3D-first. The "brain" aesthetic comes from the dark field +
   aqua glow, which both modes share.
3. Conversation-touch edges only exist for turns taken after this phase deploys (no backfill).
4. No scheduler, briefings, or git integration in Phase 2 — those moved to Phase 3 (`roadmap.md`).
