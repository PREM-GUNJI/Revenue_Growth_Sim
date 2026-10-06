import { useNavigate } from "react-router-dom"
import { PricingEvidence } from "@/components/pricing-evidence"
import { useWorkspace } from "@/workspace/workspace-context"

export function EvidencePage() {
  const { rawResults, addExternal, workspaceId } = useWorkspace()
  const navigate = useNavigate()
  return <PricingEvidence baseline={rawResults[0]} onAdd={addExternal} onOpenConjoint={() => navigate(`/w/${workspaceId}/conjoint`)} />
}
