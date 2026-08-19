import type { ReactNode } from "react"

export default function PageHeader({
  eyebrow,
  title,
  action,
}: {
  eyebrow?: string
  title: string
  action?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end sm:gap-6 md:mb-8">
      <div>
        <h1 className="font-display soft text-[30px] font-semibold leading-tight text-text md:text-[38px]">
          {title}
        </h1>
        {eyebrow && <p className="mt-1.5 text-sm text-text-muted">{eyebrow}</p>}
      </div>
      {action}
    </div>
  )
}
