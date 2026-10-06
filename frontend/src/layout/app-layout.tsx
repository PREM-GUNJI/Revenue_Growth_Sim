import { useState } from "react"
import { Link, NavLink, Outlet, useLocation, useMatch } from "react-router-dom"
import { Bot, ChartColumn, GitCompareArrows, History, House, LayoutDashboard, LogOut, Menu, ScrollText, SlidersHorizontal, Sparkles, X } from "lucide-react"
import c5iLogo from "@/assets/c5i-logo.png"
import type { AuthUser } from "@/lib/auth"

export interface AppOutletContext { user: AuthUser }

type Item = { to: string; label: string; icon: typeof House; end?: boolean }

const navClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${isActive ? "bg-ink font-medium text-white" : "text-foreground/80 hover:bg-secondary"}`

function NavGroup({ title, items, onNavigate }: { title?: string; items: Item[]; onNavigate: () => void }) {
  return (
    <div className="space-y-1">
      {title && <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{title}</p>}
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} className={navClass} onClick={onNavigate}><Icon className="size-4 shrink-0" aria-hidden="true" />{label}</NavLink>
      ))}
    </div>
  )
}

/** Sidebar shell shared by every signed-in page: C5i brand, navigation, and the user menu. */
export function AppLayout({ user, onSignOut }: { user: AuthUser; onSignOut: () => void }) {
  const [open, setOpen] = useState(false)
  const workspace = useMatch("/w/:workspaceId/*")
  const location = useLocation()
  const base = workspace ? `/w/${workspace.params.workspaceId}` : undefined
  const close = () => setOpen(false)

  const workspaceItems: Item[] = base ? [
    { to: base, label: "Overview", icon: LayoutDashboard, end: true },
    { to: `${base}/simulator`, label: "Scenario simulator", icon: SlidersHorizontal },
    { to: `${base}/board`, label: "Comparison board", icon: GitCompareArrows },
    { to: `${base}/assistant`, label: "AI decision assistant", icon: Bot },
    { to: `${base}/evidence`, label: "Pricing evidence", icon: ChartColumn },
    { to: `${base}/conjoint`, label: "Conjoint simulation", icon: Sparkles },
  ] : []

  const governanceItems: Item[] = [
    { to: "/agent-runs", label: "Agent runs", icon: History },
    { to: "/audit", label: "Audit and AI usage", icon: ScrollText },
  ]

  const sidebar = (
    <div className="flex h-full flex-col gap-1 p-4">
      <Link to="/" onClick={close} className="mb-4 flex items-center gap-3 px-2" aria-label="C5i home">
        <img src={c5iLogo} alt="C5i" className="h-9 w-auto" />
      </Link>
      <nav aria-label="Primary" className="flex-1 space-y-1 overflow-y-auto">
        <NavGroup items={[{ to: "/", label: "Home", icon: House, end: true }]} onNavigate={close} />
        {workspaceItems.length > 0 && <NavGroup title="Workspace" items={workspaceItems} onNavigate={close} />}
        <NavGroup title="Governance" items={governanceItems} onNavigate={close} />
      </nav>
      <div className="mt-3 border-t pt-3">
        <div className="px-2 pb-2">
          <p className="truncate text-sm font-medium" title={user.email}>{user.display_name}</p>
          <p className="truncate text-xs text-muted-foreground">{user.email}</p>
        </div>
        <button type="button" onClick={onSignOut} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-secondary hover:text-foreground">
          <LogOut className="size-4" aria-hidden="true" />Sign out
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex min-h-svh">
      <aside className="sticky top-0 hidden h-svh w-64 shrink-0 border-r bg-card lg:block" aria-label="Sidebar">{sidebar}</aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="sticky top-0 z-30 flex items-center justify-between border-b bg-background/90 px-4 py-2 backdrop-blur-md lg:hidden">
          <Link to="/" aria-label="C5i home"><img src={c5iLogo} alt="C5i" className="h-7 w-auto" /></Link>
          <button type="button" aria-label="Open menu" aria-expanded={open} onClick={() => setOpen(true)} className="rounded-md p-2 hover:bg-secondary"><Menu className="size-5" /></button>
        </div>
        {open && <div className="fixed inset-0 z-40 lg:hidden" key={location.pathname}>
          <button type="button" aria-label="Close menu" className="absolute inset-0 bg-black/40" onClick={close} />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-card shadow-xl">
            <button type="button" aria-label="Close menu" onClick={close} className="absolute right-3 top-3 rounded-md p-2 hover:bg-secondary"><X className="size-5" /></button>
            {sidebar}
          </div>
        </div>}
        <Outlet context={{ user } satisfies AppOutletContext} />
      </div>
    </div>
  )
}
