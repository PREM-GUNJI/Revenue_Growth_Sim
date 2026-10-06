import { AgentPanel } from "@/components/agent-panel"
import { useWorkspace } from "@/workspace/workspace-context"

export function AssistantPage() {
  const { addExternal, workspaceId } = useWorkspace()
  return <AgentPanel onAcceptScenario={addExternal} workspaceId={workspaceId} />
}
