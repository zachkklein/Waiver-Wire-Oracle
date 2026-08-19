export function EmptyState({ message }: { message: string }) {
  return <div className="py-10 text-center text-sm text-text-faint">{message}</div>
}

export function LoadingState({ message = "Loading…" }: { message?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-text-faint">
      <span className="h-3 w-3 animate-pulse rounded-full bg-accent" />
      {message}
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-status-bad/30 bg-status-bad/10 px-4 py-3 text-sm text-status-bad">
      {message}
    </div>
  )
}
