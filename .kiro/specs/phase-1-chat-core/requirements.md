# Phase 1 — Chat core — Requirements

Status: draft for review · Date: 2026-09-07

Acceptance criteria use EARS keywords: **WHEN** (event), **WHILE** (state), **IF/THEN**
(conditional), and unconditional **THE SYSTEM SHALL**. Each requirement has an ID (`REQ-N`) that
tasks in `tasks.md` cite.

---

## 1. Accounts & authentication

### REQ-1 — Registration
- THE SYSTEM SHALL provide `POST /api/auth/register` accepting an email and password.
- WHEN a registration password is shorter than 8 characters, longer than 72, missing an uppercase
  letter, or missing a digit, THE SYSTEM SHALL reject the request with `422` and not create a user.
- WHEN the email is already registered, THE SYSTEM SHALL respond `409` and not create a user.
- WHEN registration succeeds, THE SYSTEM SHALL store the password only as a bcrypt hash
  (`gensalt(rounds=12)`) and SHALL NOT return the hash.

### REQ-2 — Login & lockout
- WHEN valid credentials are supplied to `POST /api/auth/login`, THE SYSTEM SHALL return a 15-minute
  HS256 access token (`type: "access"`) and set a rotating refresh token in an HttpOnly,
  `SameSite=Strict` cookie, storing only its SHA-256 hash.
- WHEN a login fails, THE SYSTEM SHALL increment `users.failed_attempts`.
- WHEN `failed_attempts` reaches 5, THE SYSTEM SHALL set `locked_until` to 15 minutes ahead and,
  WHILE `locked_until` is in the future, SHALL reject all logins for that account with `423`.
- WHEN a login succeeds, THE SYSTEM SHALL reset `failed_attempts` to 0 and clear `locked_until`.

### REQ-3 — Refresh & logout
- WHEN `POST /api/auth/refresh` is called with a valid, unexpired, unrevoked refresh cookie, THE
  SYSTEM SHALL issue a new access token, rotate the refresh token (revoke the old, set a new cookie),
  and delete that user's expired/revoked refresh rows.
- IF the refresh token is missing, expired, revoked, or unmatched, THEN THE SYSTEM SHALL respond
  `401` and clear the cookie.
- WHEN `POST /api/auth/logout` is called, THE SYSTEM SHALL revoke the current refresh token and clear
  the cookie.

### REQ-4 — Protected routes
- WHILE a request carries no valid access token, THE SYSTEM SHALL respond `401` to every route except
  `auth/*` and health.
- THE SYSTEM SHALL derive the acting user identity only from the verified access token, never from
  request body or query parameters.

---

## 2. Onboarding

### REQ-5 — Onboarding gate
- WHILE the authenticated user has no `onboarding_state.completed_at`, THE SYSTEM SHALL report
  onboarding as incomplete via `GET /api/onboarding/state`, and the frontend SHALL route the user to
  the onboarding wizard for any app route.
- WHEN onboarding is already complete and the user opens `/onboarding`, THE SYSTEM SHALL allow it to
  be re-run without wiping existing context (answers append; entries upsert by `(category, key)`).

### REQ-6 — Onboarding questions
- THE SYSTEM SHALL serve a fixed question bank from `GET /api/onboarding/questions`, defined in code
  (not the database), covering: identity basics, working style, writing samples, current objectives,
  current projects, and one free-text "what are you trying to achieve".
- Each question SHALL declare its `id`, `type` (`text` | `long_text` | `single_select` |
  `multi_select` | `repeatable`), prompt, and options where applicable.

### REQ-7 — Onboarding submission
- WHEN `POST /api/onboarding/submit` receives answers, THE SYSTEM SHALL, in one logical operation:
  1. store every raw answer in `onboarding_responses`;
  2. create `context_entries` (`source='onboarding'`, `status='active'`) from the structured answers,
     upserting by `(user_id, category, key)`;
  3. create `objectives` and `projects` rows from the respective repeatable answers;
  4. store pasted writing samples in `style_samples`;
  5. set `onboarding_state.completed_at`.
- IF `LLM_API_KEY` is set, THEN THE SYSTEM SHALL additionally run one LLM extraction pass
  over the free-text answer plus writing samples to (a) create `proposed` `context_entries` for
  inferred facts and (b) write an initial `style_guide.guide_md`.
- IF `LLM_API_KEY` is not set, THEN THE SYSTEM SHALL complete onboarding without the extraction
  pass and SHALL leave `style_guide.guide_md` empty.
- IF the extraction pass errors, THEN THE SYSTEM SHALL still complete onboarding (structured results
  persisted) and record that enrichment was skipped.

---

## 3. Context store & assembly

### REQ-8 — Context entries CRUD
- THE SYSTEM SHALL provide list/create/update/archive for `context_entries` scoped to the
  authenticated user, with `category` ∈ {`identity`, `preference`, `goal_context`,
  `project_context`, `working_style`, `misc`} and `status` ∈ {`active`, `proposed`, `archived`}.
- WHEN an entry is created via the UI or the onboarding structured path, THE SYSTEM SHALL set
  `status='active'`.
- WHEN an entry is created by an agent tool, THE SYSTEM SHALL set `status='proposed'`.
- WHEN a create targets an existing `(user_id, category, key)`, THE SYSTEM SHALL update that row and
  bump `updated_at` rather than insert a duplicate.

### REQ-9 — Review queue
- THE SYSTEM SHALL expose the set of `proposed` entries via `GET /api/context/review`.
- WHEN the user approves a proposed entry, THE SYSTEM SHALL set `status='active'`.
- WHEN the user edits-then-approves, THE SYSTEM SHALL persist the edited `value` and set
  `status='active'`.
- WHEN the user discards a proposed entry, THE SYSTEM SHALL set `status='archived'`.

### REQ-10 — Writing-style guide
- THE SYSTEM SHALL provide `GET`/`PUT /api/context/style-guide` for `style_guide.guide_md` and
  list/add/delete for `style_samples`.
- WHEN `guide_md` is saved, THE SYSTEM SHALL bump `style_guide.updated_at`.

### REQ-11 — System-prompt assembly
- WHEN a chat turn starts, THE SYSTEM SHALL build the `system` field as exactly two blocks:
  a **stable block** — base instructions, then all `active` `context_entries` rendered as markdown
  bullets stable-sorted by `(category, key)`, then `style_guide.guide_md`, then `active` objectives
  with their open actions, then `active`/`paused` projects — kept byte-stable so the provider's automatic prefix caching engages; and a **volatile block** — current UTC and local datetime — with no cache breakpoint.
- THE SYSTEM SHALL NOT include `proposed` or `archived` context entries in the assembled prompt.
- THE SYSTEM SHALL keep the stable block byte-stable between turns when no underlying record changed
  (deterministic ordering, no timestamps inside it).

---

## 4. Objectives & actions

### REQ-12 — Objectives CRUD
- THE SYSTEM SHALL provide list/create/read/update for `objectives` scoped to the user, with
  `horizon` ∈ {`month`, `quarter`, `year`, `someday`}, `status` ∈ {`active`, `done`, `paused`,
  `dropped`}, `priority` ∈ {1,2,3}, optional `target_date`, a `tags` string array (`skill` /
  `learning` among them), and optional `project_id`.
- WHEN `status` is set to `done`, THE SYSTEM SHALL set `completed_at`; WHEN it leaves `done`, THE
  SYSTEM SHALL clear `completed_at`.
- IF `project_id` does not reference one of the user's projects, THEN THE SYSTEM SHALL reject the
  write with `422`.

### REQ-13 — Actions CRUD
- THE SYSTEM SHALL provide create/update and list-by-objective for `actions`, with `status` ∈
  {`todo`, `doing`, `done`, `dropped`}, optional `due_date`, and `source` ∈ {`manual`, `suggested`}.
- WHEN an action is created by an agent tool, THE SYSTEM SHALL set `source='suggested'`.
- WHEN `status` becomes `done`, THE SYSTEM SHALL set `completed_at`; on leaving `done`, clear it.
- WHEN the parent objective is deleted-guarded (there is no hard delete in Phase 1; objectives move
  to `dropped`), THE SYSTEM SHALL leave child actions intact and reachable by objective id.

---

## 5. Projects

### REQ-14 — Projects CRUD
- THE SYSTEM SHALL provide list/create/read/update for `projects` scoped to the user, with `status` ∈
  {`active`, `paused`, `shipped`, `archived`}, a `tech` string array, free-text `summary`,
  `next_steps`, `notes`, and nullable `repo_path` / `repo_url`.
- THE SYSTEM SHALL accept and store `repo_path` / `repo_url` but SHALL NOT read the filesystem or any
  remote in Phase 1.

---

## 6. Chat

### REQ-15 — Conversations
- THE SYSTEM SHALL provide create/list/read/archive for `conversations` scoped to the user, and
  list-messages-by-conversation returning each message's `role`, `text`, `created_at` (not
  `blocks_json`).
- WHEN the first user message of a conversation is persisted, THE SYSTEM SHALL set the conversation
  `title` to the first ~60 characters of that message (no LLM call).

### REQ-16 — Chat turn (happy path)
- WHEN `POST /api/chat/conversations/{id}/messages` receives `{text}`, THE SYSTEM SHALL respond with
  a `text/event-stream` and SHALL:
  1. rebuild the prior `messages` array from stored `blocks_json`, in `created_at` order;
  2. append the new user message;
  3. run the tool-call loop (OpenAI-compatible API) with the assembled system prompt (REQ-11) and the
     Phase-1 toolset (REQ-18), capped at 12 tool cycles;
  4. emit SSE events: `thinking` (summary), `token` (text delta), `tool`
     (`{name, status, summary}`), then a final `message` (the persisted assistant message), then
     `done`.
- WHEN the turn completes, THE SYSTEM SHALL persist every message the runner produced — the user
  message, each assistant `tool_use` message, each `tool_result` user message, and the final
  assistant text — one `messages` row each, with `blocks_json` = raw content blocks and `text` =
  concatenated text — and SHALL update `conversations.last_message_at`.

### REQ-17 — Chat turn (degraded & failure)
- IF `LLM_API_KEY` is not set, THEN THE SYSTEM SHALL respond `503 {"detail": "AI features not
  configured"}` before starting a stream.
- WHEN a tool function raises, THE SYSTEM SHALL return its result to the model with `is_error: true`,
  emit a `tool` event with `status: "error"`, and continue the loop.
- WHEN the LLM API errors or the response `finish_reason` is `content_filter`, THE SYSTEM SHALL emit an
  `error` event, persist the user message, persist no assistant row, and end the stream.
- WHEN the 12-cycle cap is reached, THE SYSTEM SHALL stop the loop, emit the assistant text produced
  so far, emit a `tool` event noting the cap, and persist normally.

### REQ-18 — Agent toolset
- THE SYSTEM SHALL expose exactly these tools to the runner, each scoped to the authenticated user
  via closure (never model input):
  - read: `get_context(category?)`, `list_objectives(status?, tag?)`, `list_projects(status?)`,
    `get_focus_snapshot()`
  - write: `upsert_context_entry(category, key, value, pinned?)`,
    `archive_context_entry(id)`, `create_objective(...)`, `update_objective(id, ...)`,
    `add_action(objective_id, title, due_date?)`, `update_action(id, ...)`,
    `create_project(...)`, `update_project(id, ...)`, `update_style_guide(guide_md)`
- WHEN `upsert_context_entry` runs, THE SYSTEM SHALL create/update the entry with `status='proposed'`
  (REQ-8) and SHALL NOT make it visible to prompt assembly until approved (REQ-9).
- WHEN `create_objective` / `add_action` / `create_project` / `update_*` run, THE SYSTEM SHALL apply
  the change immediately as `active` (objectives/projects) or with `source='suggested'` (actions).
- WHEN `update_style_guide` runs, THE SYSTEM SHALL overwrite `style_guide.guide_md` directly and bump
  `updated_at`.
- Every write tool SHALL return the created/updated record.

---

## 7. Dashboard

### REQ-19 — Aggregation
- THE SYSTEM SHALL provide `GET /api/dashboard` returning, for the user:
  - per `active` objective: open/total action counts, `% done`, `horizon`, `priority`;
  - momentum: actions completed in the last 7 and 30 days, count of objectives with `updated_at`
    inside 7 days, count of projects with `updated_at` inside 7 days;
  - "what changed this week": objectives/actions/projects with `updated_at` or `completed_at` inside
    7 days, most recent first.
- These figures SHALL come from stored timestamps only — no LLM call.

### REQ-20 — Focus snapshot
- THE SYSTEM SHALL provide `GET /api/dashboard/focus` returning the latest `focus_snapshots` row (or
  `null`) with its `created_at` and a `stale` flag (`true` when older than 24h or absent).
- WHEN `POST /api/dashboard/focus/refresh` is called AND `LLM_API_KEY` is set, THE SYSTEM SHALL
  generate a new snapshot from current objective/project state via one LLM call, store it with the
  state it was based on (`based_on_json`), and return it.
- IF `LLM_API_KEY` is not set, THEN `POST /api/dashboard/focus/refresh` SHALL respond `503` and
  `GET /api/dashboard/focus` SHALL still return any existing snapshot.

---

## 8. Frontend

### REQ-21 — Screens & navigation
- THE SYSTEM SHALL present a persistent left nav (Chat, Dashboard, Objectives, Projects, Context,
  Settings) once authenticated and onboarded.
- Chat SHALL be the index route `/` with: a conversation list, a streaming message thread that
  renders `token` deltas incrementally and shows `tool` chips inline, and a collapsible right
  context sidebar showing active focus, top objectives, active projects, and a link to the review
  queue with the count of `proposed` entries.
- Context SHALL provide category-grouped entry editing, the review queue (approve / edit-approve /
  discard), and the style-guide + samples editor.
- Objectives SHALL provide list + detail with nested actions and create/edit.
- Projects SHALL provide list + detail with create/edit; `repo_path` / `repo_url` fields SHALL be
  labelled as used from Phase 2.
- Dashboard SHALL render the focus panel (with a refresh button), objective progress, momentum
  figures, and the "what changed this week" list.
- Settings SHALL show the account email, a chat-model chooser (persists a `misc/chat_model` context
  entry, honoured per turn), and logout.

### REQ-22 — Auth UX
- WHEN an access token expires mid-session, THE frontend SHALL transparently call
  `POST /api/auth/refresh` once and retry the original request; IF refresh fails, THEN it SHALL
  redirect to `/login`.

---

## 9. Non-functional

### REQ-23 — Security
- All the "Security posture" rows in `.kiro/steering/tech.md` SHALL hold: parameterised SQL only,
  Pydantic on every body, explicit CORS origins, the ASGI security-headers middleware (HSTS only when
  `ENVIRONMENT=prod`), no secret ever logged or sent to the frontend, agent tools scoped by
  session-derived `user_id`.

### REQ-24 — Degradation
- WITH only `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `JWT_SECRET_KEY`, and `CORS_ORIGINS` set (no
  `LLM_API_KEY`), THE SYSTEM SHALL serve auth, onboarding (structured steps), all CRUD,
  `GET /api/dashboard`, and `GET /api/dashboard/focus`, and SHALL return `503` only from the AI
  endpoints named in REQ-17 and REQ-20.

### REQ-25 — Persistence fidelity
- WHEN a conversation with prior tool use is reloaded and continued, THE SYSTEM SHALL reconstruct the
  `messages` array from `blocks_json` such that the LLM API accepts it without shape errors
  (assistant `tool_use` blocks each followed by matching `tool_result` blocks).

### REQ-26 — Tests
- THE SYSTEM SHALL have unit tests for: password/JWT/refresh helpers, system-prompt assembly
  (ordering, exclusion of non-`active` entries, byte-stability), and each agent tool's
  `user_id`-scoping and `status`/`source` defaults.
- THE SYSTEM SHALL have integration tests for: the full auth flow, onboarding submit (with and
  without the AI key, the latter mocked), a chat turn with a stubbed LLM client that exercises one
  tool call and asserts the persisted `messages` rows, and the dashboard aggregation figures.
- Tests SHALL NOT make network calls (in-memory SQLite; LLM client stubbed).

---

## Open questions (resolve before or during design sign-off)

1. Onboarding "current objectives/projects" repeatable inputs — cap at N entries in Phase 1? (Propose:
   soft-cap 5 each in the UI, no server limit.)
2. Should the context sidebar's "active focus" be the latest `focus_snapshot` summary or a separate
   lighter call? (Propose: reuse the snapshot; no extra call.)
3. Conversation list — infinite or capped? (Propose: last 50, no pagination in Phase 1.)
