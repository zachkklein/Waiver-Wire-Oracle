import { useEffect, useState } from "react"
import { supabase } from "../lib/auth"

/** The whole sign-in flow: type an email, get a link, come back signed in.
 *
 * Magic links only. There's no password to forget or for us to store, and the account
 * exists the first time someone follows a link — so this is the sign-up screen too, which
 * is why the copy never says "sign up".
 */
export default function SignInPage() {
  const [email, setEmail] = useState("")
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // A link that has expired or already been used sends the browser back here with the
  // reason in the URL fragment, and nothing else would ever show it.
  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""))
    const description = params.get("error_description")
    if (description) {
      setError(description.replace(/\+/g, " "))
      window.history.replaceState(null, "", window.location.pathname)
    }
  }, [])

  const send = async (e: React.FormEvent) => {
    e.preventDefault()
    const client = supabase()
    if (!client) return

    setSending(true)
    setError(null)
    try {
      const address = email.trim()
      const { error: sendError } = await client.auth.signInWithOtp({
        email: address,
        options: { emailRedirectTo: window.location.origin },
      })
      if (sendError) throw sendError
      setSent(address)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex items-center justify-center gap-3">
          <img src="/waiverLogo.png" alt="" aria-hidden className="h-12 w-12 object-contain" />
          <span className="font-display soft text-[19px] font-semibold leading-[1.15] text-text">
            Waiver Wire
            <br />
            <span className="text-accent">Oracle</span>
          </span>
        </div>

        <div className="rounded-2xl bg-surface p-7 shadow-soft">
          {sent ? (
            <div className="flex flex-col gap-3 text-center">
              <h1 className="font-display soft text-2xl font-semibold text-text">Check your email</h1>
              <p className="text-sm leading-relaxed text-text-muted">
                We sent a sign-in link to <span className="text-text">{sent}</span>. Open it on this
                device and you'll land back here signed in.
              </p>
              <button
                onClick={() => setSent(null)}
                className="mt-2 text-sm font-semibold text-accent hover:underline"
              >
                Use a different email
              </button>
            </div>
          ) : (
            <form onSubmit={send} className="flex flex-col gap-5">
              <div className="text-center">
                <h1 className="font-display soft text-2xl font-semibold text-text">
                  Sign in to your leagues
                </h1>
                <p className="mt-1.5 text-sm leading-relaxed text-text-muted">
                  We'll email you a link — no password to remember. First time here? This makes
                  your account.
                </p>
              </div>

              <div>
                <label htmlFor="email" className="mb-1.5 block text-sm font-semibold text-text">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoFocus
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full rounded-xl border border-border bg-surface-raised px-4 py-2.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
                />
              </div>

              <button
                type="submit"
                disabled={sending || !email.trim()}
                className="pressable w-full rounded-full bg-accent px-6 py-3 text-sm font-bold text-bg hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
              >
                {sending ? "Sending" : "Email me a link"}
              </button>

              {error && (
                <p className="rounded-xl bg-status-bad/10 px-4 py-3 text-sm leading-relaxed text-status-bad">
                  {error}
                </p>
              )}
            </form>
          )}
        </div>

        <p className="mt-6 text-center text-xs leading-relaxed text-text-faint">
          Your ESPN cookies are stored on the server and only ever sent to ESPN.
        </p>
      </div>
    </div>
  )
}
