import type { ReactNode } from "react"

export default function PageHeader({
  eyebrow,
  title,
  icon,
  action,
}: {
  eyebrow?: string
  title: string
  icon?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end sm:gap-6 md:mb-8">
      <div className="flex items-center gap-4">
        {icon}
        <div>
          <h1 className="font-display soft text-[30px] font-semibold leading-tight text-text md:text-[38px]">
            {title}
          </h1>
          {eyebrow && <p className="mt-1.5 text-sm text-text-muted">{eyebrow}</p>}
        </div>
      </div>
      {action}
    </div>
  )
}
