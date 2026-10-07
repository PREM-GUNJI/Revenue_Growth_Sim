import { PersonasPanel } from "@/components/personas-panel"
import { useWorkspace } from "@/workspace/workspace-context"

export function PersonasPage() {
  const { rawResults, addExternal } = useWorkspace()
  return <PersonasPanel baseline={rawResults[0]} onAdd={addExternal} />
}
