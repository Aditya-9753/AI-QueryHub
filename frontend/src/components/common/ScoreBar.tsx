export default function ScoreBar({ value, width = 'w-20' }: { value: number | null | undefined; width?: string }) {
  if (value === null || value === undefined) return <span className="font-mono text-xs text-dim">—</span>
  const pct = Math.max(0, Math.min(1, value)) * 100
  const color = value >= 0.75 ? 'bg-accent' : value >= 0.5 ? 'bg-warn' : 'bg-dim'
  return (
    <span className="inline-flex items-center gap-2">
      <span className={`h-1.5 ${width} overflow-hidden rounded-full bg-line`}>
        <span className={`block h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="font-mono text-xs tabular-nums text-ink">{value.toFixed(2)}</span>
    </span>
  )
}
