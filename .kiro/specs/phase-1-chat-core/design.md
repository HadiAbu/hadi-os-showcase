# Phase 1 — Chat core — Design

Status: draft for review · Date: 2026-09-07 · Satisfies: `requirements.md` REQ-1…REQ-26

Read alongside `.kiro/steering/tech.md` (stack, security, conventions) and `structure.md` (module
boundaries). This document expands the approved brainstorming design with DDL, endpoint signatures,
tool schemas, and screen specs.

---

## 1. Architecture

Three tiers, mirroring the sibling projects:

```
React SPA (Vite/TS)  ──HTTP──▶  FastAPI  ──▶  Turso (libSQL, https scheme)
   chat + SSE         ◀─SSE──   - auth
                                - context / assembly       ──▶  Claude API
                                - chat agent loop (Tool Runner, streaming)
                                - CRUD: objectives / actions / projects / context
                                - onboarding, dashboard, focus
```

- Single host port `8080` via `nginx` (dev-only reverse proxy + rate limiting). `api` / `web`
  `expose` internally only.
- FastAPI lifespan runs `run_migrations()` on startup.
- The Anthropic client is constructed lazily in `services/llm_client.py`; if `ANTHROPIC_API_KEY` is
  unset, `llm_client.available()` is `False` and AI routes short-circuit to `503`.

### Request → module flow (chat turn)

```
POST /api/chat/conversations/{id}/messages
  └─ api/routes/chat.py            validate {text}, resolve user, open StreamingResponse
      └─ services/chat_agent.run_turn(user, conversation_id, text)
          ├─ services/context_assembly.build_system(user)      → [stable_block, volatile_block]
          ├─ load messages rows → parse blocks_json → messages[]
          ├─ services/llm_client.tool_runner(system, messages, tools, ...)  (streaming)
          │     tools = services/agent_tools.build_toolset(user)   # closures bind user_id
          ├─ for each stream event → yield SSE (thinking | token | tool)
          └─ on done → persist produced messages → yield message, done
```

---

## 2. Data model (DDL)

All tables carry `id TEXT PRIMARY KEY` (UUID v4) unless noted, `user_id TEXT NOT NULL` referencing
`users(id)`, and `created_at TEXT NOT NULL` (ISO-8601 UTC). Booleans are `INTEGER` `0/1`. "JSON"
columns are `TEXT`. Written as idempotent `CREATE TABLE IF NOT EXISTS` in `db/migrations.py`.

```sql
-- Auth ---------------------------------------------------------------
users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  failed_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,                       -- ISO ts or NULL
  created_at TEXT NOT NULL
);

refresh_tokens (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token_hash TEXT NOT NULL,                -- SHA-256 of the raw token
  expires_at TEXT NOT NULL,
  revoked INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
-- index: (user_id), (token_hash)

-- Context ------------------------------------------------------------
context_entries (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  category TEXT NOT NULL,                  -- identity|preference|goal_context|project_context|working_style|misc
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  source TEXT NOT NULL,                    -- onboarding|chat|import|manual
  pinned INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active',   -- active|proposed|archived
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (user_id, category, key)
);
-- index: (user_id, status)

style_samples (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  text TEXT NOT NULL,
  label TEXT,
  created_at TEXT NOT NULL
);

style_guide (
  user_id TEXT PRIMARY KEY,
  guide_md TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

-- Objectives & actions --------------------------------------------------
objectives (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  horizon TEXT NOT NULL,                   -- month|quarter|year|someday
  target_date TEXT,
  status TEXT NOT NULL DEFAULT 'active',   -- active|done|paused|dropped
  priority INTEGER NOT NULL DEFAULT 2,     -- 1..3
  tags TEXT NOT NULL DEFAULT '[]',         -- JSON array of strings
  project_id TEXT,                         -- nullable FK -> projects(id)
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT
);
-- index: (user_id, status)

actions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  objective_id TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'todo',     -- todo|doing|done|dropped
  notes TEXT NOT NULL DEFAULT '',
  due_date TEXT,
  source TEXT NOT NULL DEFAULT 'manual',   -- manual|suggested
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT
);
-- index: (user_id, objective_id)

-- Projects ---------------------------------------------------------------
projects (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',   -- active|paused|shipped|archived
  tech TEXT NOT NULL DEFAULT '[]',         -- JSON array
  repo_path TEXT,
  repo_url TEXT,
  next_steps TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
-- index: (user_id, status)

-- Chat -----------------------------------------------------------------
conversations (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_message_at TEXT
);
-- index: (user_id, archived, last_message_at)

messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,                      -- user|assistant
  text TEXT NOT NULL DEFAULT '',           -- display/search convenience
  blocks_json TEXT NOT NULL,              -- one OpenAI-format message dict (source of truth); see §11.7
  model TEXT,
  usage_json TEXT,
  created_at TEXT NOT NULL
);
-- index: (conversation_id, created_at)

-- Onboarding & dashboard ----------------------------------------------
onboarding_responses (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  answer TEXT NOT NULL,
  created_at TEXT NOT NULL
);

onboarding_state (
  user_id TEXT PRIMARY KEY,
  completed_at TEXT,
  version INTEGER NOT NULL DEFAULT 1
);

focus_snapshots (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  content_md TEXT NOT NULL,
  based_on_json TEXT NOT NULL,            -- snapshot of objective/project state used
  created_at TEXT NOT NULL
);
-- index: (user_id, created_at)
```

`tool_result` blocks are stored inside the `blocks_json` of a `role='user'` message row (that is how
the Anthropic messages array represents them). A "tool turn" therefore produces two rows: one
`assistant` row whose `blocks_json` holds `tool_use` blocks, then one `user` row whose `blocks_json`
holds the matching `tool_result` blocks and whose `text` is `''`.

---

## 3. Context assembly (`services/context_assembly.py`)

`build_system(user_id) -> list[SystemBlock]`

Returns exactly two blocks:

**Block 1 — stable (carries the cache breakpoint):**

```
<base instructions>            # static string, versioned in code as BASE_SYSTEM_PROMPT
                               # role of hadi-os; behavioural rules; "match <writing_style> in prose
                               # only — never in code, lists, tables, or structured output"

<about_me>
- {category}/{key}: {value}    # every active context_entries row, sorted by (category, key)
...

<writing_style>
{style_guide.guide_md}          # omitted if empty

<objectives>
- [{priority}] {title} ({horizon}, {status}){ tags: skill,learning}
    - ({action.status}) {action.title}{ due {due_date}}   # open actions only (todo|doing)
...                             # active objectives, ordered by (priority asc, created_at asc)

<projects>
- {name} ({status}) — {summary}
  next: {next_steps}
...                             # active + paused projects, ordered by name
```

Emitted as `{"type": "text", "text": <joined string>, "cache_control": {"type": "ephemeral"}}`.

**Block 2 — volatile (no cache_control):**

```
{"type": "text", "text": "Current time: 2026-09-07T14:03:00Z (local: Sun 7 Sep 2026, 16:03)"}
```

Rules:
- Deterministic ordering everywhere; **no timestamps, counts, or ids inside Block 1** — it must be
  byte-identical between turns when no record changed (REQ-11, verified by a unit test).
- `proposed` / `archived` entries are never included.
- If the rendered Block 1 ever exceeds a soft budget (~12k tokens; measured with
  `messages.count_tokens` during dev), log a warning — Phase 2 introduces summarisation/retrieval.

---

## 4. Chat agent loop (`services/chat_agent.py`)

`async def run_turn(user, conversation_id, text) -> AsyncIterator[SSEEvent]`

1. `if not llm_client.available(): raise AIUnavailable` → route returns `503` (REQ-17).
2. `system = context_assembly.build_system(user.id)`.
3. Load `messages` rows for the conversation ordered by `created_at`; `blocks = json.loads(row.blocks_json)`;
   build `messages=[{"role": row.role, "content": blocks}, ...]`.
4. Append `{"role": "user", "content": [{"type": "text", "text": text}]}`.
5. `tools = agent_tools.build_toolset(user.id)` — list of `@beta_tool`-decorated closures.
6. Run the **Tool Runner in streaming mode** via `llm_client`:
   - `model = settings.CHAT_MODEL` (default `claude-sonnet-5`)
   - `thinking = {"type": "adaptive", "display": "summarized"}`
   - `betas = [...]` — the Tool Runner beta flag(s); confirm exact strings from the `claude-api`
     skill's `python/claude-api/tool-use.md` at implementation time
   - iteration cap: 12 tool cycles (runner's max-iterations option; if unavailable, count manually
     and stop)
7. Translate runner/stream events → SSE:
   - text delta → `event: token`, `data: {"delta": "..."}`
   - thinking summary → `event: thinking`, `data: {"summary": "..."}`
   - a tool about to run → `event: tool`, `data: {"name": n, "status": "running", "summary": s}`
   - tool finished → `event: tool`, `data: {"name": n, "status": "done"|"error", "summary": s}`
8. On completion:
   - collect the full message list the runner built; diff against what was loaded in step 3 to get
     the **new** entries (the appended user message + everything the runner added).
   - persist each new entry as a `messages` row (`blocks_json` = its `content`, `text` = concatenated
     `text` blocks, `model`/`usage_json` on assistant rows where available).
   - `conversations.last_message_at = now`, `updated_at = now`; set `title` if this was the first
     user message (REQ-15).
   - `event: message`, `data: {"message": <persisted assistant row, minus blocks_json>}` then
     `event: done`, `data: {}`.

Failure handling (REQ-17): tool exception → runner returns `is_error: true` result, loop continues,
`tool` error event emitted. API error / `stop_reason == "refusal"` → `event: error`,
`data: {"detail": ...}`; persist only the user message; end stream. Cap reached → stop, emit produced
text, emit a `tool` event noting the cap, persist normally.

SSE transport: FastAPI `StreamingResponse(generator(), media_type="text/event-stream")`, each event
written as `event: <name>\ndata: <json>\n\n`. Auth via the normal `Authorization: Bearer` header
(so the frontend uses `fetch` + a stream reader, not `EventSource`).

---

## 5. Agent tools (`services/agent_tools.py`)

`build_toolset(user_id)` returns a list of `@beta_tool` functions closing over `user_id`. None of
them accept a user/owner parameter. All timestamps set server-side. Each write returns the
created/updated record as a dict.

| Tool | Params | Behaviour |
|---|---|---|
| `get_context` | `category?: str` | List `active` + `proposed` entries (flagged), optionally filtered. |
| `list_objectives` | `status?: str`, `tag?: str` | List objectives (+ nested open actions), filtered. |
| `list_projects` | `status?: str` | List projects. |
| `get_focus_snapshot` | — | Return latest `focus_snapshots.content_md` + `created_at` + `stale`. |
| `upsert_context_entry` | `category: str`, `key: str`, `value: str`, `pinned?: bool` | Upsert by `(user_id, category, key)`; force `status='proposed'`, `source='chat'`. |
| `archive_context_entry` | `id: str` | Set `status='archived'` (ownership-checked). |
| `create_objective` | `title`, `horizon`, `description?`, `priority?`, `tags?: list[str]`, `target_date?`, `project_id?` | Insert `status='active'`; validate `project_id` ownership. |
| `update_objective` | `id`, + any of the above + `status?` | Patch; manage `completed_at` on `done` transitions. |
| `add_action` | `objective_id`, `title`, `due_date?` | Insert `status='todo'`, `source='suggested'`; validate objective ownership. |
| `update_action` | `id`, `title?`, `status?`, `notes?`, `due_date?` | Patch; manage `completed_at`. |
| `create_project` | `name`, `summary?`, `status?`, `tech?: list[str]`, `repo_path?`, `repo_url?`, `next_steps?`, `notes?` | Insert `status='active'`. |
| `update_project` | `id`, + any of the above | Patch. |
| `update_style_guide` | `guide_md: str` | Overwrite `style_guide.guide_md`; bump `updated_at`. |

Tool descriptions (the text the model sees) live next to each function and should state *when* to use
it and that context entries require the owner's later confirmation.

---

## 6. HTTP API

All under `/api`. All except `auth/*` and `/health` require a valid access token. Bodies and
responses are Pydantic models in `models/<feature>.py`.

### auth
| Method | Path | Body → Result |
|---|---|---|
| POST | `/auth/register` | `{email, password}` → `201 {id, email}` / `409` / `422` |
| POST | `/auth/login` | `{email, password}` → `200 {access_token}` + refresh cookie / `401` / `423` |
| POST | `/auth/refresh` | cookie → `200 {access_token}` + rotated cookie / `401` |
| POST | `/auth/logout` | cookie → `204` |
| GET | `/auth/me` | → `{id, email}` |

### onboarding
| GET | `/onboarding/state` | → `{completed: bool, completed_at}` |
| GET | `/onboarding/questions` | → `[{id, type, prompt, options?}]` |
| POST | `/onboarding/submit` | `{answers: [{question_id, value}], samples: [{text, label?}]}` → `200 {completed_at, enrichment: "done"|"skipped"|"error"}` |

### context
| GET | `/context/entries?category=&status=` | → `[entry]` |
| POST | `/context/entries` | `{category, key, value, pinned?}` → `201 entry` (status `active`) |
| PATCH | `/context/entries/{id}` | `{value?, pinned?, category?, key?}` → `200 entry` |
| POST | `/context/entries/{id}/archive` | → `200 entry` |
| GET | `/context/review` | → `[entry]` (status `proposed`) |
| POST | `/context/review/{id}/approve` | `{value?}` → `200 entry` (status `active`) |
| POST | `/context/review/{id}/discard` | → `200 entry` (status `archived`) |
| GET | `/context/style-guide` | → `{guide_md, updated_at}` |
| PUT | `/context/style-guide` | `{guide_md}` → `200` |
| GET / POST / DELETE | `/context/style-samples[/{id}]` | list / add / delete |

### objectives / actions
| GET | `/objectives?status=&tag=` | → `[objective]` |
| POST | `/objectives` | `{title, horizon, description?, priority?, tags?, target_date?, project_id?}` → `201` |
| GET | `/objectives/{id}` | → `{objective, actions: [...]}` |
| PATCH | `/objectives/{id}` | partial → `200` |
| POST | `/objectives/{id}/actions` | `{title, due_date?}` → `201 action` (source `manual`) |
| PATCH | `/actions/{id}` | `{title?, status?, notes?, due_date?}` → `200` |

### projects
| GET | `/projects?status=` | → `[project]` |
| POST | `/projects` | `{name, summary?, status?, tech?, repo_path?, repo_url?, next_steps?, notes?}` → `201` |
| GET | `/projects/{id}` | → `project` |
| PATCH | `/projects/{id}` | partial → `200` |

### chat
| GET | `/chat/conversations?archived=` | → `[{id, title, last_message_at}]` (last 50) |
| POST | `/chat/conversations` | `{}` → `201 {id}` |
| GET | `/chat/conversations/{id}/messages` | → `[{role, text, created_at}]` |
| POST | `/chat/conversations/{id}/messages` | `{text}` → `text/event-stream` (§4) / `503` |
| POST | `/chat/conversations/{id}/archive` | → `200` |

### dashboard
| GET | `/dashboard` | → aggregation (REQ-19) |
| GET | `/dashboard/focus` | → `{content_md, created_at, stale} | null` |
| POST | `/dashboard/focus/refresh` | → new snapshot / `503` |

---

## 7. Onboarding question bank (initial)

`services/onboarding_questions.py` — a list of dicts, versioned in code.

| id | type | seeds |
|---|---|---|
| `identity_name` | text | `context_entries` identity/name |
| `identity_role` | text | identity/role |
| `identity_experience` | long_text | identity/experience_summary |
| `style_tone` | multi_select | working_style/preferred_tone |
| `style_samples` | repeatable(long_text) | `style_samples` rows |
| `working_hours` | text | working_style/working_hours |
| `objective_current` | repeatable | `objectives` (title, horizon, priority) |
| `project_current` | repeatable | `projects` (name, summary, status) |
| `growth_focus` | long_text | goal_context/growth_focus |
| `free_goal` | long_text | free-text → AI extraction input |

The repeatable objective/project inputs collect minimal fields; the rest are filled later in-app or
by the assistant.

---

## 8. Frontend

Stack and conventions per `tech.md`. Routing shell in `App.tsx`: unauthenticated → `/login`
`/register`; authenticated but `!completed` → `/onboarding`; else the nav shell with the routes in
REQ-21.

- `lib/api.ts` — Axios instance, `Authorization` header from in-memory access token, response
  interceptor doing one `/auth/refresh` + retry on `401`, redirect to `/login` on refresh failure
  (REQ-22).
- `lib/sse.ts` — `streamChat(conversationId, text, handlers)` using `fetch` with the auth header and
  a `ReadableStream` reader that parses `event:`/`data:` frames and dispatches to
  `handlers.onToken/onThinking/onTool/onMessage/onError/onDone`.
- `pages/Chat.tsx` — three-pane layout; optimistic user bubble; assistant bubble appends `token`
  deltas; `tool` events render as chips within the assistant bubble; right sidebar polls
  `/dashboard/focus` + `/objectives?status=active` + `/projects?status=active` + `/context/review`
  on mount and after each completed turn.
- `pages/Context.tsx` — tabs: Entries (category-grouped, inline edit/archive), Review
  (`/context/review` with approve/edit-approve/discard), Style (guide textarea + samples list).
- `pages/Objectives.tsx`, `pages/Projects.tsx` — list + detail drawer/route; forms.
- `pages/Dashboard.tsx` — focus card (+ refresh), objective-progress bars (`dataviz` palette),
  momentum stat tiles, "what changed this week" list.
- `pages/Settings.tsx` — email (read-only), model toggle (`PUT` a user setting — store as a
  `context_entries` `misc/chat_model`? No: add a tiny `user_settings` concern OR reuse env default
  and a `misc` entry. **Decision:** a `misc/chat_model` context entry, read by `llm_client` per
  turn, overriding `CHAT_MODEL` when present and valid), logout.

> Amendment to the brainstorm: the model toggle persists as a `context_entries` row
> (`category='misc'`, `key='chat_model'`), not a new table. `llm_client` reads it per turn.

---

## 9. Error handling summary

| Situation | Response |
|---|---|
| Unauthed request to protected route | `401` |
| Account locked | `423` |
| Validation failure | `422` with Pydantic detail |
| Cross-user id in a path/param/tool arg | `404` (do not confirm existence) |
| `project_id` not owned on objective write | `422` |
| AI route with no key | `503 {"detail": "AI features not configured"}` |
| Tool raises inside the loop | `is_error: true` to model; `tool` error SSE event; loop continues |
| Claude API error / refusal | `error` SSE event; user message persisted; stream ends |
| 12-cycle cap hit | stop; emit produced text + a `tool` cap notice; persist normally |

---

## 10. Testing strategy

Per `tech.md` conventions. Anthropic access goes through `services/llm_client.py`, which the test
suite replaces with a stub exposing:
- `available() -> True`
- a fake `tool_runner` that, given a scripted plan, emits a known sequence of text deltas + one tool
  call + a final message, so `chat_agent.run_turn` can be asserted end-to-end without network.

**Unit** — `security` helpers; `context_assembly.build_system` (ordering; `proposed`/`archived`
excluded; byte-stability across two calls with no data change; style guide omitted when empty); each
agent tool (user scoping, `status`/`source` defaults, ownership checks); dashboard aggregation math.

**Integration** (`httpx.AsyncClient`) — register→login→refresh→logout; `/onboarding/submit` with the
stub reporting `available()=False` (enrichment `skipped`) and `=True` (enrichment `done`, proposed
entries created); one chat turn that triggers `upsert_context_entry` and asserts (a) the SSE event
order, (b) exactly the expected `messages` rows with well-formed `blocks_json`, (c) the proposed
entry is absent from a subsequent `build_system`; `/dashboard` figures from seeded rows;
`/dashboard/focus/refresh` → `503` when `available()=False`.

---

## 11. Deviations & amendments from the brainstorm

1. `context_entries.status` gains `proposed` (agent-created entries; confirmed via the review queue).
2. Chat-model preference persists as a `misc/chat_model` context entry, not a new table.
3. `get_context` surfaces `proposed` entries to the model (flagged) so it knows what it already
   suggested, even though assembly excludes them.
4. **Chat turn is not per-token streamed (M5).** The Python Tool Runner's streaming iteration API is
   thinly documented and cannot be live-tested in this environment, so `chat_agent.run_turn` uses the
   documented non-streaming iteration (`async for message in runner` + `generate_tool_call_response()`).
   `tool` events are still emitted live between model turns; assistant **text** is delivered as
   `token` chunks once the turn completes. The SSE event contract is unchanged. Restoring true
   per-token streaming (switch the runner to `stream=True` and consume its per-turn event streams) is
   a self-contained later change.
5. **`utcnow_iso()` is microsecond precision.** Multiple rows are written in one request (a chat turn
   persists 3–4 `messages` rows); second-precision timestamps made them unsortable since ids are
   random UUIDs. All row timestamps now carry `.%f`.
6. `llm_client` was created in M4 (onboarding enrichment needed it), not M5.
7. **Provider switched: Anthropic Claude API → OpenAI-compatible API, default Groq (post-M7).**
   Reason: keep running cost at ~$0. Consequences across this doc:
   - `llm_client` is built on the `openai` SDK with `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
     (default `https://api.groq.com/openai/v1` + `llama-3.3-70b-versatile`). `ANTHROPIC_API_KEY` /
     `CHAT_MODEL` no longer exist. The feature flag is `LLM_API_KEY`.
   - The Tool Runner is gone. `chat_agent.run_turn` is a **manual loop** over
     `llm_client.create_chat`: request → for each `tool_calls` entry call `agent_tools.dispatch`
     → append `{"role":"tool","tool_call_id":...,"content":<json>}` → repeat, cap 12.
   - `agent_tools`: the 13 `_impl_*` functions are unchanged; `build_toolset` is replaced by
     `TOOL_SPECS` (OpenAI function schemas) + `dispatch(user_id, name, args)`.
   - `context_assembly.build_system` returns a **plain string** (stable prefix + a trailing
     `Current time:` line); no `cache_control` blocks — OpenAI/Groq cache prefixes automatically.
     `build_stable_prefix` is the byte-stable part (REQ-11/25 verified against it).
   - `messages.blocks_json` stores one **OpenAI-format message dict** per row (not a list of Anthropic
     content blocks); `role` is `user` / `assistant` / `tool`. The transcript endpoint
     (`GET /chat/conversations/{id}/messages`) returns only `user`/`assistant` rows with visible
     text; `_rebuild_messages` replays all rows (stripping any `reasoning*` keys).
   - Refusal handling keys off `finish_reason == "content_filter"` instead of `stop_reason ==
     "refusal"`.
   - Settings model toggle is now free-text-ish (`misc/chat_model` accepts any non-empty string;
     validity is provider-dependent) rather than a fixed sonnet/opus choice.
   - Tests: the `FakeRunner` became a scripted fake `create_chat` returning OpenAI-shaped
     completions.

Sections 1–10 above describe the original Anthropic design; where they conflict with item 7, item 7
wins. Everything else follows the approved brainstorming sections 1–5.
