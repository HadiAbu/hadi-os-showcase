# Product — hadi-os

## What it is

A personal assistant system — a "Jarvis" — that the owner talks to (chat now, voice later) and that
holds deep, persistent context about who he is, what he is trying to achieve, and what he is working
on. Its centre of gravity is **his software projects and his growth as an engineer**: it tracks
objectives, surfaces what to focus on, and answers in his own writing style.

It is a single-user system. Local-first (runs on his machine via Docker Compose), structured so a
web deployment can be added later without rework.

## Who it is for

One person: the repo owner. Real authentication exists from day one (so a later web deploy is safe),
but there is no multi-tenant, billing, team, or sharing dimension — and none is planned.

## Why it exists

The owner lives in the terminal across many repos and wants one place that:

- knows his goals and active projects without being re-briefed every time,
- tells him what to focus on rather than waiting to be asked,
- can be extended over time with new tools, automations, and integrations,
- responds in his voice, so drafted text needs little editing.

## Principles

- **Context is the product.** The assistant's value is proportional to how well it knows the owner.
  Every feature either feeds the context store or consumes it.
- **The owner stays in control of what is remembered.** The assistant *proposes* additions to its
  knowledge of him; he confirms them. It does not silently rewrite its picture of who he is.
- **Deterministic where it can be, LLM where it must be.** CRUD, aggregation, and gating are plain
  code. The model is used for conversation, extraction, and recommendations — not for things a query
  can answer.
- **Graceful degradation.** With only a database configured, everything except the AI features
  works. The AI layer is a feature flag, not a hard dependency.
- **Small, well-bounded modules.** Each service does one thing and is testable on its own.
- **Ship a usable slice, then extend.** Each phase is independently usable; Phase 1 is the real
  commitment.

## What it is not

- Not `balance-app` (a separate five-category life-balance coach in the sibling workspace). Different
  purpose, no shared code, no dependency.
- Not a habit tracker with streaks.
- Not a multi-user product.
- Not a coding agent — it reasons about the owner's projects from what he tells it (and, from
  Phase 2, from read-only git signals), it does not write their code.

## Phase map

| Phase | Theme | Outcome |
|---|---|---|
| **1 — Chat core** | Context-aware conversation | Talk to it; it answers with real knowledge of the owner's objectives, projects, and voice. Objectives/projects/context are managed in-app and by the assistant (with a confirm gate on context). A dashboard shows objective progress, momentum, and a cached "focus now". |
| **2 — Proactive layer** | It comes to you | "What to focus on" recommendations from objective/project state; daily + weekly generated briefings; a scheduled-jobs framework; live read-only git integration enriching projects with real activity. |
| **3 — Automations & integrations** | It acts for you | Send email on the owner's behalf (with approval gates + an audit trail); weekly calendar/event reminders; exam-prep workflows; MCP tool integration. |
| **4 — Voice & expansion** | Hands-free | Voice input/output; whatever features have proven worth building by then. |

Detail and cross-phase notes: `.kiro/specs/roadmap.md`. Each phase gets its own
`.kiro/specs/phase-N-*/` spec folder when it is started.
