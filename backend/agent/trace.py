"""Agent run traces and deterministic offline replay."""

from __future__ import annotations

import json
from pathlib import Path

from backend.agent.auditor import audit_answer
from backend.agent.schemas import AgentAnswer, ToolEvent
from backend.agent.tools import AgentTools


class TraceRecorder:
    def __init__(self, model_id: str, prompt_version_hash: str, temperature: int = 0):
        self.header = {"type": "header", "model_id": model_id,
                       "prompt_version_hash": prompt_version_hash, "temperature": temperature}
        self.events: list[dict] = [self.header]

    def record_tool_events(self, events: list[dict]) -> None:
        self.events.extend({"type": "tool", **event} for event in events)

    def record_final(self, answer: AgentAnswer, verdict: dict) -> None:
        self.events.append({"type": "final", "answer": answer.model_dump(mode="json"), "audit": verdict})

    def write(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "".join(json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for event in self.events),
            encoding="utf-8",
        )


def replay_trace(path: str | Path, tools: AgentTools | None = None) -> dict:
    runtime = tools or AgentTools()
    entries = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    header = next((item for item in entries if item.get("type") == "header"), None)
    final = next((item for item in reversed(entries) if item.get("type") == "final"), None)
    if header is None or final is None:
        raise ValueError("trace must include header and final records")
    replayed = []
    for entry in entries:
        if entry.get("type") != "tool":
            continue
        call_id, result = runtime.invoke(entry["name"], entry["arguments"])
        event = runtime.events[-1]
        if event["result_hash"] != entry["result_hash"]:
            raise ValueError(f"replay hash mismatch for {entry['call_id']}")
        replayed.append({"call_id": call_id, "result_hash": event["result_hash"]})
    answer = AgentAnswer.model_validate(final["answer"])
    events = [ToolEvent.model_validate(item) for item in runtime.events]
    verdict = audit_answer(answer, events)
    if verdict.model_dump(mode="json") != final["audit"]:
        raise ValueError("replay Auditor verdict does not match the recorded verdict")
    return {"model_id": header["model_id"], "tool_calls": replayed,
            "audit": verdict.model_dump(mode="json"), "answer": answer.model_dump(mode="json")}
