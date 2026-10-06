from __future__ import annotations

from backend.agent.orchestrator import AgentOrchestrator, ScriptedLLM, demo_plan
from backend.agent.trace import replay_trace


def test_ac022_trace_replay_matches_result_hashes_and_auditor(tmp_path):
    path = tmp_path / "run.jsonl"
    run = AgentOrchestrator().run("Replay this board", ScriptedLLM(demo_plan()), trace_path=path)
    replay = replay_trace(path)
    recorded_hashes = [event.result_hash for event in run.tool_events]
    replayed_hashes = [event["result_hash"] for event in replay["tool_calls"]]
    assert replayed_hashes == recorded_hashes
    assert replay["audit"] == run.audit.model_dump(mode="json")
