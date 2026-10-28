import { useCallback, useSyncExternalStore } from "react"

const EVENT = "rgs:preference"

function read(key: string): boolean {
  try { return window.localStorage.getItem(key) === "1" } catch { return false }
}

function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback)
  window.addEventListener("storage", callback)
  return () => { window.removeEventListener(EVENT, callback); window.removeEventListener("storage", callback) }
}

function usePreference(key: string): [boolean, (on: boolean) => void] {
  const value = useSyncExternalStore(subscribe, () => read(key), () => false)
  const set = useCallback((on: boolean) => {
    try { window.localStorage.setItem(key, on ? "1" : "0") } catch { /* private mode: keep the default */ }
    window.dispatchEvent(new Event(EVENT))
  }, [key])
  return [value, set]
}

/** Engineering detail (timings, hashes, IDs, raw traces). Off by default so business users see only the answer. */
export const useDetailMode = () => usePreference("rgs:show-technical-details")

/** The synthetic consumer research pages. Off by default because their numbers are illustrative. */
export const useAdvancedResearch = () => usePreference("rgs:show-advanced-research")
