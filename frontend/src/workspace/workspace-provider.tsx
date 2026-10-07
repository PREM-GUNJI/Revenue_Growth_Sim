import { useEffect, useRef, useState } from "react"
import type { ReactNode } from "react"
import type { HeatCell } from "@/components/analytics-views"
import { ApiError, evaluateScenarios, getAssumptions, getEnvelope, getEvidenceDefaults, getModelInfo, getSituation, nearestSupported, runAgent } from "@/lib/api"
import type { AgentApiRun, ApiScenario, ApiScenarioResult, EnvelopeInfo, EvidenceDefaults, Situation } from "@/lib/api"
import { baselineLever, newScenario, skuFor } from "@/lib/catalog"
import type { Assumption, ScenarioResult } from "@/lib/types"
import { getWorkspace, getWorkspaceScenarios, saveWorkspaceScenarios, updateWorkspace } from "@/lib/workspaces"
import type { WorkspaceMeta } from "@/lib/workspaces"
import { asUiAssumption, pickBest, toUiResults } from "./helpers"
import { WorkspaceContext } from "./workspace-context"
import type { SaveState, WorkspaceStatus } from "./workspace-context"

const DEFAULT_GOAL = "Improve gross profit without losing more than 5% volume."

/** Holds one case's scenarios and their engine results; every page of the case reads it via useWorkspace(). */
export function WorkspaceProvider({ workspaceId, children }: { workspaceId: string; children: ReactNode }) {
  const [workspace, setWorkspace] = useState<WorkspaceMeta>()
  const [status, setStatus] = useState<WorkspaceStatus>("loading")
  const [saveState, setSaveState] = useState<SaveState>("saved")
  const [scenarios, setScenarios] = useState<ApiScenario[]>([])
  const [results, setResults] = useState<ScenarioResult[]>([])
  const [rawResults, setRawResults] = useState<ApiScenarioResult[]>([])
  const [heatmap, setHeatmap] = useState<HeatCell[]>([])
  const [heatmapLoading, setHeatmapLoading] = useState(false)
  const [assumptions, setAssumptions] = useState<Assumption[]>([])
  const [envelope, setEnvelope] = useState<EnvelopeInfo>()
  const [evidenceDefaults, setEvidenceDefaults] = useState<EvidenceDefaults>()
  const [modelInfo, setModelInfo] = useState<{ engine_version: string; data_hash: string }>()
  const [computeMs, setComputeMs] = useState<number>()
  const [engineMs, setEngineMs] = useState<number>()
  const [situation, setSituation] = useState<Situation>()
  const [assumptionsOpen, setAssumptionsOpen] = useState(false)
  const [assumptionFocus, setAssumptionFocus] = useState<string[]>([])
  // The assistant's conversation lives here so the same run shows on the Recommend step and in the side drawer.
  const [agentGoal, setAgentGoal] = useState("")
  const [agentRun, setAgentRun] = useState<AgentApiRun>()
  const [agentError, setAgentError] = useState<string>()
  const [agentLoading, setAgentLoading] = useState(false)
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()
  const [activePack, setActivePack] = useState<string>("can_330ml")
  const [guardrail, setGuardrail] = useState(5)
  const [notice, setNotice] = useState<string>()
  const latest = useRef(0)
  const versionRef = useRef(1)
  const savedRef = useRef<ApiScenario[]>([])
  const saving = useRef(false)

  // Load this workspace and its saved scenarios from the server.
  useEffect(() => {
    let active = true
    Promise.all([getWorkspace(workspaceId), getWorkspaceScenarios(workspaceId)])
      .then(([meta, state]) => {
        if (!active) return
        const loaded = state.scenarios && state.scenarios.length ? state.scenarios : [newScenario("Baseline")]
        versionRef.current = state.version
        savedRef.current = loaded
        setWorkspace(meta); setScenarios(loaded); setStatus("ready")
        setAgentGoal((current) => current || meta.description || DEFAULT_GOAL)
      })
      .catch((cause: unknown) => {
        if (!active) return
        setStatus(cause instanceof ApiError && cause.status === 404 ? "notfound" : "failed")
        setError(cause instanceof Error ? cause.message : "Could not load this workspace")
      })
    return () => { active = false }
  }, [workspaceId])

  // Autosave one second after the last edit. Saves carry the version we loaded; a 409 means someone else saved first.
  useEffect(() => {
    if (status !== "ready" || scenarios === savedRef.current || saveState === "conflict") return
    const timer = setTimeout(async () => {
      if (saving.current) return
      saving.current = true
      setSaveState("saving")
      try {
        const saved = await saveWorkspaceScenarios(workspaceId, scenarios, versionRef.current)
        versionRef.current = saved.version
        savedRef.current = scenarios
        setSaveState("saved")
      } catch (cause) {
        if (cause instanceof ApiError && cause.status === 409) { setSaveState("conflict"); setError(cause.detail) }
        else setSaveState("error")
      } finally {
        saving.current = false
      }
    }, 1000)
    return () => clearTimeout(timer)
  }, [scenarios, status, workspaceId, saveState])

  async function renameWorkspace(name: string) {
    setWorkspace(await updateWorkspace(workspaceId, { name }))
  }

  // Re-evaluate shortly after any edit; ignore responses that arrive out of order.
  useEffect(() => {
    if (status !== "ready" || !situation) return
    const ticket = ++latest.current
    const timer = setTimeout(async () => {
      setLoading(true)
      setError(undefined)
      const started = performance.now()
      try {
        const raw = await evaluateScenarios(scenarios, 200, 42, setEngineMs)
        if (ticket !== latest.current) return
        setRawResults(raw)
        setResults(toUiResults(raw, scenarios, situation.totals.focal))
        setComputeMs(performance.now() - started)
      } catch (cause) {
        if (ticket === latest.current) setError(cause instanceof Error ? cause.message : "Unable to evaluate scenarios")
      } finally {
        if (ticket === latest.current) setLoading(false)
      }
    }, 350)
    return () => clearTimeout(timer)
  }, [scenarios, status, situation])

  useEffect(() => {
    let active = true
    Promise.all([getAssumptions(), getModelInfo(), getEnvelope(), getEvidenceDefaults(), getSituation()])
      .then(([items, info, env, defaults, where]) => {
        if (!active) return
        setAssumptions(items.map(asUiAssumption)); setModelInfo(info); setEnvelope(env); setEvidenceDefaults(defaults); setSituation(where)
      })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Backend unavailable") })
    return () => { active = false }
  }, [])
  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(undefined), 7000)
    return () => clearTimeout(timer)
  }, [notice])

  async function generateHeatmap() {
    setHeatmapLoading(true)
    setError(undefined)
    try {
      const prices = [0.92, 0.96, 1, 1.04, 1.08]
      const depths = [0, 10, 20, 30]
      const sku = skuFor(activePack)
      const grid = depths.flatMap((depth) => prices.map((price) => newScenario("Sweep price " + price + " promo " + depth, {
        [sku]: { price_index: price, promo_depth_pct: depth, mechanic: depth === 0 ? "none" : "TPR", promo_weeks_per_month: depth === 0 ? 0 : 2 },
      })))
      const evaluated = await evaluateScenarios(grid, 0, 42)
      setHeatmap(evaluated.map((item, i) => ({
        price: prices[i % prices.length], depth: depths[Math.floor(i / prices.length)], status: item.status,
        gp: item.status === "REFUSED" ? null : item.focal?.gp?.value ?? null,
      })))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to calculate heatmap")
    } finally {
      setHeatmapLoading(false)
    }
  }
  function updateLever(index: number, change: Partial<ApiScenario["levers"][string]>) {
    const sku = skuFor(activePack)
    setScenarios((current) => current.map((scenario, i) => {
      if (i !== index) return scenario
      const lever = scenario.levers[sku] ?? baselineLever
      return { ...scenario, levers: { ...scenario.levers, [sku]: { ...lever, ...change } } }
    }))
  }
  function addScenario(copyIndex?: number) {
    setScenarios((current) => {
      const source = copyIndex === undefined ? undefined : current[copyIndex]
      const copy: ApiScenario = source ? JSON.parse(JSON.stringify(source)) as ApiScenario : newScenario("New scenario")
      if (source) copy.name = "Copy of " + source.name
      return [...current, copy]
    })
  }
  /** Used by presets, research candidates and the agent: add a scenario and say where to find it. */
  function addExternal(scenario: ApiScenario) {
    setScenarios((current) => [...current, scenario])
    setNotice(`Added "${scenario.name}". It is evaluated by the engine on the comparison board.`)
  }
  async function addNearestSupported(scenarioId: string) {
    const index = results.findIndex((item) => item.scenarioId === scenarioId)
    if (index < 0) return
    try {
      const nearest = await nearestSupported(scenarios[index])
      setScenarios((current) => [...current, { ...nearest.scenario, name: "Nearest supported to " + scenarios[index].name, source: scenarios[index].source }])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not find supported alternative")
    }
  }

  async function askAgent(text?: string) {
    const goal = (text ?? agentGoal).trim()
    if (!goal) return
    setAgentLoading(true)
    setAgentError(undefined)
    try {
      setAgentRun(await runAgent(goal, workspaceId))
    } catch (cause) {
      setAgentError(cause instanceof Error ? cause.message : "Agent request failed")
    } finally {
      setAgentLoading(false)
    }
  }

  /** Open the assumptions drawer, optionally highlighting the ones a result depends on. */
  function openAssumptions(ids: string[] = []) {
    setAssumptionFocus(ids)
    setAssumptionsOpen(true)
  }

  const supportedCount = results.filter((item) => item.status !== "REFUSED").length
  const refusedCount = results.length - supportedCount
  const best = pickBest(results, guardrail)

  return <WorkspaceContext.Provider value={{
    workspaceId, workspace, status, saveState, renameWorkspace, scenarios, setScenarios, results, rawResults, heatmap, heatmapLoading, assumptions, envelope, evidenceDefaults,
    modelInfo, computeMs, engineMs, situation, loading, error, activePack, setActivePack, guardrail, setGuardrail, notice, setNotice, generateHeatmap,
    updateLever, addScenario, addExternal, addNearestSupported, supportedCount, refusedCount, best,
    assumptionsOpen, setAssumptionsOpen, assumptionFocus, openAssumptions,
    agent: { goal: agentGoal, setGoal: setAgentGoal, run: agentRun, error: agentError, loading: agentLoading, ask: askAgent, open: assistantOpen, setOpen: setAssistantOpen },
  }}>{children}</WorkspaceContext.Provider>
}
