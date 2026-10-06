export interface AuthUser { email: string; display_name: string }

/** Raised by the API client on a 401 so the app can fall back to the sign-in page. */
export class AuthError extends Error {
  constructor(message = "Not signed in") { super(message); this.name = "AuthError" }
}
export const UNAUTHORIZED_EVENT = "rgs:unauthorized"

async function detailOf(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown }
    return typeof body.detail === "string" ? body.detail : fallback
  } catch {
    return fallback
  }
}

/** The signed-in user, or null when there is no valid session. Throws only if the server is unreachable. */
export async function fetchCurrentUser(): Promise<AuthUser | null> {
  const response = await fetch("/api/auth/me")
  if (response.status === 401) return null
  if (!response.ok) throw new Error(await detailOf(response, "Server error " + response.status))
  return (await response.json() as { user: AuthUser }).user
}

export async function signIn(email: string, password: string, rememberMe: boolean): Promise<AuthUser> {
  const response = await fetch("/api/auth/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, remember_me: rememberMe }),
  })
  if (!response.ok) throw new Error(await detailOf(response, "Login failed"))
  return (await response.json() as { user: AuthUser }).user
}

export async function signOut(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" })
}
