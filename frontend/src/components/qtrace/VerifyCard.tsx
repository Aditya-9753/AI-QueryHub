import { CalendarDays, Gauge } from 'lucide-react'
import Card from '../common/Card'
import Badge from '../common/Badge'
import { money, pct } from './badges'
import type { Report } from '../../services/qtrace'

function Cell({ label, value, sub, ok }: { label: string; value: string; sub?: string; ok?: boolean }) {
  return (
    <div className="rounded-md border border-line bg-panel2/60 p-2.5">
      <div className="label">{label}</div>
      <div className="mt-1 font-mono text-[15px] font-semibold text-ink">{value}</div>
      {sub && <div className={`mt-0.5 font-mono text-[10.5px] ${ok === false ? 'text-bad' : ok ? 'text-accent' : 'text-dim'}`}>{sub}</div>}
    </div>
  )
}

export default function VerifyCard({ report }: { report: Report }) {
  const { health, gate } = report.verify
  const unit = gate.unit
  const chk = (n: string) => health.checks.find((c) => c.check_name === n)
  const comp = chk('completeness'), nul = chk('null_rate'), dup = chk('duplicates'), fresh = chk('freshness'),
    vol = chk('volume'), out = chk('outlier_days')
  const status = !health.ok ? ['DATA ISSUE', 'red'] as const : gate.status === 'anomaly' ? ['PASSED · REAL CHANGE', 'solid'] as const
    : gate.status === 'within_normal' ? ['WITHIN NORMAL', 'green'] as const : ['NO BASELINE', 'grey'] as const
  const band = gate.band
  const lo = band ? Math.min(band.low, gate.actual ?? band.low) : 0
  const hi = band ? Math.max(band.high, gate.actual ?? band.high) : 1
  const pos = (v: number) => `${((v - lo) / (hi - lo || 1)) * 100}%`
  const core = report.core

  return (
    <Card title="Step V · Anomaly gate" icon={<Gauge className="h-4 w-4" />} actions={<Badge tone={status[1]}>{status[0]}</Badge>}>
      <p className="mb-3 text-[13px] text-muted">Investigation se pehle: data theek hai? aur kya change normal band ke bahar hai?</p>
      <div className="grid grid-cols-2 gap-2">
        <Cell label="Completeness" value={`${health.days_with_data} / ${health.expected_days} days`} sub={comp ? `${(Number(comp.observed) * 100).toFixed(1)}% · need ${comp.expected}` : undefined} ok={comp?.passed} />
        <Cell label="Null rate" value={nul ? `${(Number(nul.observed) * 100).toFixed(2)}%` : '—'} sub={nul ? `${nul.expected}` : undefined} ok={nul?.passed} />
        <Cell label="Duplicate keys" value={dup?.observed ?? '—'} sub={dup ? (dup.passed ? 'key uniqueness ok' : 'duplicates mile') : undefined} ok={dup?.passed} />
        <Cell label={fresh ? 'Freshness' : vol ? 'Volume' : 'Outlier days'} value={fresh ? (fresh.passed ? 'fresh' : 'late') : vol ? `${vol.observed}/day` : out?.observed ?? '—'}
          sub={fresh ? fresh.observed.slice(0, 16) : vol ? vol.expected : out?.expected} ok={(fresh ?? vol ?? out)?.passed} />
      </div>

      <div className="mt-3 rounded-md border border-line bg-panel2/60 p-3">
        <div className="flex items-center justify-between">
          <span className="label">{gate.method === 'ets' ? 'ETS forecast vs actual' : gate.method === 'yoy' ? 'YoY excess test' : 'Baseline'}</span>
          <span className={`font-mono text-sm font-semibold ${gate.status === 'anomaly' ? 'text-bad' : 'text-ok'}`}>z = {gate.z === null ? '—' : gate.z.toFixed(2)}</span>
        </div>
        {band && (
          <>
            <div className="mt-1.5 flex flex-wrap justify-between gap-2 font-mono text-[12px]">
              <span className="text-muted">Exp {money(band.forecast, unit)} (σ {money(band.sigma, unit)})</span>
              <span className="font-semibold text-salmon">Actual {money(gate.actual, unit)}</span>
            </div>
            <div className="relative mt-2 h-2 rounded-full bg-line">
              <div className="absolute inset-y-0 rounded-full bg-accent/30" style={{ left: pos(band.low), width: `calc(${pos(band.high)} - ${pos(band.low)})` }} />
              {gate.actual !== undefined && <div className="absolute -top-1 h-4 w-1 rounded bg-salmon" style={{ left: pos(gate.actual) }} />}
            </div>
          </>
        )}
        {gate.yoy && (
          <div className="mt-1.5 font-mono text-[12px] text-muted">
            is saal {pct(Math.exp(gate.yoy.ty) - 1)} · pichhle saal {pct(Math.exp(gate.yoy.ly) - 1)} · excess {gate.yoy.excess.toFixed(3)} ± {gate.yoy.se_excess.toFixed(3)}
          </div>
        )}
        <div className="mt-2 font-mono text-[10.5px] text-dim">|z| &gt; 1.96 ⇒ normal 95% band ke bahar — investigate</div>
      </div>

      {core?.days0 !== undefined && (
        <div className="mt-3 flex items-center gap-3 rounded-md border border-line bg-panel2/60 p-3">
          <CalendarDays className="h-5 w-5 shrink-0 text-accent" />
          <div className="min-w-0 flex-1">
            <div className="label">Calendar discrepancy</div>
            <div className="text-xs text-muted">{core.days1} vs {core.days0} din</div>
          </div>
          <div className="text-right font-mono text-xs">
            <div className="text-dim line-through">{pct(Number(core.rel_change))} raw</div>
            <div className="font-semibold text-accent">{pct(Number(core.per_day_change))} per-day</div>
          </div>
        </div>
      )}
    </Card>
  )
}
