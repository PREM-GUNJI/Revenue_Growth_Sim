import { LeverWorkspace } from "@/components/lever-panels"
import { useWorkspace } from "@/workspace/workspace-context"

export function SimulatorPage() {
  const { scenarios, rawResults, activePack, envelope, evidenceDefaults, assumptions, addExternal } = useWorkspace()
  return (
    <>
            <div><p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Step 2 of 4 · Options</p>
              <h1 className="mt-1 font-display text-2xl font-semibold">Build options</h1>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">Price, pack and promotion are one decision. Set them for each option on the left, see how each lever moves Aurora's volume, revenue and gross profit below, then compare the options on the next step.</p></div>
            <LeverWorkspace scenarios={scenarios} rawResults={rawResults} activePack={activePack} envelope={envelope} defaults={evidenceDefaults} assumptions={assumptions} onAdd={addExternal} />
    </>
  )
}
