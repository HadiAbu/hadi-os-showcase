# hadi-os — CLAUDE.md

Personal assistant system ("Jarvis") centered on the owner's software projects and growth as an engineer.

**Before working in this repo, read the steering files — they are the durable project context:**

- `.kiro/steering/product.md` — what hadi-os is, the vision, the 4-phase map
- `.kiro/steering/tech.md` — stack, conventions, security posture, env vars, external deps
- `.kiro/steering/structure.md` — repo layout, module boundaries, naming rules
- `.kiro/steering/design.md` — visual direction + the Turso colour palette (applies from Phase 2)

**Active work:** `.kiro/specs/phase-1-chat-core/` — `requirements.md` (EARS acceptance criteria), `design.md` (full design + DDL), `tasks.md` (implementation plan). Later phases get their own `.kiro/specs/phase-N-*/` folder when reached; `.kiro/specs/roadmap.md` is the overview.

**Development method:** spec-driven. Requirements → design → tasks, each committed before code. Tasks cite the requirement IDs they satisfy. TDD for backend logic.

This is not `balance-app` (a separate life-balance coach in the sibling workspace). No shared code.

**LLM:** OpenAI-compatible API, provider-agnostic, default **Groq** (free tier). Env: `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`. Not Anthropic (cost). See `.kiro/steering/tech.md` § LLM configuration.

