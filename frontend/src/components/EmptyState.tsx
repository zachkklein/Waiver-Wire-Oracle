export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-border bg-surface px-6 py-16 text-center text-sm text-text-muted">
      {message}
    </div>
  )
}

export function LoadingState({ message = "Loading" }: { message?: string }) {
  return (
    <div className="flex items-center justify-center gap-2.5 py-16 text-sm text-text-faint">
      <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
      {message}
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-status-bad/10 px-5 py-4 text-sm text-status-bad">{message}</div>
  )
}
