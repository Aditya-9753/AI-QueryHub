import type { ReactNode } from 'react'

/** Dark panel: mono label + title + actions. */
export default function Card({ title, label, icon, actions, children, className = '', pad = true }: {
  title?: ReactNode
  label?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
  children?: ReactNode
  className?: string
  pad?: boolean
}) {
  return (
    <section className={`min-w-0 rounded-lg border border-line bg-panel ${pad ? 'p-4 sm:p-5' : ''} ${className}`}>
      {(title || label || actions) && (
        <header className={`mb-3 flex flex-wrap items-start justify-between gap-3 ${pad ? '' : 'px-4 pt-4 sm:px-5 sm:pt-5'}`}>
          <div className="min-w-0">
            {label && <div className="label mb-1">{label}</div>}
            {title && (
              <h2 className="flex items-center gap-2 text-[15px] font-semibold text-ink">
                {icon && <span className="text-accent">{icon}</span>}
                {title}
              </h2>
            )}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  )
}
