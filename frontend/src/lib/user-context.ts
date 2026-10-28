import { createContext, useContext } from "react"
import type { AuthUser, Role } from "@/lib/auth"

export const UserContext = createContext<AuthUser | null>(null)

/** The signed-in user's role. Hiding UI is a convenience; the server enforces every role check (ADR-017). */
export function useRole(): Role {
  return useContext(UserContext)?.role ?? "analyst"
}

export const canEdit = (role: Role) => role !== "viewer"
export const isAdmin = (role: Role) => role === "admin"
