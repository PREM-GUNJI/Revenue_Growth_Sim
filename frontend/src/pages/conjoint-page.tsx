import { ConjointPanel } from "@/components/conjoint-panel"
import { useWorkspace } from "@/workspace/workspace-context"

export function ConjointPage() {
  const { evidenceDefaults, rawResults, addExternal } = useWorkspace()
  return <ConjointPanel defaults={evidenceDefaults} baseline={rawResults[0]} onAdd={addExternal} />
}
