import type { ReactNode } from "react"

export default function Card({
  title,
  action,
  children,
  className = "",
  bodyClassName = "p-5",
}: {
  title?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <section
      className={`overflow-hidden rounded-2xl border border-border bg-surface shadow-soft ${className}`}
    >
      {(title || action) && (
        <header className="flex items-center justify-between gap-4 px-5 pb-1 pt-5">
          {title && (
            <h2 className="font-display soft text-base font-semibold text-text">{title}</h2>
          )}
          {action}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  )
}
