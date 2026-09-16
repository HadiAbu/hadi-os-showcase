# Structure — hadi-os

## Repo layout

```
hadi-os/
├── .kiro/
│   ├── steering/                    # durable project context — read before working here
│   │   ├── product.md
│   │   ├── tech.md
│   │   └── structure.md
│   └── specs/
│       ├── roadmap.md               # 4-phase overview
│       ├── phase-1-chat-core/
│       │   ├── requirements.md
│       │   ├── design.md
│       │   └── tasks.md
│       ├── phase-2-visual-and-graph/  # visual identity + knowledge graph + telemetry
│       │   ├── requirements.md
│       │   ├── design.md
│       │   └── tasks.md
│       └── phase-2.5-journal-and-reflections/
│           ├── requirements.md
│           ├── design.md
│           └── tasks.md
├── CLAUDE.md                        # thin pointer to the steering files
├── backend/
│   ├── app/
│   │   ├── api/routes/              # one module per feature area; thin — validation + service calls
│   │   │   ├── auth.py
│   │   │   ├── onboarding.py
│   │   │   ├── chat.py
│   │   │   ├── context.py           # + GET /context/stats (Phase 2)
│   │   │   ├── objectives.py
│   │   │   ├── projects.py
│   │   │   ├── dashboard.py
│   │   │   ├── graph.py             # GET /graph, /graph/links CRUD (Phase 2)
│   │   │   ├── usage.py             # GET /usage?window= (Phase 2)
│   │   │   ├── journal.py           # /journal CRUD + /{id}/continue (Phase 2.5)
│   │   │   └── reflections.py       # /reflections generate / GET / PATCH (Phase 2.5)
│   │   ├── core/
│   │   │   ├── config.py            # pydantic-settings Settings
│   │   │   ├── security.py          # hashing, JWT, refresh-token helpers
│   │   │   └── deps.py              # current_user() dependency
│   │   ├── db/
│   │   │   ├── client.py            # Turso client + db_execute helper
│   │   │   └── migrations.py        # run_migrations(), idempotent DDL
│   │   ├── models/                  # Pydantic request/response schemas, one module per feature
│   │   ├── services/
│   │   │   ├── context_assembly.py  # builds the 2-block system prompt
│   │   │   ├── chat_agent.py        # manual tool-call loop, SSE bridge, turn persistence
│   │   │   ├── agent_tools.py       # @beta_tool functions (read/write the owner's records)
│   │   │   ├── tool_log.py          # tool_invocations writer + entity-touch derivation (Phase 2)
│   │   │   ├── graph.py             # build_graph(user_id) — nodes/links assembly (Phase 2)
│   │   │   ├── graph_links.py       # entity_links CRUD, ownership-checked (Phase 2)
│   │   │   ├── usage.py             # usage(user_id, window) + RATES cost table (Phase 2)
│   │   │   ├── context_stats.py     # context store counts / growth / staleness (Phase 2)
│   │   │   ├── journal_store.py     # journal_entries CRUD + style-sample sync (Phase 2.5)
│   │   │   ├── insights.py          # compute_signals + generate reflections (Phase 2.5)
│   │   │   ├── _stopwords.py        # stopword set for insights theme extraction
│   │   │   ├── onboarding_questions.py  # the fixed question bank
│   │   │   ├── focus.py             # cached "focus now" generation
│   │   │   ├── style.py             # style-guide read/update
│   │   │   └── llm_client.py        # thin OpenAI-compatible wrapper (client, model, base_url)
│   │   └── main.py                  # app factory + lifespan (run_migrations)
│   ├── tests/
│   │   ├── conftest.py              # in-memory SQLite fixture; patches db_execute
│   │   ├── unit/
│   │   └── integration/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt         # pytest, pytest-asyncio, aiosqlite — not in the prod image
│   ├── pytest.ini
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/              # components/<feature>/… + ui/ (shadcn primitives)
│   │   │   ├── ui/                  # generated shadcn/ui primitives, themed from tokens
│   │   │   ├── graph/               # GraphCanvas(+Lazy/+3D), GraphPanel, GraphModeToggle
│   │   │   ├── charts/              # Sparkline, BarChart (inline SVG, no chart lib)
│   │   │   ├── usage/               # UsageCard (dashboard)
│   │   │   ├── journal/             # JournalEditor, MoodChips (Phase 2.5)
│   │   │   ├── reflections/         # ReflectionCard, ReflectionTeaser (Phase 2.5)
│   │   │   └── NavRail.tsx, AuthShell.tsx
│   │   ├── contexts/               # AuthContext.tsx, AuthProvider.tsx (separate files)
│   │   ├── hooks/                   # useAuth.ts, …
│   │   ├── lib/                     # api.ts (Axios + single-flight refresh), sse.ts,
│   │   │                           #   utils.ts (cn), graph.ts, usage.ts, useReducedMotion.ts
│   │   ├── pages/                   # Login, Register, Onboarding, Chat, Dashboard, Journal,
│   │   │                           #   Objectives, Projects, Context, Graph, Usage,
│   │   │                           #   Reflections, Settings, Styleguide
│   │   ├── index.css               # Tailwind 4 CSS-first — all design tokens live here
│   │   ├── App.tsx                  # router + nav shell
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── package.json
│   └── .env.example
├── nginx/
│   └── nginx.conf                   # dev-only reverse proxy + rate limiting; sole host port
├── docker-compose.yml
└── .gitignore
```

## Module boundaries (one purpose each)

| Module | Does | Depends on | Does not |
|---|---|---|---|
| `api/routes/*` | HTTP: parse + validate request, call a service, shape the response. No business logic. | `models/`, `services/`, `core/deps` | touch the DB directly, call the LLM directly |
| `core/security` | password hashing, JWT encode/decode, refresh-token hash/rotate | — | know about routes or business objects |
| `core/deps` | `current_user()` — resolve + verify the access token → user row | `core/security`, `db` | — |
| `db/client` | Turso connection + `db_execute(sql, params)` | — | know any table's shape |
| `db/migrations` | the schema, as idempotent DDL | `db/client` | — |
| `services/context_assembly` | turn the owner's stored context + objectives + projects + style guide into the 2-block system prompt | `db` | call the LLM |
| `services/agent_tools` | the `@beta_tool` functions the model can call; each scoped to one authenticated user | `db`, `services/style` | build prompts, manage the loop |
| `services/chat_agent` | run one chat turn: assemble → manual tool-call loop over `llm_client.create_chat` → SSE events → persist every produced message + one `tool_invocations` row per call on success | `context_assembly`, `agent_tools`, `tool_log`, `llm_client`, `db` | define CRUD endpoints |
| `services/tool_log` | write `tool_invocations` (4 KB-truncated), derive `(entity_type, entity_id)` touches for the graph | `db` | run the loop, call the LLM |
| `services/graph` | `build_graph(user_id)` — assemble nodes/links from live rows + `tool_invocations` + `entity_links`; cap 250 | `db`, `tool_log` | write anything, call the LLM |
| `services/graph_links` | `entity_links` CRUD; verify both endpoints belong to the user | `db` | — |
| `services/usage` | `usage(user_id, window)` — token/cost/tool-call aggregates; owns the `RATES` cost table | `db` | call the LLM |
| `services/context_stats` | context store counts / 30-day growth / 45-day staleness | `db` | call the LLM |
| `services/journal_store` | `journal_entries` CRUD; on write, sync a `journal:<id>` `style_samples` row for long entries | `db`, `objectives_store`, `projects_store`, `style` | build prompts, own the graph |
| `services/insights` | `compute_signals` (momentum/drift/themes, pure) + `generate` (signal set → stored `reflections`, LLM-voiced or templated) + list/status | `db`, `style`, `llm_client` (generate only) | own the schema, drive a loop |
| `services/focus` | generate + cache the "focus now" snapshot from objective/project state | `llm_client`, `db` | — |
| `services/style` | read/derive/update `style_guide` from samples + corrections | `llm_client` (derive only), `db` | — |
| `services/llm_client` | construct the OpenAI-compatible client (key + base_url), pick the model, expose `create_chat` / `one_shot` / `extract_json` | `openai` SDK, `core/config` | know about hadi-os domain objects |

## Naming rules

- Route modules and their `models/` counterpart share a name (`objectives.py` ↔ `models/objectives.py`).
- Service files are `snake_case` nouns describing the thing they own (`context_assembly.py`).
- `@beta_tool` function names are the verb the model sees: `list_objectives`, `upsert_context_entry`,
  `create_project`. Keep them short and unambiguous — they are part of the prompt.
- DB columns: `snake_case`; enums stored as their literal slug (`active`, `proposed`, `archived`);
  boolean columns named `is_*` or a plain adjective (`pinned`, `archived`) stored as `0`/`1`.
- Frontend: pages `PascalCase.tsx`, hooks `useThing.ts`, everything a feature owns under
  `components/<feature>/`.

## Where things go

- A new **agent capability** → a new `@beta_tool` in `agent_tools.py` + its data access; register it in
  the tool list `chat_agent` passes to the runner.
- A new **tracked entity** → a table in `migrations.py`, a `models/` module, a `services/` owner if it
  has logic beyond CRUD, a route module, a page.
- A new **piece of "what the assistant knows"** → almost always a `context_entries` category, not a
  new table. Add a table only when the thing has its own lifecycle and relationships (as objectives
  and projects do).
- A new **phase** → `.kiro/specs/phase-N-<slug>/` with its own `requirements.md` / `design.md` /
  `tasks.md`; update `.kiro/specs/roadmap.md`.
