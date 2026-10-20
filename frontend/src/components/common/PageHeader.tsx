import type { ReactNode } from 'react'

export default function PageHeader({ title, subtitle, crumbs, children }: {
  title: ReactNode
  subtitle?: ReactNode
  crumbs?: string[]
  children?: ReactNode
}) {
  return (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {crumbs && <div className="label mb-1.5 truncate">{crumbs.join(' / ')}</div>}
        <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  )
}
