# Generative UI intake — 5 November 2026
Agent Infrastructure only. Documentation-level assessment; no runtime, dependency, framework migration or live provider change.

## Delivery decision
Use controlled, schema-validated UI composition for v0.1. Reuse existing dashboard components and backend. Do not add a second orchestration authority. Evaluate a rendering framework only if it reduces measured implementation cost. Keep security-critical approval, identity/scope, cancellation and verified outcome displays application-owned; model-generated presentation must not invent authoritative state.

## Source disposition
| Source | Useful contribution | Disposition |
|---|---|---|
| https://ai-sdk.dev/docs/ai-sdk-ui/generative-user-interfaces | Tool-output-to-component rendering and loading/error states | Borrow pattern; adoption would require frontend/transport compatibility evaluation |
| https://github.com/CopilotKit/generative-ui | Controlled, declarative and open-ended UI examples; AG-UI/A2UI/MCP Apps | Protocol reference; the submitted duplicate URL is one source |
| https://github.com/CopilotKit/OpenIntelligentUI | Conversational text/native/custom interactive UI built with CopilotKit and AG-UI | Interaction reference; not a replacement backend |
| https://json-render.dev | Catalog-defined components/actions/data bindings and constrained JSON rendering | Preferred declarative-renderer experiment after baseline pilot works; not yet dependency-selected |
| https://research.google/blog/generative-ui-a-rich-custom-visual-interactive-user-experience-for-any-prompt/ and https://generativeui.github.io | Research, interactive explanation examples and PAGEN evaluation material | Inspiration and later evaluation; researcher preference findings are not our safety/latency evidence |
| https://uizard.io/ai-design/ | Prompt/screenshot-to-editable design mockups | Optional design-time tool, not execution or approval infrastructure |
| https://github.com/narrowin/awesome-generative-ui | Discovery catalog | Backlog input; verify each candidate against its primary documentation |

## Minimal component catalog
Source preview with provenance; editable brief with source locators; comparison table; proposal card; persisted run progress; result with independently checked evidence. Keep exact-action approval in a fixed trusted component. Model suggestions can choose allowed presentation and reference authorized data, but do not carry credentials, permission grants, arbitrary executable code or authoritative completion claims.

Client actions submit typed commands to the existing backend. The backend rechecks actor, scope, current revision, policy, approval and idempotency as relevant. UI allowlisting alone does not establish authorization. Streamed partial JSON must not activate consequential controls before full validation. Unknown components/actions fail safely with a text fallback. Generated external links and resource requests need explicit restrictions; never interpolate untrusted HTML.

## Acceptance before adoption
Prove one useful existing workflow with fixed rendering first. Compare one declarative variant on the same task for correctness, user effort, render/response latency, payload size and accessibility. Test malformed/truncated UI descriptions, forged success, stale revisions, unauthorized action IDs, XSS, foreign-scope data references, retry/duplicate commands, reduced motion and keyboard/mobile access. Any loss of authorization, provenance or outcome truth rejects the candidate regardless of visual preference.

No repository implementation was tested by this source review. Preserve all archived contributions and the current integration scope. This intake does not substitute for recovering/running the actual pilot.
