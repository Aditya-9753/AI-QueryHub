import { useState } from 'react'
import { BrainCircuit, Check, ChevronRight, Cpu, Database, FileCheck2, Layers, ShieldCheck, Sparkles } from 'lucide-react'
import type { TraceStage } from '../../services/types'

const ICON: Record<string, typeof Cpu> = {
  context: Layers, llm_sql: BrainCircuit, firewall: ShieldCheck, execute: Database, answer: FileCheck2, profile: Sparkles,
}
/** Request ke dauraan dikhne wale placeholder stages (asli trace response ke saath aata hai). */
const PENDING = [
  ['context', 'Schema + semantic context'], ['llm_sql', 'LLM → SQL'], ['firewall', 'SQL firewall'],
  ['execute', 'Read-only execution'], ['answer', 'Grounded answer'], ['profile', 'Result profiling'],
]

const n = (v: unknown) => (typeof v === 'number' ? v : 0)
const list = (v: unknown) => (Array.isArray(v) ? (v as string[]) : [])

function detail(s: TraceStage): string[] {
  switch (s.key) {
    case 'context':
      return [`${list(s.retrieved).length}/${n(s.tables_visible)} tables · ${n(s.metrics)} metrics`, `rag: ${String(s.rag ?? '—')}`]
    case 'llm_sql':
      return [String(s.model ?? '—'), `${n(s.attempts)} attempt${n(s.attempts) > 1 ? 's (repaired)' : ''} · ${n(s.tokens_in) + n(s.tokens_out)} tokens`]
    case 'firewall':
      return [`4/4 layers passed`, `tables: ${list(s.tables).join(', ') || '—'}`]
    case 'execute':
      return [`${n(s.rows).toLocaleString('en-IN')} rows · ${String(s.dialect ?? '')}`, `sha256 ${String(s.checksum ?? '').slice(0, 12)}…`]
    case 'answer':
      return [s.source === 'llm' ? 'LLM sentence · numbers verified' : 'template from result', `${n(s.numbers)} numbers grounded`]
    case 'profile':
      return [`shape: ${String(s.shape ?? '—')}`, `${n(s.insights)} insights · no LLM`]
    default:
      return []
  }
}

/** ASK / ANALYZE ka execution trace: har stage, uska time aur kya hua — "black box" nahi. */
export default function PipelineTrace({ trace, pending = false }: { trace?: TraceStage[]; pending?: boolean }) {
  const [open, setOpen] = useState(false)
  const stages: TraceStage[] = pending ? PENDING.map(([key, label]) => ({ key, label, ms: 0 })) : trace ?? []
  if (!stages.length) return null
  const total = stages.reduce((a, s) => a + s.ms, 0)
  const max = Math.max(...stages.map((s) => s.ms), 1)
  const fw = stages.find((s) => s.key === 'firewall')
  const layers = (fw?.layers as { name: string; detail: string }[] | undefined) ?? []

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div className="label">Execution trace</div>
        <div className="font-mono text-[11px] text-muted">
          {pending ? <span className="animate-pulse text-accent">running…</span> : <>total <span className="text-ink">{total.toFixed(0)} ms</span></>}
        </div>
      </div>
      <ol className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {stages.map((s, i) => {
          const Icon = ICON[s.key] ?? Cpu
          return (
            <li key={s.key} className={`relative rounded-md border bg-panel2/60 p-2.5 ${pending ? 'animate-pulse border-line' : 'border-line'}`}>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-dim">0{i + 1}</span>
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded bg-accent/10 text-accent"><Icon className="h-3.5 w-3.5" /></span>
                <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium text-ink">{s.label}</span>
                {!pending && <Check className="h-3.5 w-3.5 shrink-0 text-ok" aria-label="passed" />}
              </div>
              {!pending && (
                <>
                  <div className="mt-2 font-mono text-[15px] font-semibold tabular-nums text-ink">{s.ms < 1 ? '<1' : s.ms.toFixed(0)}<span className="ml-0.5 text-[10px] text-dim">ms</span></div>
                  <div className="mt-1 h-1 overflow-hidden rounded-full bg-line" title={`${((s.ms / (total || 1)) * 100).toFixed(0)}% of total`}>
                    <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(2, (s.ms / max) * 100)}%` }} />
                  </div>
                  <div className="mt-2 space-y-0.5 font-mono text-[10.5px] leading-snug text-muted">
                    {detail(s).map((d) => <div key={d} className="truncate" title={d}>{d}</div>)}
                  </div>
                </>
              )}
              {i % 3 !== 2 && i < stages.length - 1 && <ChevronRight className="absolute -right-2.5 top-1/2 z-10 hidden h-4 w-4 -translate-y-1/2 text-dim lg:block" />}
            </li>
          )
        })}
      </ol>
      {layers.length > 0 && (
        <div className="mt-2">
          <button onClick={() => setOpen(!open)} className="font-mono text-[11px] text-accent hover:underline">
            {open ? '− hide' : '+ show'} firewall layers
          </button>
          {open && (
            <ul className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {layers.map((l, i) => (
                <li key={l.name} className="flex items-start gap-2 rounded border border-line px-2.5 py-1.5 text-[12px]">
                  <span className="font-mono text-accent">0{i + 1}</span>
                  <span className="text-ink">{l.name}</span>
                  <span className="ml-auto truncate pl-2 text-right font-mono text-[11px] text-muted" title={l.detail}>{l.detail}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
