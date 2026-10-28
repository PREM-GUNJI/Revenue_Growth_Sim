import type { ReactNode } from "react"
import { BrowserRouter, Link, Route, Routes } from "react-router-dom"
import { TooltipProvider } from "@/components/ui/tooltip"
import { AppLayout } from "@/layout/app-layout"
import type { AuthUser } from "@/lib/auth"
import { isAdmin, useRole } from "@/lib/user-context"
import { AgentRunDetailPage, AgentRunsPage } from "@/pages/agent-runs-page"
import { AssistantPage } from "@/pages/assistant-page"
import { AuditPage } from "@/pages/audit-page"
import { BoardPage } from "@/pages/board-page"
import { ConjointPage } from "@/pages/conjoint-page"
import { PersonasPage } from "@/pages/personas-page"
import { EvidencePage } from "@/pages/evidence-page"
import { ExecutivePage } from "@/pages/executive-page"
import { HomePage } from "@/pages/home-page"
import { SimulatorPage } from "@/pages/simulator-page"
import { SituationPage } from "@/pages/situation-page"
import { WorkspaceLayout } from "@/workspace/workspace-layout"

function NotFound() {
  return (
    <main className="mx-auto grid w-full max-w-xl flex-1 place-content-center gap-3 px-5 py-24 text-center">
      <h1 className="font-display text-3xl font-semibold">Page not found</h1>
      <p className="text-muted-foreground">That address doesn't match anything here.</p>
      <Link to="/" className="font-medium text-primary underline-offset-4 hover:underline">Go to the homepage</Link>
    </main>
  )
}

/** Governance pages are admin-only; the API returns 403 for anyone else, so other roles get a plain explanation instead. */
function AdminOnly({ children }: { children: ReactNode }) {
  if (isAdmin(useRole())) return children
  return (
    <main className="mx-auto grid w-full max-w-xl flex-1 place-content-center gap-3 px-5 py-24 text-center">
      <h1 className="font-display text-3xl font-semibold">Admins only</h1>
      <p className="text-muted-foreground">The audit trail, AI cost and agent run history are visible to administrators.</p>
      <Link to="/" className="font-medium text-primary underline-offset-4 hover:underline">Go to the homepage</Link>
    </main>
  )
}

function App({ user, onSignOut }: { user: AuthUser; onSignOut: () => void }) {
  return (
    <TooltipProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout user={user} onSignOut={onSignOut} />}>
            <Route index element={<HomePage />} />
            <Route path="w/:workspaceId" element={<WorkspaceLayout />}>
              <Route index element={<SituationPage />} />
              <Route path="simulator" element={<SimulatorPage />} />
              <Route path="board" element={<BoardPage />} />
              <Route path="assistant" element={<AssistantPage />} />
              <Route path="executive" element={<ExecutivePage />} />
              <Route path="evidence" element={<EvidencePage />} />
              <Route path="conjoint" element={<ConjointPage />} />
              <Route path="personas" element={<PersonasPage />} />
            </Route>
            <Route path="agent-runs" element={<AdminOnly><AgentRunsPage /></AdminOnly>} />
            <Route path="agent-runs/:traceId" element={<AdminOnly><AgentRunDetailPage /></AdminOnly>} />
            <Route path="audit" element={<AdminOnly><AuditPage /></AdminOnly>} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  )
}
export default App
