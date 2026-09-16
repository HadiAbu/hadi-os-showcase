# Phase 2.5 — Journal & Reflections — Requirements

Status: draft for review · Date: 2026-09-08

Builds on Phase 1 (chat core, context store, objectives/actions) and Phase 2 (token design system,
knowledge graph, `messages.usage_json`). EARS keywords: **WHEN** (event), **WHILE** (state),
**IF/THEN** (conditional), unconditional **THE SYSTEM SHALL**. IDs (`REQ-N`) are cited by `tasks.md`.

Scope in one line: a place to write that the system learns your voice from, plus on-demand
reflections about your progress and recurring themes — drawn from the journal and your objectives
only, generated when you ask.

---

## 1. Journal

### REQ-1 — Journal entry store
- THE SYSTEM SHALL provide `journal_entries` (`id`, `user_id`, `title`, `body`, `mood`,
  `tags` (JSON array), `linked_objective_id`, `linked_project_id`, `created_at`, `updated_at`) with
  every row scoped by `user_id`.
- `mood` SHALL be one of a fixed small set (`good`, `flat`, `low`, `energised`, `drained`) or empty.
- `title` MAY be empty; `body` SHALL be the substantive field.
- WHEN `linked_objective_id` or `linked_project_id` is set to an id the user does not own, THE
  SYSTEM SHALL reject the write with `422`.

### REQ-2 — Journal CRUD
- THE SYSTEM SHALL provide, all requiring a valid access token and scoped to the user:
  `GET /api/journal` (newest first), `POST /api/journal`, `GET /api/journal/{id}`,
  `PATCH /api/journal/{id}`, `DELETE /api/journal/{id}`.
- `GET /api/journal` SHALL support an optional `?objective_id=` / `?project_id=` filter.
- A missing or other-user id SHALL return `404` (never confirm existence).

### REQ-3 — Journal screen
- THE SYSTEM SHALL provide `/journal` (a new nav item) on the Phase-2 token system + shadcn
  primitives: a date-ordered list of entries on the left, a title + body editor on the right with
  **debounced autosave**, a mood chip row, a tag input, and optional objective / project selectors.
- WHEN the user opens a new entry, THE editor SHALL create the row on first save, not on open (no
  empty rows from navigating away — mirrors the chat `booted` guard rationale).
- THE list SHALL show title-or-first-line, date, mood, and link chips per entry.

### REQ-4 — Journal in the knowledge graph
- THE SYSTEM SHALL add a `journal` node type to `GET /api/graph`: one node per entry with a
  non-empty `body`, `label` = title-or-first-line, `meta` = `{created_at, mood}`.
- THE SYSTEM SHALL emit a `mentions` link from `journal:<id>` to `objective:<linked_objective_id>`
  and to `project:<linked_project_id>` when those are set and the target is in the node set.
- THE new node type SHALL have its own colour token (`--node-jrnl`) and legend entry, and SHALL be
  filterable on `/graph` like the other types.

---

## 2. Writing-style capture & assist

### REQ-5 — Entries feed the style model
- WHEN a journal entry is saved with a `body` of at least 200 characters AND the entry's
  `learn_from_style` flag is not false, THE SYSTEM SHALL upsert it into `style_samples` with
  `label = "journal:<entry id>"`.
- THE upsert SHALL be keyed on that label so editing an entry replaces its sample rather than
  adding a second; deleting the entry SHALL remove the sample.
- THE journal editor SHALL expose a per-entry "don't learn from this one" toggle
  (`learn_from_style`, default true).

### REQ-6 — Continue in my voice
- THE SYSTEM SHALL provide `POST /api/journal/{id}/continue` returning 1–2 short paragraphs that
  continue the current `body`, generated via `llm_client` using the derived style guide plus the
  three most recent other entries as few-shot context.
- THE endpoint SHALL NOT persist anything; the client appends the text into the editor where the
  user can keep or discard it.
- IF `LLM_API_KEY` is unset, THE endpoint SHALL return `503` and the editor SHALL hide the affordance.

---

## 3. Reflections

### REQ-7 — Signal computation (deterministic)
- THE SYSTEM SHALL compute, from stored rows only and with no LLM call, a signal payload for the
  user covering:
  - **momentum**: per active objective, actions completed in the last 30 and 60 days; objectives
    with no action `completed_at` in the last 21 days flagged as stalled.
  - **drift**: objectives whose title or a tag appears in ≥ 2 journal entries in the last 30 days
    but which have zero action progress (no `completed_at`, no new action) in that window.
  - **themes**: the most frequent stopword-filtered 1- and 2-grams across journal `body` text in
    the last 30 days, with each term's count in the prior 30 days for comparison.
- Each signal item SHALL carry the ids it derives from (`objective_id`s, `journal_entry_id`s).

### REQ-8 — Reflection generation
- THE SYSTEM SHALL provide `POST /api/reflections/generate` which computes the REQ-7 signals, then:
  - IF `LLM_API_KEY` is set, calls `llm_client` once with the compact signal payload and the style
    guide, and stores 3–5 `reflections` rows, each written in the user's voice.
  - IF `LLM_API_KEY` is unset, stores the same rows with a plain templated `body` built from the
    signals directly (the feature degrades, it does not disappear).
- Each `reflections` row: `id`, `user_id`, `kind` (`momentum` | `drift` | `theme`), `body`,
  `evidence_json` (the source ids), `status` (`active` | `pinned` | `dismissed`), `created_at`.
- THE endpoint SHALL return the rows it created.
- WHEN generation produces a signal set that is entirely empty (no journal entries, no active
  objectives), THE SYSTEM SHALL create no rows and return an empty list with a `reason`.

### REQ-9 — Reflection lifecycle
- THE SYSTEM SHALL provide `GET /api/reflections?status=` (default: `active` + `pinned`, newest
  first) and `PATCH /api/reflections/{id}` accepting `status` ∈ {`pinned`, `dismissed`, `active`}.
- Dismissed reflections SHALL be retained (not deleted) so the history of what the system observed
  stays intact; they are simply excluded from the default view.

### REQ-10 — Reflections screen + Dashboard teaser
- THE SYSTEM SHALL provide `/reflections` (a new nav item): a "Generate" button, and the
  reflection list grouped by generation date, newest group first. Each card shows its `kind`, the
  `body`, evidence chips that link to the referenced objective / journal entry, and pin / dismiss
  controls (the same interaction shape as the context review queue).
- THE Dashboard right-hand stack SHALL show a one-line "latest reflection →" teaser linking to
  `/reflections`; WHEN there are none it SHALL show a muted "no reflections yet" with the same link.

---

## 4. Non-functional

### REQ-11 — Migrations
- `run_migrations()` SHALL create `journal_entries` and `reflections` idempotently on startup as
  additive `CREATE TABLE IF NOT EXISTS` with their indexes — no change to existing tables.

### REQ-12 — Security
- All new endpoints SHALL require a valid access token, be scoped by `user_id`, use parameterised
  SQL and Pydantic bodies, and never expose or mutate another user's rows (cross-user id →
  `404`/`422`).
- `journal_entries.body` and `reflections.body` SHALL have a length cap enforced at the schema so a
  single row cannot grow unbounded.

### REQ-13 — Degradation
- WITH no `LLM_API_KEY`: journal CRUD, the graph journal nodes, signal computation,
  `POST /api/reflections/generate` (templated bodies), and all reflection lifecycle endpoints SHALL
  work. Only `POST /api/journal/{id}/continue` SHALL return `503`.

### REQ-14 — Tests
- Unit: `journal_store` CRUD + ownership checks; `insights` signal computation (momentum windows,
  drift detection, theme n-gram counts) with seeded rows and **no LLM**; the templated-body
  fallback; graph assembly gains a `journal` node + `mentions` edge.
- Integration: journal CRUD round-trip + cross-user `404`/`422`; `POST /api/reflections/generate`
  writes rows on a stubbed LLM and on no-key (templated); `GET`/`PATCH /api/reflections` lifecycle;
  `POST /api/journal/{id}/continue` → `503` with no key; every new endpoint `401` without a token.
- A saved long entry appears in `style_samples`; editing it replaces the sample; deleting removes it.
- Tests SHALL NOT make network calls.
- Frontend: `npm run build` clean; `/journal` and `/reflections` walked in a browser against the
  Docker stack (create an entry → generate reflections → pin one → see the Dashboard teaser).

---

## 5. Out of scope (deferred to Phase 3)

- Any **scheduled** generation — a weekly reflection digest, automatic style-guide refresh — and the
  jobs framework they need.
- Reflection **notifications** (email, push).
- Reflections drawing on **context history** or **usage / cadence** data (deliberately excluded).
- Rich-text / markdown rendering in the journal editor beyond plain text with newlines.
- Full-text search over journal entries (the `/graph` search + the objective/project filter are the
  only retrieval in this phase).

---

## Open questions

1. `mood` value set — is `good / flat / low / energised / drained` the right vocabulary, or keep it
   free-text? Propose: the fixed set (cleaner for any later charting), free-text is easy to switch to.
2. "Continue in my voice" few-shot size — three recent entries. Enough signal without blowing the
   context / cost? Propose: three, and only their first ~800 chars each.
3. Theme extraction — pure Python n-gram counting vs. a tiny embedding cluster. Propose: n-gram
   counting (no new dependency, deterministic, testable); revisit if themes read as noise.
4. Should `POST /api/reflections/generate` be rate-limited beyond nginx's `api_zone` (it's one LLM
   call and some SQL)? Propose: no extra limit in 2.5; revisit with the Phase-3 scheduler.
