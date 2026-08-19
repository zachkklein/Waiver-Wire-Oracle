import type { ReactNode, SelectHTMLAttributes, InputHTMLAttributes } from "react"

const CONTROL =
  "rounded-xl border border-border bg-surface px-4 py-2.5 text-sm text-text transition-colors hover:border-border-strong focus:border-accent focus:outline-none"

export function Select({
  label,
  children,
  ...props
}: { label?: string; children: ReactNode } & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <label className="flex flex-col gap-1.5">
      {label && <span className="text-xs font-medium text-text-muted">{label}</span>}
      <select {...props} className={`${CONTROL} ${props.className ?? ""}`}>
        {children}
      </select>
    </label>
  )
}

export function TextInput({
  label,
  ...props
}: { label?: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="flex flex-col gap-1.5">
      {label && <span className="text-xs font-medium text-text-muted">{label}</span>}
      <input
        {...props}
        className={`${CONTROL} placeholder:text-text-faint ${props.className ?? ""}`}
      />
    </label>
  )
}
