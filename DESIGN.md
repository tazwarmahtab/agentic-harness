# Design System — AOS (Agentic Operating System)

## Product Context
- **What this is:** Governance-first, multi-venture agentic operating system. Orchestrates autonomous business systems for a solo founder running multiple companies.
- **Who it's for:** Solo founders and operators running multiple ventures through AI agents.
- **Space/industry:** AI agent infrastructure, agentic orchestration, developer tools.
- **Project type:** CLI + FastAPI web dashboard + documentation.

## Aesthetic Direction
- **Direction:** Industrial/Utilitarian
- **Decoration level:** Minimal — typography and data do all the work.
- **Mood:** Serious infrastructure for serious work. Bloomberg Terminal meets GitHub. Not a SaaS marketing site.
- **Reference sites:** Langfuse (data-dense dashboard), n8n (dark mode execution), GitHub (developer-native aesthetic).

## Typography
- **Display/Hero:** Clash Grotesk — geometric, sharp, technical without being cold. Distinctive from the Inter/Space Grotesk convergence in the category.
- **Body:** DM Sans — clean, readable, pairs well with monospace. Slightly warmer than Inter.
- **UI/Labels:** Same as body (DM Sans).
- **Data/Tables:** JetBrains Mono — tabular-nums, ligatures, designed for screens. Connects CLI and web surfaces.
- **Code:** JetBrains Mono (same as data).
- **Loading:** Google Fonts via `<link>` tags. Self-host for production.
- **Scale:** 2xs(0.6rem) xs(0.7rem) sm(0.8rem) md(1rem) lg(1.25rem) xl(1.75rem) 2xl(2.5rem)

## Color
- **Approach:** Restrained — 1 accent + neutrals, color is rare and meaningful.
- **Primary:** `#10B981` (Emerald Green) — signals "system operational," "go," "healthy." Semantically correct for a governance system. Breaks the purple/teal category default.
- **Primary Dim:** `#065F46` — badges, subtle backgrounds on primary.
- **Neutrals (cool grays):**
  - Background: `#0D1117`
  - Surface: `#161B22`
  - Surface Raised: `#1C2128`
  - Border: `#30363D`
  - Border Muted: `#21262D`
  - Text: `#E6EDF3`
  - Text Muted: `#8B949E`
  - Text Subtle: `#6E7681`
- **Semantic:** success `#10B981`, warning `#F59E0B`, error `#EF4444`, info `#3B82F6`
- **Dark mode:** This IS the dark mode. Light mode is not a priority for v1. If added later: invert surfaces, reduce saturation 10-20%, keep primary green.

## Spacing
- **Base unit:** 8px
- **Density:** Compact — this is a dashboard, not a landing page. Maximize information density.
- **Scale:** 2xs(2) xs(4) sm(8) md(12) lg(16) xl(24) 2xl(32) 3xl(48)

## Layout
- **Approach:** Grid-disciplined — strict columns, predictable alignment, information density over whitespace.
- **Grid:** Sidebar (220px) + main content (fluid). Dashboard and CLI share the same visual language.
- **Max content width:** None (fluid within grid).
- **Border radius:** sm(4px) md(6px) lg(8px) full(9999px). Minimal rounding — infrastructure, not consumer.

## Motion
- **Approach:** Minimal-functional — only state transitions that aid comprehension. No entrance animations, no scroll effects.
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** micro(50-100ms) short(150-250ms)

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-15 | Initial design system created | Created by /design-consultation. Competitive research on LangChain, CrewAI, Langfuse, Helicone, n8n, Dify. Chose green accent to differentiate from purple/teal category default. Industrial/Utilitarian aesthetic matches "serious infrastructure" memorable-thing. |
