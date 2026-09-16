# hadi-os

A personal assistant system — a "Jarvis" — centred on the owner's software
projects and growth as an engineer. Chat interface, deep persistent context
about who the owner is and what they're working toward, and a dashboard that
tracks momentum.

Built spec-driven. The authoritative design lives in `.kiro/`:

- `.kiro/steering/` — `product.md`, `tech.md`, `structure.md`, `design.md` (durable context)
- `.kiro/specs/roadmap.md` — the phase plan
- `.kiro/specs/phase-1-chat-core/` — `requirements.md`, `design.md`, `tasks.md`

**Read `.kiro/steering/*` before working in this repo.**

---

## Design

`.kiro/steering/design.md` holds the visual direction and the Turso-derived colour palette
(applies from Phase 2). The redesign mockups — Dashboard (graph-forward), Chat, Context,
Objectives — live as a Claude Design canvas:

**https://claude.ai/code/artifact/af3e41e5-602d-4d98-ba40-5147c4f9ace3**

Artboard sources: `design/*.dc.html` + `design/canvas.json` (re-seed with the `design` skill's
helper to update the canvas).

---

## Status

**Phase 1 (chat core) — implemented.** Auth, onboarding, context store + review
queue + writing-style guide, two-tier objectives/actions, projects, a
context-aware chat agent (OpenAI-compatible LLM, default Groq's free tier), and a dashboard
with a cached
"focus now" note.

Backend: 109 tests, all passing, no network. Frontend: builds clean.

Not yet exercised end-to-end against a live database + a real LLM key — see
"What's left to verify" below.

---

## Running the stack

### Docker (recommended)

```bash
cp backend/.env.example backend/.env      # fill in TURSO_* and JWT_SECRET_KEY
cp frontend/.env.example frontend/.env
docker compose up --build
```

Everything is served from **http://localhost:8080** (nginx reverse-proxies
`/api/*` to the backend, everything else to the Vite dev server; `api` and `web`
are internal-only so the rate limiter can't be bypassed).

The app boots without `LLM_API_KEY` — chat, onboarding AI enrichment, and
the dashboard "focus now" refresh return `503`; everything else works.

### Without Docker

```bash
# backend
cd backend
python -m venv .venv && ./.venv/Scripts/activate    # or: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                                 # fill in TURSO_* + JWT_SECRET_KEY
uvicorn app.main:app --reload                        # http://localhost:8000

# frontend (separate shell)
cd frontend
npm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env
npm run dev                                          # http://localhost:5173
```

### Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

`tests/conftest.py` swaps Turso for an in-memory SQLite database and stubs the
LLM client, so tests never hit the network. There is no CI yet — run
locally before pushing.

---

## Environment variables

See `.kiro/steering/tech.md` § Environment variables for the full table. The
minimum to run: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `JWT_SECRET_KEY`,
`CORS_ORIGINS`. Add `LLM_API_KEY` (a free Groq key from console.groq.com by default) to
enable the AI features; `LLM_BASE_URL` / `LLM_MODEL` switch providers/models.

---

## Layout

```
backend/    FastAPI + Turso (libSQL). app/api/routes, app/services, app/db, app/core
frontend/   React 19 + Vite + TS + Tailwind 4 + React Router 7
nginx/      dev-only reverse proxy + rate limiting
.kiro/      the spec set (steering + per-phase requirements/design/tasks)
```

Module boundaries and naming rules: `.kiro/steering/structure.md`.

---

## What's left to verify (Phase 1)

Everything below is covered by automated tests but has not been run against real
infrastructure in this environment:

- `docker compose up` end-to-end against a real Turso database
- The chat turn against a real `LLM_API_KEY` (calls a tool,
  proposes a context entry, survives reload + continuation)
- The frontend flows: onboarding → chat → CRUD → dashboard

Design deviations recorded during the build are in
`.kiro/specs/phase-1-chat-core/design.md` § 11 — notably the chat turn is not yet
per-token streamed; assistant text arrives as end-of-turn chunks over the SSE
contract (a later change switches `create_chat` to `stream=True`).

---

## Next phases

`.kiro/specs/roadmap.md`: proactive layer (recommendations, briefings, scheduled
jobs, live git integration), automations & integrations (email, calendar,
exam-prep, MCP), then voice.
