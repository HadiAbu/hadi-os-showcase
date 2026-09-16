# Design — hadi-os

## Direction

**Dark-first, Turso-inspired.** One bright aqua accent on deep teal-black surfaces.
Calm, dense, instrument-panel feel — this is a tool the owner lives in, not a marketing site.
The current Phase-1 UI is a light utilitarian placeholder; Phase 2 redesigns it on this system.

## Palette (from turso.tech/brand)

| Token | Hex | Role |
|---|---|---|
| `--bg` | `#0D1318` | app background (Turso "Bunker") |
| `--rail` | `#101820` | the left nav rail (one notch below `--bg`) |
| `--surface` | `#162129` | cards, panels ("Mirage") |
| `--surface-raised` | `#183134` | modals, popovers, active rows, hover ("Dark Teal") |
| `--void` | `#0A0F14` | the knowledge-graph field only — "looking into space", darker than `--bg` |
| `--border` | `#293945` | hairlines, dividers ("Pickled Bluewood") |
| `--accent` | `#4FF8D2` | primary buttons, links, focus rings, graph edges ("Turso Aqua") |
| `--accent-hi` | `#7FFCE0` | accent hover (lightened) |
| `--accent-ink` | `#0D1318` | text/icons on an aqua fill |
| `--text` | `#E8F0EF` | primary text (cool near-white) |
| `--text-muted` | `#8FA3A0` | secondary text, labels, section headers, **any interactive or state-bearing text** |
| `--text-faint` | `#5C6E6C` | placeholders and purely decorative separators only — fails AA for content |

Radius scale: cards `12px`, buttons / inputs / small controls `8px`, nav items `9px`, inner
tiles `10px`, pills `999px`. Fonts: **Hanken Grotesk** (UI) + **JetBrains Mono** (numbers, ids,
keys) via Google Fonts, `system-ui` / `ui-monospace` fallbacks.

Semantic:

| Token | Hex | |
|---|---|---|
| `--warn` | `#F5B849` | warnings, "stale", the review badge |
| `--danger` | `#F87171` | destructive, errors |
| `--ok` | `#4FF8D2` | success (reuse the accent) |

Graph node categories (on-brand, distinguishable on the dark bg — see `dataviz` skill before
finalising): objective `#4FF8D2` · project `#7CC7FF` · context `#B7A5FF` · action `#8FE9B0` ·
conversation `#5C6E6C`.

## Rules

- Accent is scarce: primary action per view, links, focus. Never large aqua fills.
- Elevation by surface colour, not shadow (shadows read poorly on near-black).
- `color-scheme: dark`; respect `prefers-reduced-motion` (the 3D graph must degrade to a static
  2D layout).
- Keep the existing information architecture (the nav, the screens) — this is a reskin + polish,
  not a rebuild of flows.

## Tooling (Phase 2 redesign)

- **`design` skill** (Claude Design canvas) — mock the redesigned screens as artboards on this
  palette, tweak visually, then build against the approved canvas.
- **Mobbin MCP** — pull real dashboard / graph-view / chat patterns for reference.
- **shadcn/ui** — adopt for the rebuilt components (Radix primitives + Tailwind, themeable with the
  tokens above). Replaces the hand-rolled Phase-1 components.
- **`react-force-graph-3d`** (three.js) — the knowledge-graph view.
- **`dataviz` skill** — palette/'form for the usage charts and the graph legend.
