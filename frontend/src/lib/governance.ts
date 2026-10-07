import { request } from "@/lib/api"
import { AuthError, UNAUTHORIZED_EVENT } from "@/lib/auth"
import type { AgentClaim } from "@/lib/api"

export interface AuditItem { id: number; at: string; user_email: string; action: string; workspace_id: string | null; workspace_name: string | null; detail: Record<string, unknown> | null }
export interface AuditLogPage { total: number; limit: number; offset: number; actions: string[]; items: AuditItem[] }
export interface AuditFilters { user_email?: string; action?: string; workspace_id?: string; start?: string; end?: string }
const query = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== "") search.set(key, String(value))
  const text = search.toString()
  return text ? "?" + text : ""
}
export const getAuditLog = (filters: AuditFilters, limit: number, offset: number) => request<AuditLogPage>("/audit/log" + query({ ...filters, limit, offset }))

export interface UsageBucket { runs: number; input_tokens: number; cached_input_tokens: number; output_tokens: number; cost_usd: number | null; unpriced_runs: number }
export interface UsageGroup extends UsageBucket { key: string | null; name?: string }
export interface AiUsage {
  totals: UsageBucket
  by_workspace: UsageGroup[]
  by_user: UsageGroup[]
  by_model: UsageGroup[]
  recent: Array<{ at: string; user_email: string; workspace_id: string | null; workspace_name: string | null; trace_id: string | null; model: string; input_tokens: number; cached_input_tokens: number; output_tokens: number; cost_usd: number | null }>
  rates: { version: string; source: string; fetched_on: string; unit: string; models: Record<string, { input: number; cached_input: number; output: number }> }
}
export const getAiUsage = (filters: { workspace_id?: string; start?: string; end?: string }) => request<AiUsage>("/audit/ai-usage" + query(filters))

export interface AgentRunRow { trace_id: string; goal: string; at: string; user_email: string; workspace_id: string | null; workspace_name: string | null; input_tokens: number | null; output_tokens: number | null; cost_usd: number | null }
export interface AgentRunDetail {
  trace_id: string
  model_id: string | null
  prompt_version_hash: string | null
  tool_calls: Array<{ call_id: string; name: string; result_hash: string }>
  answer: null | { summary: string; recommendations: string[]; refusals: string[]; caveats: string[]; claims: AgentClaim[] }
  audit: null | { passed: boolean; issues: string[]; numbers_checked: number }
}
export const getAgentRuns = (workspaceId?: string) => request<AgentRunRow[]>("/agent/runs" + query({ workspace_id: workspaceId }))
export const getAgentRun = (traceId: string) => request<AgentRunDetail>("/agent/runs/" + encodeURIComponent(traceId))

/** Download a workspace deck. Uses the session cookie; returns the blob and the server's filename. */
export async function exportWorkspace(workspaceId: string): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch("/api/workspaces/" + encodeURIComponent(workspaceId) + "/export", { method: "POST" })
  if (response.status === 401) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    throw new AuthError()
  }
  if (!response.ok) {
    let detail = "Export failed"
    try { const body = await response.json() as { detail?: unknown }; if (typeof body.detail === "string") detail = body.detail } catch { /* keep default */ }
    throw new Error(detail)
  }
  const match = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") ?? "")
  return { blob: await response.blob(), filename: match?.[1] ?? "workspace.pptx" }
}

/** Open the one-page labelled brief for a workspace in a new tab (print to PDF from there). */
export async function openWorkspaceBrief(workspaceId: string, traceId?: string): Promise<void> {
  const query = traceId ? "?trace_id=" + encodeURIComponent(traceId) : ""
  const response = await fetch("/api/workspaces/" + encodeURIComponent(workspaceId) + "/brief" + query, { method: "POST" })
  if (response.status === 401) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    throw new AuthError()
  }
  if (!response.ok) throw new Error("Brief failed")
  window.open(URL.createObjectURL(new Blob([await response.text()], { type: "text/html" })), "_blank")
}
