import { createContext, useContext } from "react"
import type { HeatCell } from "@/components/analytics-views"
import type { ApiScenario, ApiScenarioResult, EnvelopeInfo, EvidenceDefaults } from "@/lib/api"
import type { Assumption, ScenarioResult } from "@/lib/types"
import type { WorkspaceMeta } from "@/lib/workspaces"

export type WorkspaceStatus = "loading" | "ready" | "notfound" | "failed"
export type SaveState = "saved" | "saving" | "error" | "conflict"

export interface WorkspaceValue {
  workspaceId: string
  workspace?: WorkspaceMeta
  status: WorkspaceStatus
  saveState: SaveState
  renameWorkspace: (name: string) => Promise<void>
  scenarios: ApiScenario[]
  setScenarios: React.Dispatch<React.SetStateAction<ApiScenario[]>>
  results: ScenarioResult[]
  rawResults: ApiScenarioResult[]
  heatmap: HeatCell[]
  heatmapLoading: boolean
  assumptions: Assumption[]
  envelope?: EnvelopeInfo
  evidenceDefaults?: EvidenceDefaults
  modelInfo?: { engine_version: string; data_hash: string }
  computeMs?: number
  loading: boolean
  error?: string
  activePack: string
  setActivePack: (pack: string) => void
  guardrail: number
  setGuardrail: (value: number) => void
  notice?: string
  setNotice: (message?: string) => void
  generateHeatmap: () => Promise<void>
  updateLever: (index: number, change: Partial<ApiScenario["levers"][string]>) => void
  addScenario: (copyIndex?: number) => void
  addExternal: (scenario: ApiScenario) => void
  addNearestSupported: (scenarioId: string) => Promise<void>
  supportedCount: number
  refusedCount: number
  best?: ScenarioResult
}

export const WorkspaceContext = createContext<WorkspaceValue | null>(null)

export function useWorkspace(): WorkspaceValue {
  const value = useContext(WorkspaceContext)
  if (!value) throw new Error("useWorkspace must be used inside a workspace route")
  return value
}
