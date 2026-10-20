const PHASES = ['Q', 'V', 'T', 'R', 'A', 'C', 'Ch', 'E', 'X', 'Rec']

export default function Timeline({ steps }: { steps: { phase?: string; type: string; ref: string | null; from: string | null; to: string | null; ts: string }[] }) {
  const seen = new Set(steps.map((s) => s.phase ?? s.type.split(':')[0]))
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1">
        {PHASES.map((p) => (
          <span key={p} className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${seen.has(p) ? 'bg-accent/15 text-accent' : 'bg-panel2 text-dim'}`}>{p}</span>
        ))}
      </div>
      <ol className="flex max-h-80 flex-col gap-1 overflow-y-auto pr-1 text-xs">
        {steps.map((s, i) => {
          const phase = s.phase ?? s.type.split(':')[0]
          return (
            <li key={i} className="flex items-center gap-2 border-l border-line pl-2">
              <span className="w-8 shrink-0 font-mono font-semibold text-accent">{phase}</span>
              <span className="text-dim">{s.type.replace(/^\w+:/, '')}</span>
              {s.ref && <span className="min-w-0 truncate font-mono text-muted">{s.ref}</span>}
              {(s.from || s.to) && <span className="ml-auto shrink-0 font-mono text-dim">{s.from ?? '·'} → <b className="text-ink">{s.to}</b></span>}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
