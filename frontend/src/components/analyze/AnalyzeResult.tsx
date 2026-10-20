import { ArrowRight, BarChart3, Compass, Lightbulb, Table2 } from 'lucide-react'
import type { Mode, QueryResult } from '../../services/types'
import { fmtMeasure } from '../../utils/format'
import Badge from '../common/Badge'
import Card from '../common/Card'
import StatTile from '../common/StatTile'
import InsightCards from './InsightCards'
import PipelineTrace from './PipelineTrace'
import ResultTable, { CsvButton } from './ResultTable'
import SmartChart from './SmartChart'

type Tile = { label: string; value: string; sub?: string; tone?: 'default' | 'accent' | 'ok' | 'bad' | 'warn' }

/** Profile se KPI strip — har value result / profile stats se (koi naya number nahi). */
function kpis(r: QueryResult): Tile[] {
  const p = r.profile
  const s = p?.stats
  if (!p || !s || !p.measure) return [{ label: 'Rows', value: r.row_count.toLocaleString('en-IN') }, { label: 'Columns', value: String(r.columns.length) }]
  const f = (v: number) => fmtMeasure(v, p.format)
  const find = (k: string) => p.insights.find((i) => i.kind === k)
  if (p.shape === 'breakdown') {
    const top = find('top')
    const conc = find('concentration')
    return [
      s.total !== null ? { label: `Total ${p.measure}`, value: f(s.total), tone: 'accent' } : { label: `Avg ${p.measure}`, value: f(s.mean), tone: 'accent' },
      { label: `${p.dimension} values`, value: String(s.n) },
      { label: 'Leader', value: String(top?.values.label ?? p.top_label ?? '—'),
        sub: typeof top?.values.share === 'number' ? `${((top.values.share as number) * 100).toFixed(1)}% share` : `max ${f(s.max)}` },
      conc ? { label: 'Top-3 share', value: `${((conc.values.top3 as number) * 100).toFixed(1)}%`, sub: `${conc.values.pareto_k} make 80%`,
        tone: (conc.values.top3 as number) >= 0.8 ? 'warn' : 'default' }
        : { label: 'Lowest', value: String(find('spread')?.values.low ?? '—'), sub: f(s.min) },
    ]
  }
  if (p.shape === 'timeseries') {
    const trend = find('trend')
    const ch = typeof trend?.values.change === 'number' ? (trend.values.change as number) : null
    const peak = find('peak')
    return [
      { label: 'Periods', value: String(s.n) },
      { label: `Avg ${p.measure}`, value: f(s.mean) },
      { label: 'First → last', value: ch === null ? '—' : `${ch >= 0 ? '+' : ''}${(ch * 100).toFixed(1)}%`, tone: ch === null ? 'default' : ch >= 0 ? 'ok' : 'bad' },
      { label: 'Peak', value: f(s.max), sub: String(peak?.values.peak ?? '') },
    ]
  }
  if (p.shape === 'scalar') return [{ label: p.measure, value: f(s.max), tone: 'accent' }]
  return [
    s.total !== null ? { label: `Total ${p.measure}`, value: f(s.total), tone: 'accent' } : { label: `Avg ${p.measure}`, value: f(s.mean), tone: 'accent' },
    { label: 'Cells', value: String(s.n) },
    { label: 'Max', value: f(s.max) },
    { label: 'Min', value: f(s.min) },
  ]
}

export default function AnalyzeResult({ result, onFollowup }: { result: QueryResult; onFollowup: (q: string, mode: Mode) => void }) {
  const p = result.profile
  const tiles = kpis(result)
  const showInsights = !!p && p.shape !== 'scalar' && p.insights.length > 0

  return (
    <div className="flex flex-col gap-4">
      <Card className="relative overflow-hidden border-accent/30">
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-accent/10 blur-3xl" />
        <div className="label mb-1.5">{result.mode === 'ANALYZE' ? 'Analysis' : 'Answer'}</div>
        <p className="max-w-3xl text-lg leading-snug text-ink sm:text-xl">{result.answer}</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Badge tone="solid">{result.mode}</Badge>
          <Badge tone={result.answer_source === 'llm' ? 'green' : 'grey'}>{result.answer_source === 'llm' ? 'AI sentence · numbers verified' : 'answer from result'}</Badge>
          <Badge>{result.generated ? `AI SQL · ${result.attempts} attempt${result.attempts > 1 ? 's' : ''}` : 'manual SQL'}</Badge>
          {p && <Badge tone="blue">{p.shape}</Badge>}
        </div>
        {tiles.length > 1 && (
          <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-4">
            {tiles.map((t) => <StatTile key={t.label} label={t.label} value={t.value} sub={t.sub} tone={t.tone} />)}
          </div>
        )}
      </Card>

      <div className={`grid grid-cols-1 gap-4 ${showInsights ? 'xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]' : ''}`}>
        <Card label={p?.measure && p.dimension ? `${p.measure} by ${p.dimension}` : 'Visualization'} title="Chart" icon={<BarChart3 className="h-4 w-4" />}>
          <SmartChart columns={result.columns} rows={result.rows} profile={p} />
        </Card>
        {showInsights && (
          <Card label="Auto insights" title="What stands out" icon={<Lightbulb className="h-4 w-4" />}>
            <InsightCards insights={p!.insights} rows={result.row_count} />
          </Card>
        )}
      </div>

      {!!p?.followups.length && (
        <Card label="Next steps" title="Dig deeper" icon={<Compass className="h-4 w-4" />}>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
            {p.followups.map((f) => (
              <button key={f.question} onClick={() => onFollowup(f.question, f.mode)}
                className="group flex items-start gap-2 rounded-md border border-line bg-panel2/50 p-3 text-left transition hover:border-accent/50 hover:bg-accent/5">
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-semibold text-ink group-hover:text-accent">{f.label}</div>
                  <div className="mt-0.5 line-clamp-2 text-[12px] text-dim">{f.question}</div>
                </div>
                <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-dim group-hover:text-accent" />
              </button>
            ))}
          </div>
        </Card>
      )}

      {!!result.trace?.length && <Card><PipelineTrace trace={result.trace} /></Card>}

      <Card label={`${result.row_count.toLocaleString('en-IN')} rows · ${result.duration_ms} ms`} title="Result data" icon={<Table2 className="h-4 w-4" />}
        actions={<CsvButton columns={result.columns} rows={result.rows} name={`queryhub-${result.history_id.slice(0, 8)}`} />}>
        <ResultTable columns={result.columns} rows={result.rows} profile={p} />
        {result.row_count > result.rows.length && <p className="mt-2 text-xs text-dim">Pehli {result.rows.length} rows (total {result.row_count}).</p>}
      </Card>
    </div>
  )
}
