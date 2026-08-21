import type { ReactNode } from "react"
import { useAuth } from "./AuthProvider"
import SignInPage from "./SignInPage"

/** Nothing below this renders until we know who (if anyone) is asking.
 *
 * The brief blank moment is deliberate: every page fetches league data on mount, and
 * without accounts resolved first those requests would go out unauthenticated and 401.
 * On a self-hosted install this resolves to `disabled` on the first tick and gets out of
 * the way entirely.
 */
export default function AuthGate({ children }: { children: ReactNode }) {
  const { status } = useAuth()

  if (status === "loading") return <div className="min-h-screen bg-bg" />
  if (status === "signed-out") return <SignInPage />
  return <>{children}</>
}
