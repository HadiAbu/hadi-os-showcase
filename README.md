# hadi-os

A personal assistant system — a "Jarvis" for one's own software projects and growth as an
engineer. It holds persistent context about goals, active projects, and working style, and
answers in the owner's own voice.

> This is a public showcase build seeded with fake demo data. Nothing here is real personal
> information.

## What it does

- **Chat core** — talk to the assistant; it answers with real knowledge of your objectives,
  projects, and writing style, and can create/update objectives, projects, and context entries
  on your behalf through tool calls.
- **Dashboard** — objective progress, momentum, and a cached "focus now" recommendation.
- **Knowledge graph** — objectives, projects, journal entries, conversations, and context
  entries rendered as a connected graph (2D/3D), built from real relationships and touch history.
- **Journal & reflections** — freeform journaling with mood/tags, and generated reflections
  (momentum, drift, recurring themes) computed from journal + objective signals.
- **Usage** — token/cost/tool-call aggregates per time window.

## Tech stack

**Backend:** Python 3.12, FastAPI, Turso (libSQL) via `libsql-client`, JWT auth (`python-jose` +
`bcrypt`), an OpenAI-compatible LLM client (provider-agnostic — default Groq, free tier).

**Frontend:** React 19, Vite, TypeScript, Tailwind CSS 4, React Router v7, shadcn/ui,
`react-force-graph` for the knowledge graph.

**Infra:** Docker Compose (`api` + `web` + `nginx`), no local database container — points at a
real Turso database even in dev.

## Architecture

- `backend/app/api/routes/*` — thin HTTP layer: validate, call a service, shape the response.
- `backend/app/services/*` — business logic (context assembly, the chat tool-call loop, the
  knowledge graph builder, journal/reflection generation).
- `backend/app/db/migrations.py` — the schema, as idempotent DDL, applied on every boot.
- `frontend/src/pages/*` + `frontend/src/components/<feature>/` — one page per feature area.

See `.kiro/steering/` for the full architecture and conventions this project was built against,
and `.kiro/specs/` for the phase-by-phase requirements/design/task history.

## Run it yourself

**Prerequisites:**
- A free [Turso](https://turso.tech) database (`TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN`).
- Optionally, a free [Groq](https://console.groq.com) API key to enable chat/AI features — the
  app runs fully without one; AI-only endpoints just return `503` and everything else (auth,
  dashboard, objectives/projects/journal CRUD, the graph, templated reflections) works.

```bash
cp backend/.env.example backend/.env    # fill in TURSO_* (and LLM_API_KEY if you want AI features)
cp frontend/.env.example frontend/.env
docker compose up --build
```

Seed it with demo data:

```bash
docker compose exec api python -m app.scripts.seed_demo
```

Then open http://localhost:8080 and log in with:

- **Email:** `demo@example.com`
- **Password:** `DemoPass123`

## Screenshots

_(placeholder — add screenshots of the dashboard, chat, and knowledge graph here)_

## License

MIT — see `LICENSE`.
