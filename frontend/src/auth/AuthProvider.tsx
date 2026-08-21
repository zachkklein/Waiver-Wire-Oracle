import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react"
import type { Subscription } from "@supabase/supabase-js"
import { loadAuthConfig, rememberAccessToken, supabase } from "../lib/auth"

/** Whether this deployment has accounts, and if so who's signed in.
 *
 * `disabled` isn't an error state — it's the self-hosted install, where there is one
 * person and no sign-in screen. Components that behave differently with accounts check
 * `accountsEnabled` rather than assuming a user exists.
 */
export type AuthStatus = "loading" | "disabled" | "signed-out" | "signed-in"

interface AuthState {
  status: AuthStatus
  email: string | null
  accountsEnabled: boolean
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState>({
  status: "loading",
  email: null,
  accountsEnabled: false,
  signOut: async () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading")
  const [email, setEmail] = useState<string | null>(null)
  const subscription = useRef<Subscription | null>(null)

  useEffect(() => {
    let active = true

    loadAuthConfig().then((cfg) => {
      const client = supabase()
      if (!active) return
      if (!cfg.enabled || !client) {
        setStatus("disabled")
        return
      }

      // onAuthStateChange fires immediately with the stored session — and again when a
      // magic link is picked up out of the URL, when a token refreshes, and on sign-out —
      // so this one subscription covers first load and every later change.
      subscription.current = client.auth.onAuthStateChange((_event, session) => {
        rememberAccessToken(session?.access_token ?? null)
        setEmail(session?.user?.email ?? null)
        setStatus(session ? "signed-in" : "signed-out")
      }).data.subscription
    })

    return () => {
      active = false
      subscription.current?.unsubscribe()
      subscription.current = null
    }
  }, [])

  const signOut = async () => {
    await supabase()?.auth.signOut()
    rememberAccessToken(null)
  }

  return (
    <AuthContext.Provider
      value={{ status, email, accountsEnabled: status !== "disabled" && status !== "loading", signOut }}
    >
      {children}
    </AuthContext.Provider>
  )
}
