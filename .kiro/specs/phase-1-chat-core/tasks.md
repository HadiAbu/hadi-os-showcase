# Phase 1 — Chat core — Tasks

Status: draft for review · Date: 2026-09-07

Execution order top to bottom. Each task lists the requirements it satisfies, the files it touches,
and how it is verified. Backend logic is TDD: write the test from the cited EARS criteria first, watch
it fail, implement, watch it pass. Check a box only when its verification actually passes. Commit at
the end of each milestone (and more often within long ones).

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## M0 — Scaffold

- [x] **0.1 Repo skeleton.** Create `backend/`, `frontend/`, `nginx/`, `docker-compose.yml`,
  `.gitignore`, `backend/.env.example`, `frontend/.env.example`. Backend: FastAPI app factory in
  `app/main.py` with an empty `run_migrations()` lifespan hook; `/health` route. `requirements.txt`
  (fastapi, uvicorn, libsql-client, python-jose, bcrypt, pydantic-settings, openai, httpx),
  `requirements-dev.txt` (pytest, pytest-asyncio, aiosqlite), `pytest.ini`.
  _Verify:_ `uvicorn app.main:app` boots; `GET /health` → `200`. ✅ boots; `/health` → 200, `/docs` → 200.
- [x] **0.2 Config.** `app/core/config.py` — `Settings` (pydantic-settings) with every var from
  `tech.md`. `LLM_API_KEY` optional (`LLM_BASE_URL` / `LLM_MODEL` default to Groq). _Verify:_ unit test that `Settings` loads and
  that missing required vars raise. (REQ-23, REQ-24) ✅ `tests/unit/test_config.py` (4 tests) green.
- [x] **0.3 DB client + test harness.** `app/db/client.py` — libsql client (force `https://`, lazy
  import) + `db_execute(sql, params)` returning `list[dict]`; `new_id`/`utcnow_iso` helpers.
  `tests/conftest.py` — in-memory SQLite (`aiosqlite`), autouse fixture, monkeypatches
  `app.db.client.db_execute`. _Verify:_ a trivial test inserts/selects a row through the patched
  helper. ✅ `tests/unit/test_db_client.py` (4 tests) green.
- [x] **0.4 Frontend skeleton.** Vite + React 19 + TS + Tailwind 4 + Router v7 + Axios. `App.tsx`
  with placeholder routes; `lib/api.ts` Axios instance (no interceptor yet). _Verify:_ `npm run dev`
  serves a page; build passes. ✅ `npm install` clean; `npm run build` (tsc + vite) clean.
- [~] **0.5 Compose + nginx.** `nginx/nginx.conf` (dev reverse proxy `/api`→api, `/`→web; `auth_zone`
  on `/api/auth`, `api_zone` on `/api`; SSE-safe `/api/` location). `docker-compose.yml` (api, web,
  nginx; api/web `expose` only; nginx publishes `8080`). _Verify:_ `docker compose up` → app
  reachable at `http://localhost:8080`, `/api/health` proxied. ⚠️ `docker compose config` validates;
  full `up` smoke NOT run — Docker Desktop daemon was not running in the build environment. Re-run
  `docker compose up --build` once Docker is available.

_Commit: "scaffold: backend + frontend + compose"._

---

## M1 — Migrations & auth

- [x] **1.1 Schema.** `app/db/migrations.py` — all 13 tables from `design.md` §2 as idempotent DDL +
  indexes, run from the lifespan. _Verify:_ `test_migrations.py` — every table exists after startup;
  double-run is a no-op. ✅ 2 tests.
- [x] **1.2 Security helpers.** `app/core/security.py` — `hash_password`/`verify_password`
  (bcrypt 12), `create_access_token`/`decode_access_token` (HS256, 15 min, `type`+`sub` verified,
  `TokenError` on any failure), `new_refresh_token`/`hash_refresh_token` (SHA-256), `refresh_expiry`.
  _Verify (TDD):_ `test_security.py` — hash round-trip + salted; tampered / expired / wrong-type /
  wrong-key tokens rejected; refresh hash deterministic & 64-hex. ✅ 9 tests. (REQ-1/2/3, REQ-26)
- [x] **1.3 Register.** `models/auth.py` `RegisterRequest` (EmailStr; 8–72, ≥1 upper, ≥1 digit);
  `POST /api/auth/register`; DB access in `services/users.py`. _Verify (TDD):_ `test_auth.py` — weak
  passwords → 422; dup → 409; success returns id+email, never the hash. ✅ (REQ-1)
- [x] **1.4 Login + lockout.** `POST /api/auth/login` — verify, issue access token, set rotating
  HttpOnly/SameSite=Strict refresh cookie (`path=/api/auth`, `Secure` in prod), store SHA-256 hash.
  `register_failed_attempt` locks at 5 for 15 min; success resets. _Verify (TDD):_ 5 failures then
  correct password → 423; successful login resets the counter. ✅ (REQ-2)
- [x] **1.5 Refresh + logout + cleanup.** `POST /api/auth/refresh` (validate cookie, rotate, revoke
  old, `purge_stale_refresh_tokens`), `POST /api/auth/logout` (revoke + clear cookie, 204).
  _Verify (TDD):_ rotation issues a new token and the replayed old one → 401; no cookie → 401;
  logout then refresh → 401. ✅ (REQ-3)
- [x] **1.6 `current_user` dependency + protection.** `app/core/deps.py` (`HTTPBearer`, identity from
  the verified token only); `GET /api/auth/me`. _Verify (TDD):_ valid token → user; no token → 401;
  garbage token → 401. ✅ (REQ-4)
- [x] **1.7 Security middleware + CORS.** `app/core/middleware.py` pure-ASGI `SecurityHeadersMiddleware`
  (CSP, X-Frame-Options=DENY, X-Content-Type-Options=nosniff, Referrer-Policy, Permissions-Policy;
  HSTS only in prod); explicit `CORS_ORIGINS` list, credentials allowed. _Verify (TDD):_ headers
  present on `/health`, HSTS absent in dev. ✅ (REQ-23)
- [~] **1.8 Frontend auth.** `contexts/AuthContext.tsx` + `AuthProvider.tsx`, `hooks/useAuth.ts`;
  `lib/api.ts` in-memory token + single-flight refresh interceptor (one retry, then auth-failure
  handler → `/login`); `pages/Login.tsx` / `Register.tsx`; `RequireAuth` guard + nav `Shell` +
  boot-time refresh in `App.tsx`. _Verify:_ ✅ `npm run build` (tsc strict + vite) clean. ⚠️ manual
  register→login→reload E2E pending — needs a running backend with real Turso creds. (REQ-22)

_Commit: "auth: register/login/refresh/logout + guards"._

---

## M2 — Context store & assembly

- [x] **2.1 Context entries CRUD.** `models/context.py`, `services/context_store.py`,
  `api/routes/context.py` — list (`?category=&status=`) / create / patch / archive; create is an
  upsert on `(user_id, category, key)`; UI path `source='manual'`, `status='active'`; patch guards
  a natural-key collision → 409. _Verify (TDD):_ `test_context.py` — defaults; upsert not duplicate;
  patch + archive; 404; user-scoped; auth required. ✅ (REQ-8)
- [x] **2.2 Review queue.** `GET /context/review` (status `proposed`), `POST .../approve` (`{value?}`
  → edit-then-activate), `POST .../discard` (→ archived). _Verify (TDD):_ lists only proposed;
  proposed absent from active set; approve activates; edit-approve persists value; discard archives.
  ✅ (REQ-9)
- [x] **2.3 Style guide + samples.** `services/style.py`; `GET`/`PUT /context/style-guide` (empty
  default, no row created on GET; upsert on PUT), `style-samples` list/add/delete (204/404).
  _Verify (TDD):_ ✅ (REQ-10)
- [x] **2.4 System-prompt assembly.** `services/context_assembly.py` `build_system(user_id)` — two
  text blocks, `cache_control: ephemeral` on block 1 only; block 1 = base prompt + `<about_me>` +
  `<writing_style>` (omitted when empty) + `<objectives>` (with `todo`/`doing` actions only) +
  `<projects>` (active/paused); deterministic `ORDER BY`; volatile time in block 2.
  _Verify (TDD):_ `test_context_assembly.py` — block structure; `proposed`/`archived` excluded;
  style section omit/present; done actions excluded; projects archived excluded; **block 1
  byte-identical across two calls**. ✅ 6 tests. (REQ-11, REQ-25)
- [~] **2.5 Frontend Context page.** `pages/Context.tsx` — tabs Entries (category-grouped, inline
  edit / pin / archive, add form), Review (editable value, Approve / Approve-edited / Discard, count
  badge), Style (guide textarea + save, samples list add/remove); wired at `/context`. _Verify:_
  ✅ `npm run build` clean. ⚠️ manual against a seeded user pending real DB. (REQ-21)

_Commit: "context: store, review queue, style guide, assembly"._

---

## M3 — Objectives, actions, projects

- [x] **3.1 Projects CRUD.** `models/projects.py`, `services/projects_store.py` (JSON `tech`
  hydrate/serialize, `project_exists` helper), `api/routes/projects.py` — list (`?status=`) /
  create / read / patch; `repo_path`/`repo_url` stored, never read. _Verify (TDD):_ `test_projects.py`
  — defaults; tech round-trips as a list; 404; patch; user-scoped. ✅ (REQ-14)
- [x] **3.2 Objectives CRUD.** `services/objectives_store.py` — list (`?status=&tag=`, tag filtered
  in Python, ordered by priority→created_at), create/read/patch; `priority` 1–3 (422 out of range);
  `tags` JSON; `completed_at` set on →`done` / cleared on leaving `done`; `project_id` ownership →
  422; `GET /objectives/{id}` returns `{objective, actions}`. _Verify (TDD):_ `test_objectives.py`
  — defaults; priority bounds; completed_at toggling; unknown vs valid project_id; tag filter +
  ordering. ✅ (REQ-12)
- [x] **3.3 Actions CRUD.** `POST /objectives/{id}/actions` (`source='manual'`, 404 if objective
  missing), `PATCH /actions/{id}`; `completed_at` managed; objective →`dropped` (no hard delete)
  leaves child actions reachable. _Verify (TDD):_ action lifecycle + detail; 404 under missing
  objective; dropped objective keeps actions. ✅ (REQ-13)
- [~] **3.4 Frontend Objectives + Projects pages.** `pages/Projects.tsx` (add form + expandable
  editor rows, `repo_*` fields greyed "Phase 2"), `pages/Objectives.tsx` (add form with project
  dropdown, priority/horizon/tags, inline status select, expandable nested action list with
  add + per-action status). Wired at `/objectives`, `/projects`. _Verify:_ ✅ `npm run build` clean.
  ⚠️ manual CRUD round-trip pending real DB. (REQ-21)

_Commit: "objectives, actions, projects: CRUD + pages"._

---

## M4 — Onboarding

> **Pulled forward from M5:** `services/llm_client.py` was created here (needed by 4.3):
> `available()`, `chat_model_for(override)`, `one_shot()`, `extract_json()` (async `anthropic`
> 1.x client, lazy import, adaptive thinking). M5 task 5.1 now only adds the streaming Tool Runner.

- [x] **4.1 Question bank.** `services/onboarding_questions.py` (10 questions per `design.md` §7);
  `GET /onboarding/questions`, `GET /onboarding/state`. _Verify (TDD):_ `test_onboarding.py` —
  question ids + `style_tone` options; state reflects `onboarding_state`; auth required. ✅ (REQ-5, 6)
- [x] **4.2 Submit (structured).** `services/onboarding.py` + `POST /onboarding/submit` — store raw
  answers (`onboarding_responses`); upsert `context_entries` (`onboarding`/`active`) from the mapped
  answers; create `objectives` (horizon `quarter`) + `projects`, skipping same-title/-name
  duplicates; store `style_samples`; upsert `onboarding_state.completed_at`. _Verify (TDD):_
  structured entries + objectives + projects + samples created; re-run doesn't duplicate. ✅ (REQ-5, 7)
- [x] **4.3 Submit (AI enrichment).** When `llm_client.available()`: one `extract_json` call over
  `free_goal` + samples → `proposed` `context_entries` + `style_guide.guide_md`. Absent key →
  `skipped`; exception → `error`; onboarding completes and structured seeding persists either way.
  _Verify (TDD):_ all three enrichment outcomes with `llm_client` monkeypatched. ✅ (REQ-7, REQ-24)
- [~] **4.4 Frontend onboarding wizard.** `pages/Onboarding.tsx` — one-question-per-step stepper with
  progress bar, multi-select chips, repeatable inputs (cap 5), samples paste; `AuthProvider` now
  tracks `onboarded` (from `/onboarding/state`) + `markOnboarded()`; `App.tsx` gate — `RequireAuth`
  redirects incomplete users to `/onboarding`, `/onboarding` itself needs auth only (re-runnable).
  _Verify:_ ✅ `npm run build` clean. ⚠️ manual first-run flow pending real DB. (REQ-5, REQ-21)

_Commit: "onboarding: question bank, submit, enrichment, wizard"._

---

## M5 — Chat agent loop

> **Post-M7 provider swap (see `design.md` §11.7):** the LLM layer moved from the Anthropic Claude
> API + Tool Runner to an **OpenAI-compatible API, default Groq**, to keep cost at ~$0. `llm_client`
> now wraps the `openai` SDK (`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`); `chat_agent` runs a
> **manual tool-call loop** over `llm_client.create_chat`; `agent_tools` exposes `TOOL_SPECS` +
> `dispatch` instead of `@beta_async_tool` closures; `context_assembly.build_system` returns a
> string. All M5 tests were rewritten to a scripted fake `create_chat`. The M5 notes below describe
> the original Anthropic build; the current code is the OpenAI-compatible version. **103 tests pass.**

> Consulted the `claude-api` skill (`python/claude-api/{README,tool-use,streaming}.md`).
> **Decision recorded:** the Python Tool Runner's *streaming* iteration API is thinly documented and
> cannot be live-tested here, so `chat_agent` uses the well-documented **non-streaming** iteration
> (`async for message in runner`, `runner.generate_tool_call_response()`). Consequence: assistant
> text is delivered as `token` chunks at the end of the turn rather than true per-token. The SSE
> contract is unchanged. True token streaming is a later refinement (see `design.md` §11).
> `beta_async_tool` confirmed importable in `anthropic` 1.4.0.

- [x] **5.1 `llm_client`.** `available()`, `chat_model_for(override)`, `one_shot()`, `extract_json()`
  (M4), plus `tool_runner(model, system, messages, tools)` wrapping
  `client.beta.messages.tool_runner` with adaptive thinking. Tests replace `tool_runner` with a
  scripted fake. _Verify:_ covered via `test_config` (`ai_enabled`) + the chat tests. ✅ (REQ-17, 24)
- [x] **5.2 Agent tools.** `services/agent_tools.py` — 13 `_impl_*` async functions (explicit
  `user_id`, unit-tested) + `build_toolset(user_id)` returning `@beta_async_tool` closures that bind
  `user_id` and carry the model-facing descriptions. `upsert_context_entry` → `proposed`/`chat`;
  `add_action` → `suggested`; objectives/projects active. _Verify (TDD):_ `test_agent_tools.py` —
  status/source defaults, user scoping, cross-user archive no-op, toolset has 13. ✅ (REQ-18, REQ-23)
- [x] **5.3 Conversations CRUD.** `models/chat.py`, `services/chat_store.py`, `api/routes/chat.py` —
  create / list (last 50, `?archived=`) / archive; `GET .../messages` → `role/text/created_at`.
  _Verify (TDD):_ CRUD + archive filter; 404 for missing; title from first message (in 5.4). ✅ (15)
- [x] **5.4 Turn engine.** `services/chat_agent.py` `run_turn()` — rebuild `messages` from
  `blocks_json` (thinking blocks stripped on replay), persist the user message immediately, drive
  the runner (cap 12), emit `tool` events live, **buffer** assistant/tool-result rows and persist
  them only on success, set title from the first message. _Verify (TDD):_ `test_chat.py` — SSE order
  `tool,tool,token,message,done`; 4 persisted rows `user/assistant/user/assistant`; **continue** →
  captured `messages` shows `assistant(tool_use)` then `user(tool_result)` then new `user` (REQ-25).
  ✅ *(Also fixed: `utcnow_iso()` now microsecond-precision so same-second rows sort by insertion.)*
  (REQ-16, REQ-25)
- [x] **5.5 Turn engine — degraded & failure.** `503` before any stream when `!available()`;
  `refusal` stop reason → `error` event + only the user message persisted; 12-cycle cap → `(loop)`
  notice + graceful `done`; any loop exception → `error` event. _Verify (TDD):_ all three with the
  fake runner. ✅ (REQ-17)
- [x] **5.6 SSE endpoint.** `POST /chat/conversations/{id}/messages` → `StreamingResponse`
  (`text/event-stream`), frames `event: <name>\ndata: <json>\n\n`; 404 unknown conversation; 503
  no key. _Verify:_ integration test reads the stream frame-by-frame. ✅ (REQ-16)
- [~] **5.7 Frontend chat.** `lib/sse.ts` (`fetch` stream reader, one 401→refresh retry);
  `pages/Chat.tsx` — conversation list · thread with inline tool chips + streaming assistant draft ·
  collapsible "what it knows" sidebar (objectives / projects / review count / focus), refreshed on
  mount + each `done`. Wired at `/`. _Verify:_ ✅ `npm run build` clean. ⚠️ manual send/stream flow
  pending real DB + API key; nav-shell + chat's own sidebar overlap noted for M7. (REQ-21)

_Commit: "chat: llm client, agent tools, streaming turn engine, chat UI"._

---

## M6 — Dashboard & focus

- [x] **6.1 Aggregation.** `services/dashboard.py` + `GET /dashboard` — per active objective
  open/total/`pct_done`; momentum (`actions_done_7d/30d` from `completed_at`, `objectives_touched_7d`
  / `projects_touched_7d` from `updated_at`); `changed_this_week` (objectives/actions/projects with
  a timestamp inside 7d, merged, newest first, capped 20). Timestamp arithmetic only. _Verify (TDD):_
  `test_dashboard.py` — progress numbers, all four momentum counts, change kinds + ordering; no LLM
  call when key absent. ✅ (REQ-19)
- [x] **6.2 Focus snapshot.** `services/focus.py` — `GET /dashboard/focus` (latest row or
  `{null,null,stale:true}`; `stale` when >24h); `POST /dashboard/focus/refresh` = one
  `llm_client.one_shot` over active/paused objectives+projects → store `content_md` + `based_on_json`;
  `503` when `!available()` (GET still serves). _Verify (TDD):_ default stale/null; 503 without key;
  refresh stores + subsequent GET serves it, `stale=false`. ✅ (REQ-20, REQ-24)
- [~] **6.3 Frontend dashboard.** `pages/Dashboard.tsx` — Focus card (refresh button, `stale` badge,
  503 message), Momentum stat tiles, Objective-progress bars, "Changed this week" list. Wired at
  `/dashboard`. _Verify:_ ✅ `npm run build` clean. ⚠️ manual against seeded data pending real DB.
  A richer `dataviz`-guided visual pass is deferred to M7 polish. (REQ-21)

_Commit: "dashboard: aggregation, focus snapshot, dashboard UI"._

---

## M7 — Settings, polish, end-to-end

- [x] **7.1 Settings.** `pages/Settings.tsx` — account email, chat-model radio (Sonnet 5 / Opus 5)
  persisting a `misc/chat_model` context entry via `POST /context/entries`, logout. `chat_agent`
  `_resolve_model` reads that entry per turn. _Verify (TDD):_ `test_chat.py` — override →
  `capture["model"] == "claude-opus-5"`; an invalid value falls back to `claude-sonnet-5`. ✅ (REQ-21)
- [x] **7.2 Degradation pass.** `test_degradation.py` (autouse `available()=False`) — onboarding
  (structured, `enrichment: skipped`), context/objectives/projects CRUD, `GET /dashboard`, and
  `GET /dashboard/focus` all `200`; `POST /chat/.../messages` and `POST /dashboard/focus/refresh`
  → `503`. Frontend: `lib/sse.ts` surfaces "AI features are not configured" on 503; the Dashboard
  focus card shows the same. ✅ (REQ-24)
- [x] **7.3 Security review pass.** Walked every `tech.md` "Security posture" row against the code:
  bcrypt(12) + strength check; 5/15-min lockout; HS256 15-min access token (`type`+`sub` verified);
  rotating SHA-256 refresh cookie (HttpOnly, SameSite=Strict, `path=/api/auth`, Secure in prod),
  stale rows purged on login/refresh; **parameterised SQL only** (dynamic `SET` clauses use fixed
  Pydantic-field / hardcoded column names, values always bound); Pydantic on every body; explicit
  CORS list; ASGI headers middleware (HSTS prod-only); `LLM_API_KEY` never logged or returned;
  agent tools bind `user_id` in the closure and scope every query; cross-user ids → 404.
  `test_cross_user.py` adds objective/conversation/context scoping + a headers assertion on an API
  route. ✅ (REQ-23)
- [x] **7.4 Full test run + README.** `pytest -q` → **103 passed**, zero network. `README.md` written
  (run the stack via Docker or bare, run tests, env vars, layout, what's left to verify).
  `.env.example` files finalised. ⚠️ the clean `docker compose up` walkthrough itself is still
  pending a running Docker daemon + real Turso creds. (REQ-26)

_Commit: "settings, degradation + security passes, docs — Phase 1 complete"._

---

## Definition of done (Phase 1)

**Met:**
- Every task above is `[x]`; each backend task has a passing test.
- `pytest -q` → **109 passed**, zero network calls (Turso → in-memory SQLite, LLM client stubbed).
- `npm run build` (tsc strict + vite) clean.
- All 26 requirements traceable to a passing test.

**Live run — done (2026-09-08, local uvicorn + real Turso + real Groq key):**
- `run_migrations()` created all 13 tables in a real Turso DB on startup.
- register → login (real JWT) → onboarding submit → **AI enrichment produced 6 `proposed` context
  entries** (career goal, technical focus, and 4 writing-style observations) from the free-text goal
  + one writing sample.
- Chat turn against Groq `openai/gpt-oss-120b`: streamed SSE (`token`/`message`/`done`), answered
  grounded in the real objectives, and **in the owner's style** (the enrichment style guide fed the
  system prompt).
- Tool-calling turn: model called `create_objective`, the objective was persisted, model confirmed.
- `GET /dashboard` figures correct; `POST /dashboard/focus/refresh` generated + stored a real note.
- UTF-8 round-trips cleanly at every layer (SSE, Turso, HTTP response).

**Fixes the live run surfaced (committed):**
- `client.normalize_db_url` — Turso now hands out `turso://` URLs (also handle `wss://`, bare host);
  was only converting `libsql://`. + unit tests.
- Default `LLM_MODEL` → `openai/gpt-oss-120b` (`llama-3.3-70b-versatile` was retired / not on the
  account). Groq model ids rotate — check `console.groq.com/docs/models` if it 404s.
- `agent_tools.dispatch` drops `""`/`None` args (models send `{"status":""}` for unset filters).
- `focus.refresh` `max_tokens` 600 → 1200 (reasoning-model headroom).

**Pre-push review pass (self + `/code-review` agent) — fixed:**
- `Settings.tsx` "use server default" posted `value:""` → 422 + UI stuck on "saving…". Now archives
  the `misc/chat_model` entry; all model changes are `try/catch`ed with an error state.
- `chat_agent` tool-error detection was a substring sniff (`'"error"' in result[:20]`) → now
  `_result_is_error` parses the JSON and checks for a top-level `"error"` key. + test.
- `objectives_store` / `projects_store` coerce `tags` / `tech` to a `list[str]` before storing — a
  tool call sending a bare string used to write malformed JSON that 500'd every later read. + tests.
- `_rebuild_messages` skips legacy list-shaped `blocks_json` rows (pre-provider-swap) instead of
  crashing the turn with `AttributeError`. + test.
- `finish_reason == "length"` (truncated completion) now emits a `(truncated)` notice instead of
  silently serving a cut-off answer; chat `max_tokens` 4096 → 8192. + test.
- `usage_json` persistence restored — summed across tool cycles onto the final assistant row
  (regression from the provider swap; verified live: `total_tokens` recorded).
- `llm_client` client gets a 90s timeout + 1 retry (was the SDK's 10-min default — a hung request
  would stall the SSE stream).
- `_tool_summary` truncates each arg value to 40 chars.
- Conversation is titled until it has a real assistant reply (covers a first turn that errored).
- `tech.md` softened: the "env-only provider switch" claim now excludes OpenAI reasoning models
  (`o1`/`o3`/`gpt-5` need `max_completion_tokens`).
- Reviewer's flag on the `qwen/qwen3.8-27b` preset was checked against a **live** `models.list()` —
  it is valid on the account; kept.
- **114 tests pass**; live re-verify green (multi-tool turn, coercion path, usage recorded).

**Docker full-stack smoke — done (2026-09-08):** `docker compose up --build` → all 3 containers up,
migrations ran, and through nginx `:8080`: `GET /` 200, `GET /api/health` ok, `GET /api/auth/me` 401,
and a full register → login → onboard → **streamed chat turn** (nginx → api → Turso + Groq). Torn
down clean.

**Browser walkthrough — done (2026-09-08, Docker stack + Playwright):** every screen driven in a
real browser — register → onboarding wizard (all question types) → Chat (streamed turn, tool chips,
context sidebar) → Context (entries, review-queue approve, tabs+badge) → Objectives (create,
expand, agent-created "suggested" action) → Projects → Dashboard (momentum, progress bar,
changed-this-week, focus refresh via Groq) → Settings (model radios + revert-to-default).

**Bugs the browser walkthrough surfaced (fixed + re-verified):**
- **A confirmed context entry could be silently downgraded to `proposed`.** `context_store.create_entry`
  upserts on `(category, key)`; onboarding's AI enrichment proposes an `identity/role` inference
  *after* structured seeding, so the proposal overwrote the confirmed active entry (the value the
  user typed in step 2 vanished). Fix: a `proposed` create never touches an existing `active` entry.
  + test.
- Onboarding lost fast-typed values between steps — the question `<input>` was reused across
  questions. Fix: `key={q.id}` remounts it per step.
- Chat's first-load bootstrap created a second, empty conversation (React StrictMode / re-render
  double-invoke). Fix: a `useRef` run-once guard.
- Dashboard "Focus now" showed literal `**markdown**`. Fix: a tiny `Markdownish` renderer.
- No favicon (404). Added `frontend/public/favicon.svg` + a `public/` volume mount in compose.

**Known-minor (not fixed):** the Chat sidebar's focus snippet still shows raw markdown; a 401 on the
boot `/auth/refresh` logs a console error while logged out (expected for cookie auth).

**115 tests pass**; browser re-verify of all four fixes green.

**Carried forward** (recorded in `design.md` §11): restore true per-token streaming in the chat turn
by switching `llm_client.create_chat` to `stream=True` and consuming deltas.
