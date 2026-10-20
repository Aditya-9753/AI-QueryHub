import type { ReactNode } from 'react'

export default function Tabs<T extends string>({ value, onChange, items, size = 'md' }: {
  value: T
  onChange: (v: T) => void
  items: { value: T; label: ReactNode }[]
  size?: 'sm' | 'md'
}) {
  return (
    <div className="inline-flex max-w-full overflow-x-auto rounded-md border border-line bg-panel2 p-0.5">
      {items.map((it) => (
        <button key={it.value} type="button" onClick={() => onChange(it.value)}
          className={`whitespace-nowrap rounded font-mono uppercase tracking-wider transition-colors ${
            size === 'sm' ? 'px-2 py-1 text-[10.5px]' : 'px-3 py-1.5 text-[11px]'
          } ${value === it.value ? 'bg-accent/15 text-accent' : 'text-muted hover:text-ink'}`}>
          {it.label}
        </button>
      ))}
    </div>
  )
}
