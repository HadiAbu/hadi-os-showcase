# Phase 2.5 — Journal & Reflections — Design

Status: draft for review · Date: 2026-09-08 · Satisfies `requirements.md` REQ-1…REQ-14

Read alongside `.kiro/steering/{tech,structure,design}.md`. This extends Phase 1 + Phase 2; nothing
here changes auth, the chat loop, the graph cap logic, or any existing table.

---

## 1. Architecture delta

Two new tables, one new service pair, three new route modules, two new screens. No new long-running
process. One LLM call, on an explicit user action only.

```
backend/app/
  db/migrations.py         + journal_entries, reflections
  models/
    journal.py             JournalCreate / Patch / Out
    reflections.py         ReflectionOut, ReflectionPatch, GenerateOut
  services/
    journal_store.py       CRUD + ownership checks + style-sample sync
    insights.py            compute_signals(user_id) -> SignalSet   (pure, no LLM)
                           generate(user_id) -> list[reflection rows]  (LLM or templated)
    graph.py               + journal nodes + `mentions` edges
    style.py               + a small helper the "continue" endpoint reuses
  api/routes/
    journal.py             /api/journal CRUD + /api/journal/{id}/continue
    reflections.py         /api/reflections/generate, GET, PATCH /{id}

frontend/src/
  lib/journal.ts           types + fetch helpers
  lib/reflections.ts       types + fetch helpers
  pages/Journal.tsx        /journal
  pages/Reflections.tsx    /reflections
  components/journal/      JournalEditor, MoodChips
  components/reflections/  ReflectionCard
  components/graph/        + journal colour in the legend
  pages/Dashboard.tsx      + a "latest reflection" line in the right stack
  components/NavRail.tsx   + Journal, Reflections items
  index.css                + --node-jrnl token
```

---

## 2. Data model (DDL — additive)

```sql
CREATE TABLE IF NOT EXISTS journal_entries (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  mood TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '[]',           -- JSON array of strings
  linked_objective_id TEXT,
  linked_project_id TEXT,
  learn_from_style INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
-- index: (user_id, created_at)

CREATE TABLE IF NOT EXISTS reflections (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  kind TEXT NOT NULL,                        -- momentum | drift | theme
  body TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '{}',  -- {objective_ids: [...], journal_entry_ids: [...], terms: [...]}
  status TEXT NOT NULL DEFAULT 'active',     -- active | pinned | dismissed
  created_at TEXT NOT NULL
);
-- index: (user_id, status, created_at)
```

IDs UUID v4. Timestamps microsecond ISO-8601 UTC (`utcnow_iso`). `tags` hydrated/serialised at the
service boundary exactly like `objectives.tags` / `projects.tech` (`as_str_list`).

Schema caps (enforced in Pydantic, REQ-12): `title` ≤ 200, `body` ≤ 20 000, `mood` from the enum,
`tags` ≤ 12 items, `reflections.body` ≤ 2 000.

---

## 3. `services/journal_store.py`

Mirrors `projects_store` / `objectives_store` shape.

- `list_entries(user_id, *, objective_id=None, project_id=None) -> list[dict]` — `ORDER BY created_at
  DESC, id`; `_hydrate` parses `tags`.
- `get_entry(user_id, entry_id) -> dict | None`
- `create_entry(user_id, data) -> dict` — validates `linked_objective_id` via
  `objectives_store.get_objective` and `linked_project_id` via `projects_store.project_exists`;
  raises `LinkNotOwned` (route → 422). Then `_sync_style_sample(entry)`.
- `patch_entry(user_id, entry_id, fields) -> dict | None` — same link check on any provided link
  field; `updated_at` bumped; then `_sync_style_sample`.
- `delete_entry(user_id, entry_id) -> bool` — deletes the row and its `journal:<id>` style sample.

### 3.1 Style-sample sync (REQ-5)

`_sync_style_sample(entry)`:
- `label = f"journal:{entry['id']}"`
- if `entry["learn_from_style"]` and `len(entry["body"].strip()) >= 200`:
  upsert into `style_samples` on `label` — `UPDATE ... WHERE user_id=? AND label=?`; if 0 rows,
  `INSERT`. `text = entry["body"]`.
- else: `DELETE FROM style_samples WHERE user_id=? AND label=?` (covers un-ticking the toggle or an
  edit that drops the entry under 200 chars).

`style_samples` already has `label TEXT` (Phase 1). No schema change; add
`style.upsert_labelled_sample(user_id, label, text)` and `style.delete_labelled_sample(user_id,
label)` so `journal_store` doesn't hand-write SQL against another feature's table.

---

## 4. `services/insights.py`

### 4.1 `compute_signals(user_id) -> dict` — deterministic, no LLM

```python
{
  "generated_at": <iso>,
  "momentum": [
    {"objective_id", "title", "done_30d": int, "done_60d": int, "stalled": bool}
  ],
  "drift": [
    {"objective_id", "title", "journal_entry_ids": [...], "mentions_30d": int}
  ],
  "themes": [
    {"term": "distributed systems", "count_30d": int, "count_prev_30d": int,
     "journal_entry_ids": [...]}
  ],
  "counts": {"entries_30d": int, "active_objectives": int}
}
```

- **momentum**: for each `status='active'` objective, `COUNT` of its actions with
  `completed_at >= now-30d` / `-60d`; `stalled = no action completed_at >= now-21d`.
- **drift**: for each active objective, scan the last-30-day journal entries' `body` + `title`
  (case-folded) for the objective title (whole-word) or any of its `tags`. If it appears in ≥ 2
  distinct entries AND `done_30d == 0` AND no action `created_at >= now-30d` → a drift item, with
  the matching `journal_entry_ids`.
- **themes**: concatenate the last-30-day bodies; tokenise on `\w+`, lowercase, drop a static
  stopword list (`services/_stopwords.py`, ~120 common English words) and tokens < 3 chars; count
  1-grams and adjacent 2-grams; take the top 8 by `count_30d`; for each, also count over the
  prior 30-day window. Attach up to 5 `journal_entry_ids` the term occurs in.

Everything is `client.db_execute` + Python. One helper `_days_ago_iso(n)` (copy the
`dashboard._days_ago` idiom).

### 4.2 `generate(user_id) -> list[dict]`

1. `signals = await compute_signals(user_id)`
2. If `signals["counts"]["entries_30d"] == 0 and signals["counts"]["active_objectives"] == 0`:
   return `{"reflections": [], "reason": "nothing to reflect on yet — write an entry or add an objective"}`
3. Build 3–5 reflection dicts `{kind, body, evidence_json}`:
   - **with `llm_client.available()`**: one `llm_client.one_shot(system, user)` call. `system` =
     "You write short first-person reflections in the owner's voice" + the derived style guide.
     `user` = a compact JSON of `signals` + explicit instruction: 3–5 items, each ≤ 60 words, each
     tagged with its `kind` and the ids it's about, returned as a JSON array. Parse; on parse
     failure fall through to (b).
   - **templated fallback (b)** — no key or parse failure: **one row per signal group that has
     content** (so 1–3 rows total), each summarising its group's most salient item(s), `body` from
     a format string, e.g.
     `momentum` → *"{done_30d} actions done on '{title}' in 30 days"* for the top mover, plus
     *"; '{title}' hasn't moved in 3 weeks"* appended for the first stalled objective;
     `drift` → *"'{title}' comes up in your journal but hasn't moved — {mentions_30d} mentions, no progress"* for the strongest drift item;
     `theme` → *"'{term}' is recurring — {count_30d} times this month vs {count_prev_30d} last"* for the top term.
     `evidence_json` for a group row carries every id in that group, not just the quoted one.
4. Insert each as a `reflections` row (`status='active'`), return them.

`evidence_json` always carries the real ids so the UI can link, regardless of path.

---

## 5. Graph integration (`services/graph.py`)

Additive, inside `build_graph`:

- After the conversation node query, add:
  ```sql
  SELECT id, title, body, mood, created_at FROM journal_entries
  WHERE user_id = ? AND TRIM(body) != ''
  ```
  node `journal:<id>`, `label` = `title or body[:40]`, `meta` = `{mood, created_at}`,
  `sortkey` = `created_at` (feeds the existing cap tiebreak).
- In the link pass, for each journal node with `linked_objective_id` / `linked_project_id`
  (re-query the two columns), `add(f"journal:{id}", f"objective:{oid}", "mentions")` /
  `"project:{pid}"`. Dangling-drop already handles a link to a capped-out target.
- `NODE_CAP` unchanged; journal is not in `_ALWAYS_KEEP` (objectives/projects only).

Frontend `lib/graph.ts`: add `journal` to `EntityType`, `NODE_TYPES`, `NODE_COLOR`
(`--node-jrnl`, a warm amber-violet — proposed `#e0a3c7`), `NODE_LABEL` ("Journal"), `NODE_ROUTE`
(`/journal`). `index.css` gets `--node-jrnl` + its `@theme` mapping. Legend picks it up
automatically (it maps over `NODE_TYPES`).

---

## 6. API routes

### `api/routes/journal.py` (`prefix="/journal"`)
| Method | Path | Body | Returns | Notes |
|---|---|---|---|---|
| GET | `` | — | `list[JournalOut]` | `?objective_id=` / `?project_id=` optional |
| POST | `` | `JournalCreate` | `JournalOut` 201 | `LinkNotOwned` → 422 |
| GET | `/{id}` | — | `JournalOut` | 404 if missing/other-user |
| PATCH | `/{id}` | `JournalPatch` | `JournalOut` | 404 / 422 |
| DELETE | `/{id}` | — | 204 | 404 if missing |
| POST | `/{id}/continue` | — | `{text: str}` | 503 without `LLM_API_KEY`; 404 if missing |

### `api/routes/reflections.py` (`prefix="/reflections"`)
| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/generate` | — | `{reflections: list[ReflectionOut], reason: str \| null}` |
| GET | `` | — (`?status=` optional, default active+pinned) | `list[ReflectionOut]` |
| PATCH | `/{id}` | `{status}` | `ReflectionOut` (404 if missing) |

Both registered in `main.py` after `projects` / `usage`.

`POST /journal/{id}/continue`: load entry (404 if none), return 503 if `not
llm_client.available()`, else `style.get_style_guide` + the **3 most recent entries other than this
one** (`journal_store.list_entries`, drop the current id, first 800 chars of each `body`) as
few-shot → `llm_client.one_shot(system, user)` → `{"text": ...}`. Nothing persisted.

---

## 7. Frontend

### 7.1 `/journal` (`pages/Journal.tsx` + `components/journal/`)
- Layout like Chat: a `w-64` left list on `bg-rail` (entries: title-or-first-line, `mono` date,
  mood dot, link chips), "New entry" button; right pane = `<JournalEditor>`.
- `<JournalEditor>`: shadcn `Input` (title), a large `Textarea` (body, `min-h` ~60vh), `<MoodChips>`
  (aqua-toggle chips like onboarding multi-select), a tag `Input` (comma → chips), two shadcn
  `Select`s (objective / project, `__none__` sentinel like Objectives), a "don't learn from this
  one" `label`+checkbox, and — when `llm_client` is available — a "Continue in my voice" `Button`
  that calls `/continue` and appends `text` to the body.
- **Autosave**: `useEffect` debounced 800 ms on any field change; first save `POST`s and swaps the
  route id in, subsequent saves `PATCH`. A `booted`-style ref stops an open-then-navigate creating
  an empty row (REQ-3). A small "saved · 12:04" / "saving…" line.

### 7.2 `/reflections` (`pages/Reflections.tsx` + `components/reflections/ReflectionCard.tsx`)
- Header: "Reflections" + a `Button` "Generate" (spinner while running; on `reason` show a muted
  line instead of cards).
- List grouped by `created_at` date (newest group first). `<ReflectionCard>`: a left rule coloured
  by `kind` (`momentum` aqua, `drift` warn, `theme` node-ctx violet), the `body`, a row of evidence
  chips — objective ids → `<Link to="/objectives">`, journal entry ids → `<Link to="/journal">`
  (deep-linking to a specific entry is out of scope; the list is short) — and pin / dismiss buttons
  (`PATCH`). Dismissed cards drop out of the default view.

### 7.3 Dashboard teaser
- In the right-hand stack (below `UsageCard`), a thin `SectionCard`-less line: `fetchReflections()`
  on mount, show the newest `active`/`pinned` `body` truncated + "→" linking `/reflections`; muted
  "No reflections yet →" when empty.

### 7.4 NavRail
- Add **Journal** (a book/pen SVG) and **Reflections** (a spark/lightbulb SVG) items. Order:
  Chat · Dashboard · Journal · Objectives · Projects · Context · Graph · Usage · Reflections ·
  Settings. (Reflections sits with the other read-only/analytical views near Usage.)

---

## 8. Testing

- **Unit** (`tests/unit/`):
  - `test_journal_store.py` — create/list/get/patch/delete; `tags` hydration; `LinkNotOwned` on a
    foreign objective/project id; style-sample created for a ≥200-char entry, replaced on edit,
    removed on delete and on un-ticking `learn_from_style`.
  - `test_insights.py` — `compute_signals` with seeded objectives/actions/entries: momentum 30/60d
    counts + `stalled` at the 21-day cutoff; drift fires only on ≥2 mentions + zero progress;
    theme n-gram counts + prior-window comparison + stopword filtering; empty-input `reason` path.
    `generate` with a stubbed `llm_client` (rows written, evidence ids preserved) and with
    `available()` false (templated bodies, one row per signal group).
  - `test_graph.py` — a `journal` node appears for a non-empty entry; `mentions` edge to its linked
    objective; no edge when the target is filtered/capped out.
- **Integration** (`tests/integration/`):
  - `test_journal.py` — full CRUD round-trip; `?objective_id=` filter; cross-user `404`/`422`;
    `POST /journal/{id}/continue` → `503` with `llm_client.available` monkeypatched false, and a
    stubbed 200 with it true; `401` without a token on every route.
  - `test_reflections.py` — `generate` writes rows (stubbed LLM) and returns them; no-key path
    writes templated rows; `GET` default filters out `dismissed`; `PATCH` pin/dismiss round-trip;
    second user sees none; `401` without a token.
  - `test_degradation.py` extended — journal CRUD, `/reflections/generate`, `GET/PATCH
    /reflections`, and `GET /api/graph` (with a journal node) all `200` with no `LLM_API_KEY`.
- **No network** in any test (Turso → in-memory SQLite, `llm_client` stubbed).
- **Frontend**: `npm run build` clean; Docker + Playwright — create an entry (autosave), see it as
  a graph node, generate reflections, pin one, confirm the Dashboard teaser and the
  `/reflections` grouping.

---

## 9. Deviations / notes

1. `style_samples.label` is reused as the sync key (`journal:<id>`). No schema change; two helpers
   added to `services/style.py` so the coupling is explicit and testable.
2. Theme extraction is plain n-gram counting — no embeddings, no new dependency. If themes read as
   noise in use, an embedding cluster is a contained follow-up (it only changes
   `insights._themes`).
3. `generate` is not idempotent — each call appends a new dated batch. That is intentional: the
   point is a timeline of observations. The default `GET` view and the Dashboard teaser only show
   the most recent `active`/`pinned` ones, so repeated clicks don't bury the screen.
4. No scheduled generation, no style-guide auto-refresh, no notifications — Phase 3, per
   `requirements.md` §5.
