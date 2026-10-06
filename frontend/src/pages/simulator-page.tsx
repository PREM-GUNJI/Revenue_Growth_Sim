import { LeverWorkspace } from "@/components/lever-panels"
import { useWorkspace } from "@/workspace/workspace-context"

export function SimulatorPage() {
  const { scenarios, rawResults, activePack, envelope, evidenceDefaults, assumptions, addExternal } = useWorkspace()
  return (
    <>
            <div><h1 className="font-display text-2xl font-semibold">Scenario simulator</h1>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">Price, pack and promotion are one decision. Analyse how each lever moves volume, revenue and margin, then add joint combinations to the board.</p></div>
            <LeverWorkspace scenarios={scenarios} rawResults={rawResults} activePack={activePack} envelope={envelope} defaults={evidenceDefaults} assumptions={assumptions} onAdd={addExternal} />
    </>
  )
}
