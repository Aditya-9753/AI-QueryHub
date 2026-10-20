import type { ReactNode } from 'react'

const TONE = { default: 'text-ink', accent: 'text-accent', ok: 'text-ok', bad: 'text-bad', warn: 'text-warn' }

export default function StatTile({ label, value, sub, tone = 'default' }: {
  label: ReactNode
  value: ReactNode
  sub?: ReactNode
  tone?: keyof typeof TONE
}) {
  return (
    <div className="min-w-0 rounded-md border border-line bg-panel2/60 p-3">
      <div className="label truncate">{label}</div>
      <div className={`mt-1 truncate font-mono text-lg font-semibold tabular-nums ${TONE[tone]}`}>{value}</div>
      {sub && <div className="mt-0.5 truncate font-mono text-[11px] text-dim">{sub}</div>}
    </div>
  )
}
