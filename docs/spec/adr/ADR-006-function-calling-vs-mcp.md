# ADR-006: Function calling vs MCP for the tool layer

Status: accepted

Context: The agent needs typed, schema-validated tools (engine calls, `calc`, `save_scenario`). Both Anthropic's native tool use and an MCP server could expose them.

Options considered:
- A. MCP server wrapping the engine, consumed by the agent as an MCP client.
- B. Native Anthropic tool use (function calling) with Pydantic schemas doubling as the tool specs, called directly in-process.
- C. Both: native tool use for the MVP runtime agent, MCP server as an optional V2 interface for external consumers (e.g. driving the agent from Claude Desktop).

Decision: C, with B as the MVP and the MCP server explicitly deferred to V2 (`docs/plan/PLAN.md` section 2). Native tool use keeps the MVP's dependency surface and latency lower and the scripted-fake-LLM test harness (Phase 10-13) simpler, since it only has to satisfy the Anthropic Messages API tool-call shape.

Consequences: If an MCP server is added later, it wraps the same tool functions (`simulator/agent/tools.py`) rather than duplicating logic, so the deterministic-components-as-tools principle (PLAN.md section 9) still holds either way.

Owner / date: C (agent owner) / 2026-10-05
