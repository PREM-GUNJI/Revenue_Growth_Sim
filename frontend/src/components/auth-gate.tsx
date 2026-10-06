import { useCallback, useEffect, useState } from "react"
import App from "@/App"
import { LoginPage } from "@/components/login-page"
import { UNAUTHORIZED_EVENT, fetchCurrentUser, signOut } from "@/lib/auth"
import type { AuthUser } from "@/lib/auth"

type Session = { state: "checking" } | { state: "signed-out" } | { state: "signed-in"; user: AuthUser } | { state: "unreachable"; message: string }

/** Shows the sign-in page until the server confirms a session, then the app. */
export function AuthGate() {
  const [session, setSession] = useState<Session>({ state: "checking" })

  const check = useCallback(() => {
    fetchCurrentUser()
      .then((user) => setSession(user ? { state: "signed-in", user } : { state: "signed-out" }))
      .catch((cause: unknown) => setSession({ state: "unreachable", message: cause instanceof Error ? cause.message : "Server unreachable" }))
  }, [])
  useEffect(check, [check])
  useEffect(() => {
    const expired = () => setSession({ state: "signed-out" })
    window.addEventListener(UNAUTHORIZED_EVENT, expired)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, expired)
  }, [])

  if (session.state === "checking") return <div className="grid min-h-svh place-items-center bg-ink text-sm text-white/70" role="status">Loading…</div>
  if (session.state === "unreachable") return (
    <div className="grid min-h-svh place-items-center bg-ink p-6 text-center text-white">
      <div className="max-w-sm space-y-4">
        <p className="font-display text-xl font-semibold">Can't reach the server</p>
        <p className="text-sm text-white/70">{session.message}. Check that the backend is running, then try again.</p>
        <button type="button" onClick={() => { setSession({ state: "checking" }); check() }} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:brightness-110">Try again</button>
      </div>
    </div>
  )
  if (session.state === "signed-out") return <LoginPage onSignedIn={(user) => setSession({ state: "signed-in", user })} />
  return <App user={session.user} onSignOut={() => { void signOut().finally(() => setSession({ state: "signed-out" })) }} />
}
