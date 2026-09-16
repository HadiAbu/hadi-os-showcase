# Tech — hadi-os

The stack mirrors the sibling `balance-app` / `aiphilosophy` projects — a proven, secure pattern the
owner already knows. Deviations from that pattern are called out explicitly below.

## Stack

### Backend
- Python 3.12, FastAPI 0.115+
- `libsql-client` — Turso HTTP client. **Force the `https://` URL scheme** (WebSocket transport on
  `libsql://` is unreliable — same decision as the sibling projects).
- `python-jose` (JWT), `bcrypt` (used directly, not via passlib)
- `pydantic-settings` for env config; Pydantic v2 models on every request/response body
- `openai` — used as an **OpenAI-compatible client**, pointed at any provider via `LLM_BASE_URL`.
  Chat drives a **hand-written tool-call loop** (there is no provider-specific tool runner).
- `httpx` for any outbound HTTP

### Frontend
- React 19 + Vite + TypeScript, Tailwind CSS 4, React Router v7, Axios
- `AuthContext` / `AuthProvider` split into separate files (Fast Refresh requires it — a context
  object and its provider component cannot share a file)
- **Design system (Phase 2):** shadcn/ui "new-york" primitives in `components/ui/` (generated,
  kept in-repo), themed from the Turso palette. Tailwind 4 is CSS-first — all tokens live in
  `src/index.css` (`:root` raw palette + graph node colours + the shadcn token contract;
  `@theme inline` exposes them as utilities). No `tailwind.config`. `@/*` path alias in
  `tsconfig` + `vite.config`. `cn()` in `lib/utils.ts`.
- **Knowledge graph:** `react-force-graph-2d` (+ `-3d` behind a toggle, pulling `three`) and
  `d3-force` for the reduced-motion static layout. Both graph renderers are `React.lazy`
  code-split (`components/graph/GraphCanvasLazy` → `GraphCanvas`; `three` splits again behind
  `GraphCanvas3D`) so nothing graph-related enters the main bundle.
- Dashboard / Usage visualisations are hand-rolled inline SVG (`components/charts/`), single aqua
  hue — no chart library.
- Chat streaming via a small `lib/sse.ts` fetch-stream reader (not `EventSource` — the request is a
  `POST` with an auth header)
- `lib/api.ts` coalesces concurrent token refreshes onto one in-flight `/auth/refresh` promise —
  the `AuthProvider` cold-load bootstrap and the 401 interceptor both call `refreshAccessToken()`,
  and refresh tokens are single-use, so a second racing call would 401 and drop the session.

### Infra (local only in Phase 1 — structure, not deployment)
- Docker Compose: `api` + `web` + `nginx`. No local database container — points at a real Turso
  database even in dev, same as the sibling projects.
- `nginx/nginx.conf` is a **dev-only** reverse proxy + rate limiter and the sole host port (8080).
  `auth_zone` on `/api/auth`, `api_zone` on general `/api`. `api`/`web` only `expose` internally so
  rate limiting cannot be bypassed. This is not the production nginx (no TLS/domain) — production
  deploy is deferred and not designed here.

## LLM configuration

- **Provider-agnostic — any OpenAI-compatible chat API.** Set via three env vars: `LLM_API_KEY`,
  `LLM_BASE_URL`, `LLM_MODEL`. This was chosen over the Anthropic API to keep running costs at (or
  near) zero.
- **Default: Groq** — `LLM_BASE_URL=https://api.groq.com/openai/v1`,
  `LLM_MODEL=openai/gpt-oss-120b`. Groq's free tier has rate limits but no charge. A `gsk_...`
  key comes from https://console.groq.com.
- **Switching providers is env-only** for standard chat-completions models: OpenAI
  (`LLM_BASE_URL=https://api.openai.com/v1`, `LLM_MODEL=gpt-4o-mini`), a local Ollama
  (`http://host.docker.internal:11434/v1`), OpenRouter, Together, etc. OpenAI's *reasoning* models
  (`o1`/`o3`/`gpt-5`…) are **not** drop-in — they reject `max_tokens` (need `max_completion_tokens`)
  and would need a small `llm_client.create_chat` change.
- Per-user override: a `misc/chat_model` context entry (set from the Settings screen) overrides
  `LLM_MODEL` for that user's turns. Any non-empty string is accepted — validity depends on the
  provider.
- **Chat turn:** `chat_agent.run_turn` is a manual loop over `llm_client.create_chat` — request →
  run tool calls (`agent_tools.dispatch`) → append `{"role":"tool", ...}` results → repeat, capped
  at **12 tool cycles**. Not per-token streamed: the model's text is delivered as end-of-turn
  `token` chunks over the SSE contract (a later refinement can switch `create_chat` to `stream=True`).
- Prompt-prefix caching is automatic on OpenAI and Groq — no `cache_control` parameter. The
  `context_assembly` stable prefix is still kept byte-stable so that caching engages.
- The client is constructed with a 90s timeout + 1 retry. `create_chat` sends `max_tokens=8192`
  and a `finish_reason == "length"` (truncated) turn emits a `(truncated)` notice. Per-turn token
  usage (summed across tool cycles) is stored on the final assistant row's `messages.usage_json`.

## Environment variables

| Var | Required | Purpose |
|---|---|---|
| `TURSO_DATABASE_URL` | yes | Turso DB, `https://` scheme |
| `TURSO_AUTH_TOKEN` | yes | Turso auth |
| `JWT_SECRET_KEY` | yes | HS256 signing key for access tokens |
| `TOKEN_ENCRYPTION_KEY` | later | Fernet key for encrypting third-party tokens at rest (Phase 3; unused in Phase 1) |
| `LLM_API_KEY` | no (feature-flagged) | Enables chat, onboarding AI extraction, and dashboard "focus now". Absent ⇒ those endpoints return `503`; everything else works. |
| `LLM_BASE_URL` | no | OpenAI-compatible endpoint. Default `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | no | Default `openai/gpt-oss-120b` (Groq) |
| `CORS_ORIGINS` | yes | Explicit allowed origins, comma-separated |
| `ENVIRONMENT` | no | `dev` (default) / `prod` — gates HSTS header |

`.env` is gitignored; `backend/.env.example` and `frontend/.env.example` are the templates.

## Security posture (non-negotiable — copied from `aiphilosophy`, do not weaken)

| Requirement | Implementation |
|---|---|
| Passwords | `bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12))`; server-side strength check (8–72 chars, ≥1 uppercase, ≥1 digit) in the register schema |
| Login lockout | 5 failed attempts ⇒ account locked 15 min (`users.failed_attempts` / `locked_until`); reset on success |
| Access tokens | HS256 JWT, 15-min expiry, `type: "access"` claim verified on decode |
| Refresh tokens | UUID v4 raw value in an HttpOnly + `SameSite=Strict` cookie; SHA-256 hash stored in DB; rotated every refresh; that user's expired/revoked rows deleted on every login/refresh |
| SQL | parameterised only |
| Input validation | Pydantic on every request body |
| CORS | explicit origins only; no methods a route does not need |
| Security headers | pure ASGI middleware — CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy; HSTS only when `ENVIRONMENT=prod` |
| Secrets | `LLM_API_KEY` and any future third-party tokens are never logged and never sent to the frontend |
| Agent tools | `user_id` is bound by `chat_agent` from the authenticated session and passed to `agent_tools.dispatch` / every `_impl_*`, **never** taken from model-supplied arguments; every tool query is scoped by `user_id` |

## Conventions

- IDs: `TEXT` UUID v4.
- Timestamps: `TEXT` ISO-8601 UTC (e.g. `2026-09-07T14:03:00Z`).
- "JSON" columns: `TEXT` holding a JSON string; parse/serialise at the service boundary.
- Schema: created by `run_migrations()` in the FastAPI lifespan on startup. Idempotent
  `CREATE TABLE IF NOT EXISTS` + additive migrations. No separate migration command.
- Question banks / catalogs (onboarding questions, base system prompt) live in Python modules, not DB
  tables, so copy changes need no migration.
- Tests: `backend/tests/conftest.py` wires an in-memory SQLite DB with the real schema and patches
  the Turso `db_execute` helper everywhere it is imported, so tests never hit the network.
  `tests/unit/` for pure logic (context assembly, security helpers, EARS-critical branching);
  `tests/integration/` drives the app through `httpx.AsyncClient`. Run locally before pushing; no CI
  in Phase 1.
- Frontend: `lib/api.ts` owns the Axios instance + refresh interceptor. Feature code lives in
  `pages/<Feature>.tsx` + `components/<feature>/`.

## Telemetry & knowledge graph (Phase 2)

- **`tool_invocations`** — one row per tool call taken in a chat turn, written by
  `services/tool_log.record_invocations` on the success persist path only (nothing on
  refusal/error). `args`/`result` truncated to 4 KB. `tool_log.touches_from` derives
  `(entity_type, entity_id)` from successful create/update/add_action results for the graph.
- **`entity_links`** — user-drawn edges between any two entities; natural-key `UNIQUE`.
  `services/graph_links` CRUD, both endpoints ownership-checked → 422.
- **`services/graph.build_graph(user_id)`** — five node queries + six link rules
  (`has_action`, `for_project`, `context_of`, `touched`, explicit), dedup, drop dangling links,
  cap at `NODE_CAP` (250) with a `truncated` flag. `GET /api/graph`, `/api/graph/links`.
- **`services/usage.usage(user_id, window)`** — aggregates `messages.usage_json` +
  `tool_invocations`. The per-model cost-estimate rate table (`RATES`, USD per 1M in/out;
  Groq models are 0) lives at the top of `services/usage.py`; `cost_known` is false when any
  model in the window is absent from it. `GET /api/usage?window=7d|30d|all`.
- **`services/context_stats.stats(user_id)`** — `by_status` / `by_category` / 30-day `growth` /
  `stale` (active, `updated_at` > 45d). `GET /api/context/stats`.
- All four are pure reads (no LLM) and work with `LLM_API_KEY` unset.

## Journal & reflections (Phase 2.5)

- **`journal_entries`** — freeform entries (`title` optional, `body` substantive, `mood` enum,
  `tags`, optional `linked_objective_id` / `linked_project_id`, `learn_from_style`). CRUD in
  `services/journal_store`; a foreign link id → `LinkNotOwned` → 422.
- **Style capture:** on save, an entry ≥ 200 chars with `learn_from_style` set is mirrored into
  `style_samples` under the label `journal:<id>` (`services/style.upsert_labelled_sample` /
  `delete_labelled_sample`) — editing replaces it, shortening / opting out / deleting removes it.
  So the writing-style guide tracks what the owner actually journals.
- **`POST /api/journal/{id}/continue`** — `llm_client.one_shot` with the style guide + the 3 most
  recent other entries as voice reference; 1–2 paragraphs, nothing persisted. `503` with no key.
- **`journal` graph node** — one per entry with a body; `mentions` edges to its linked
  objective / project. New colour token `--node-jrnl`.
- **`services/insights`** — `compute_signals(user_id)` is pure SQL + Python: `momentum` (actions
  done per objective 30/60d + a 21-day `stalled` flag), `drift` (an objective mentioned in ≥ 2
  recent journal entries with zero action progress), `themes` (top stopword-filtered 1-/2-grams
  over recent bodies with a prior-window count; stopword list in `services/_stopwords.py`).
  `generate(user_id)` turns a signal set into 3–5 stored `reflections` rows — one
  `llm_client.extract_json` call for voiced bodies when a key is set, a templated body per
  non-empty signal group otherwise (or on a parse failure). `evidence_json` always carries the
  real source ids. `GET/PATCH /api/reflections`, `POST /api/reflections/generate`. Nothing here
  needs `LLM_API_KEY`.
- **Known follow-up:** the reflection *voice* path depends on the model returning the requested
  JSON; with `gpt-oss-120b` it currently often falls back to the templated bodies. Prompt / JSON-
  mode tuning (or a `response_format` option on `llm_client`) is a Phase-3 refinement — the
  fallback is correct and covered by tests.

## Feature flags / graceful degradation

| Missing config | Behaviour |
|---|---|
| `LLM_API_KEY` unset | `POST /api/chat/**`, onboarding AI extraction, `POST /api/dashboard/focus/refresh`, and `POST /api/journal/{id}/continue` return `503 {"detail": "AI features not configured"}`. Everything else works: auth, onboarding (structured steps), all CRUD, dashboard aggregation, the last cached focus snapshot, the Phase-2 graph/usage/context-stats endpoints, journal CRUD, and reflection generation (templated bodies). |

## External dependencies

- **An OpenAI-compatible LLM endpoint** (default Groq) — the only external service in Phase 1.
- Turso — the database (not "external" in the integration sense; always required).
- Google (Calendar/Gmail), MCP servers, voice providers — Phases 2–4, not now.
