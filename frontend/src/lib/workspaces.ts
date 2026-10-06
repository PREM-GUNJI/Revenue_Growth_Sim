import { request } from "@/lib/api"
import type { ApiScenario } from "@/lib/api"

export interface WorkspaceMeta {
  id: string
  name: string
  description: string
  created_by: string
  updated_by: string
  created_at: string
  updated_at: string
  archived: boolean
  scenario_count: number
}

export interface HubSummary {
  database: string
  workspaces: { active: number; archived: number }
  agent_evals: null | {
    tasks: number
    passed: boolean
    checks: Record<string, boolean>
    metrics: Record<string, number>
    budgets: Record<string, number>
    report_updated_at: string
  }
  benchmarks: null | {
    rows: Array<{ scenarios: number; p95_ms: number; budget: string; result: "PASS" | "FAIL" }>
    within_budget: number
    total: number
    report_updated_at: string
  }
  governance: { assumptions: number; adrs: number }
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) })

export const listWorkspaces = (includeArchived = false) => request<WorkspaceMeta[]>("/workspaces" + (includeArchived ? "?include_archived=true" : ""))
export const getWorkspace = (id: string) => request<WorkspaceMeta>("/workspaces/" + encodeURIComponent(id))
export const createWorkspace = (body: { name: string; description?: string; scenarios?: ApiScenario[] | null }) =>
  request<WorkspaceMeta>("/workspaces", json("POST", body))
export const updateWorkspace = (id: string, body: { name?: string; description?: string; archived?: boolean }) =>
  request<WorkspaceMeta>("/workspaces/" + encodeURIComponent(id), json("PATCH", body))
export const getWorkspaceScenarios = (id: string) =>
  request<{ scenarios: ApiScenario[] | null; version: number }>("/workspaces/" + encodeURIComponent(id) + "/scenarios")
export const saveWorkspaceScenarios = (id: string, scenarios: ApiScenario[], version: number) =>
  request<{ version: number; scenario_count: number }>("/workspaces/" + encodeURIComponent(id) + "/scenarios", json("PUT", { scenarios, version }))
export const getHubSummary = () => request<HubSummary>("/hub/summary")
