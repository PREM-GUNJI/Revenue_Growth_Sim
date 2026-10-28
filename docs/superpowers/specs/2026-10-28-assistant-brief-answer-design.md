# Assistant brief answer (Decision first)

## Status
Implemented. Audience: both exec and analyst.

## Goal
Make “Ask the AI decision assistant” scannable in ~30 seconds while keeping the full audit trail available.

## Design
### Answer shape (`AgentAnswer`)
- `decision`: one plain sentence (what to do / which option wins).
- `why`: at most two short bullets (main commercial reason + volume/risk if needed).
- `recommendations`: at most two action sentences.
- `summary`: kept for traces/evals; mirrors `decision` (and may append why lines for older readers).
- Refusals stay mandatory and visible on the Decision card (never buried).

### UI (`AgentPanel`)
1. **Decision card** (always open): audit badge, `decision`, `why`, recommendations, refusals.
2. Collapsed by default: Why / claims & caveats · Compared options · Synthetic evidence · Sensitivity · Audit details.

Fallback if `decision` is empty (old traces): first sentence of `summary`.

### Prompt
Tighten OpenAI draft instructions to fill `decision` / `why` and cap recommendation count. Bump `PROMPT_VERSION_HASH`.

### Out of scope
Changing Auditor rules, engine math, or executive-brief export.
