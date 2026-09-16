# Roadmap — hadi-os

Four phases. Each is independently usable. Phase 1 is the real commitment; 2–4 are sketches that
firm up when started. Every phase gets its own `.kiro/specs/phase-N-<slug>/` folder with
`requirements.md` / `design.md` / `tasks.md` before its code is written.

**Status:** Phase 1 ✅ shipped · Phase 2 ✅ shipped (2026-09-08) · Phase 2.5 (journal &
reflections) ✅ shipped (2026-09-08), spec `.kiro/specs/phase-2.5-journal-and-reflections/` ·
Phase 3–4 not started.

---

## Phase 1 — Chat core

**Goal:** talk to hadi-os and have it answer with real knowledge of the owner's objectives,
projects, and writing style — and let both the owner and the assistant maintain that knowledge.

**In scope**
- Auth: register / login / refresh / logout (single user in practice; real auth for later web deploy).
- Onboarding wizard: seeds the context store (identity, working style, writing samples, current
  objectives, current projects, a free-text goal). One optional Claude extraction pass over the
  free-text + samples when `LLM_API_KEY` is set.
- Context store: atomic `context_entries` + a derived writing-style guide. Direct editing in the UI.
- Chat: manual tool-call agentic loop (OpenAI-compatible API, default Groq) over an assembled system prompt;
  a Phase-1 toolset that reads/writes the owner's context, objectives, actions, and projects.
- Conversational learning: the assistant *proposes* new context entries (`status='proposed'`); the
  owner confirms them in a review queue before they enter the prompt.
- Objectives (two-tier: objective + child actions) and Projects (manual records, with unused
  `repo_*` fields) — full CRUD in the UI and via agent tools.
- Dashboard: cached "focus now" panel, objective progress, momentum from timestamps, "what changed
  this week".

**Out of scope (explicitly):** proactive/scheduled anything, real git analysis, email, calendar,
MCP, voice, RAG/embeddings, conversation compaction, tool-approval gates, multi-user.

**Outcome:** a daily-usable assistant that already knows the owner.

---

## Phase 2 — Visual identity + knowledge graph + telemetry

**Goal:** it looks like the tool it is, and it shows the owner how their work connects and what it costs.
Spec: `.kiro/specs/phase-2-visual-and-graph/`.

1. **UI/UX redesign on the Turso palette** *(first — everything else is built on it)*. Dark-first,
   one aqua accent; tokens and rules in `.kiro/steering/design.md`; mockups on the design canvas
   (link in `README.md`). Same information architecture; new component layer (shadcn/ui). `frontend/`
   moves from hand-rolled light Tailwind to the token system.
2. **Knowledge graph — a "brain" view.** `GET /api/graph` returns nodes (objectives, actions,
   projects, active context entries, conversations) and edges (objective→action, objective↔project
   via `project_id`, context→objective/project by category/tag, conversation→entities it touched,
   plus explicit links from a small `entity_links` table). Rendered with `react-force-graph`
   (three.js): glowing aqua edges on the dark field, nodes coloured by type. Graph-forward panel on
   the Dashboard + a fullscreen route; degrades to a static 2D layout under `prefers-reduced-motion`.
3. **Usage & context telemetry.** `GET /api/usage` aggregates `messages.usage_json` (captured per
   turn since Phase 1) + a new `tool_invocations` table: tokens per day / conversation / model,
   estimated cost from a per-model rate table (Groq free = $0, tracked for when the provider
   changes), tool-call counts. `GET /api/context/stats`: active/proposed/archived counts, growth,
   stale entries. Dashboard panel + a `/usage` route (`dataviz` skill for the charts).

**Depends on Phase 1:** objectives/projects schema, context assembly, `messages.usage_json`.

---

## Phase 3 — Proactive layer + automations

**Goal:** it comes to the owner, and acts on their behalf — safely.

**Proactive:**
- "What to focus on" as a first-class, always-current recommendation (not just an on-demand call):
  ranked from objective priority/horizon, staleness, and momentum.
- Daily briefing + weekly review: generated documents, viewable and stored, with a nudge when due.
- **Scheduled-jobs framework** — a job registry, a runner, run history; the substrate the automations
  below plug into. Lightweight in-process scheduler or a cron-invoked management command; decide at
  spec time.
- **Live git integration** for projects: a read-only scanner over `repo_path`/`repo_url` (commit
  cadence, languages, recent changes) that enriches project records and feeds momentum, focus, and
  the graph. No writes to the owner's repos.

**Automations & integrations:**

- **Send email** for the owner (draft in his style, he approves, it sends). Per-tool **approval
  gates** inside `agent_tools.dispatch`; the `tool_invocations` table (created in Phase 2 for
  telemetry) is reused here for the audit trail.
- Weekly calendar/event reminders (Google Calendar read; keyword→context categorisation).
- Exam-prep workflows: track upcoming exams, generate study plans and practice material, schedule
  review sessions.
- **MCP tool integration**: connect external MCP servers so their tools are available in chat
  (`mcp_toolset` + the MCP client beta).
- Third-party tokens encrypted at rest with Fernet (`TOKEN_ENCRYPTION_KEY`), server-side only.

**Depends on Phase 2:** the redesigned component layer, `tool_invocations`, the graph model.

---

## Phase 4 — Voice & expansion

**Goal:** hands-free.

- Voice input (speech-to-text) and output (text-to-speech) over the existing chat loop.
- Push/desktop notifications for reminders and briefings.
- Whatever has earned its place by then — the feature list is deliberately open.

**Depends on Phase 3:** a stable tool/automation surface worth driving by voice.

---

## Cross-phase notes

- The context store is the spine. Prefer a new `context_entries` category over a new table unless the
  thing has its own lifecycle.
- The agent toolset only ever grows; each capability is one `@beta_tool` + its data access.
- Risky tools (anything outward-facing or irreversible) require an approval gate and an audit row
  (`tool_invocations`, created in Phase 2) — mandatory from Phase 3 on.
- The LLM layer is OpenAI-compatible and provider-agnostic (default Groq). Switching providers is
  three env vars (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`), no code change.
