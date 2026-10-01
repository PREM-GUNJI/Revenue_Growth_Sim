import { AppFooter } from "@/components/app-footer"
import { AssumptionsDrawer } from "@/components/assumptions-drawer"
import { ComparisonBoard } from "@/components/comparison-board"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { MOCK_ASSUMPTIONS, MOCK_SCENARIOS } from "@/lib/mock-data"

function App() {
  return (
    <TooltipProvider>
      <div className="flex min-h-svh flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold">Revenue Growth Scenario Simulator</h1>
            <p className="text-sm text-muted-foreground">
              Synthetic CPG data · deterministic elasticity engine · comparison-first
            </p>
          </div>
          <AssumptionsDrawer assumptions={MOCK_ASSUMPTIONS} />
        </header>

        <main className="flex-1 px-6 py-6">
          <Tabs defaultValue="board">
            <TabsList>
              <TabsTrigger value="board">Comparison board</TabsTrigger>
              <TabsTrigger value="agent">
                Agent
                <Badge variant="outline" className="ml-2">
                  Phase 15
                </Badge>
              </TabsTrigger>
            </TabsList>
            <TabsContent value="board" className="mt-4">
              <ComparisonBoard scenarios={MOCK_SCENARIOS} />
            </TabsContent>
            <TabsContent value="agent" className="mt-4">
              <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                The agent panel (chat, quick-start goals, "Grounded: N/N" Auditor
                badge, accept-to-board) ships in Phase 15 once the agent
                orchestrator (Phase 10-13) is wired to this frontend.
              </div>
            </TabsContent>
          </Tabs>
        </main>

        <AppFooter />
      </div>
    </TooltipProvider>
  )
}

export default App
