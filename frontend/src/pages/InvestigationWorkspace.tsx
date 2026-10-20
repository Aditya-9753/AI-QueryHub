import { useMemo, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  BarChart3, Download, FileCheck2, FlaskConical, GitBranch, Lightbulb, Loader2, ShieldCheck, Swords, TestTubes,
} from 'lucide-react'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import Empty from '../components/common/Empty'
import ScoreBar from '../components/common/ScoreBar'
import StatTile from '../components/common/StatTile'
import Tabs from '../components/common/Tabs'
import Waterfall from '../components/charts/Waterfall'
import ClaimsList from '../components/qtrace/ClaimsList'
import ExperimentPicker from '../components/qtrace/ExperimentPicker'
import Timeline from '../components/qtrace/Timeline'
import VerifyCard from '../components/qtrace/VerifyCard'
import { SourceChip, StatusChip, keyLabel, money, pct } from '../components/qtrace/badges'
import { useExperiment } from '../hooks/useExperiment'
import { DataSourceAPI } from '../services/api'
import { InvestigateAPI, type Report, type ReportFinding, type WaterfallData } from '../services/qtrace'
import type { WaterfallStep } from '../services/types'
import { useAppStore } from '../store/useAppStore'
import { errorMessage } from '../utils/format'

const FACTOR: Record<string, string> = {
  days: 'Calendar', orders_per_day: 'Orders/day', orders: 'Orders', aov: 'AOV', placed_orders: 'Placed/day',
  cancel_rate: 'Cancellations', mix: 'Mix shift', rate: 'AOV rate',
}
const SUPPORTED = new Set(['supported', 'upheld', 'revised'])
type Src = 'all' | 'metric_tree' | 'template' | 'drilldown' | 'llm'

function toSteps(w: WaterfallData): WaterfallStep[] {
  const inr = w.unit === 'inr'
  const s = (v: number) => (inr ? v / 1e5 : v)
  return [
    { label: `${w.period_base} base`, value: s(w.base ?? 0), kind: 'total' },
    ...w.steps.map((x) => ({ label: FACTOR[x.factor] ?? x.factor, value: s(x.amount), kind: 'delta' as const,
      note: `${pct(x.share)} of Δ · ${x.status}${x.label ? ` · ${x.label}` : ''}`, dim: !SUPPORTED.has(x.status) })),
    { label: `${w.period_current} final`, value: s(w.current ?? 0), kind: 'total' },
  ]
}

function Launcher() {
  const qc = useQueryClient()
  const { datasourceId, setDatasourceId, setCurrentExperimentId } = useAppStore()
  const [question, setQuestion] = useState('Feb me Delhi revenue kyun gira?')
  const datasources = useQuery({ queryKey: ['datasources'], queryFn: DataSourceAPI.list })
  const start = useMutation({
    mutationFn: async () => {
      const e = await InvestigateAPI.create(question, datasourceId)
      await InvestigateAPI.run(e.id)
      return e.id
    },
    onSuccess: (id) => { setCurrentExperimentId(id); qc.invalidateQueries({ queryKey: ['experiments'] }) },
  })
  const submit = (e: FormEvent) => { e.preventDefault(); if (question.trim()) start.mutate() }
  return (
    <form onSubmit={submit} className="flex flex-col gap-2 rounded-lg border border-line bg-panel p-3 md:flex-row md:items-center">
      <FlaskConical className="hidden h-5 w-5 shrink-0 text-accent md:block" />
      <input value={question} onChange={(e) => setQuestion(e.target.value)} className="input flex-1"
        placeholder="“Kyun?” wala sawaal — e.g. Feb me Delhi revenue kyun gira?" />
      <select value={datasourceId} onChange={(e) => setDatasourceId(e.target.value)} className="input md:w-56">
        {datasources.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
      </select>
      <Button type="submit" disabled={start.isPending}>{start.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}Investigate</Button>
      {start.isError && <p className="text-sm text-bad md:basis-full">{errorMessage(start.error)}</p>}
    </form>
  )
}

function MatrixRow({ f, unit }: { f: ReportFinding; unit: string }) {
  const rejected = !SUPPORTED.has(f.status)
  return (
    <tr className={rejected ? 'opacity-75' : ''}>
      <td className="min-w-[220px]">
        <div className={`font-mono text-[12px] font-semibold ${rejected ? 'text-muted' : 'text-accent'}`}>{keyLabel(f.key)}</div>
        <div className="mt-0.5 text-[13px] text-muted">{f.statement}</div>
      </td>
      <td><SourceChip source={f.source} /></td>
      <td className={`num whitespace-nowrap text-right ${rejected ? 'text-dim' : (f.amount ?? 0) < 0 ? 'text-salmon' : 'text-ok'}`}>{money(f.amount, unit)}</td>
      <td className="num text-right text-ink">{pct(f.share_of_delta)}</td>
      <td className="min-w-[220px] text-[12.5px] text-muted">
        <div>{f.method.replace(/_/g, ' ')} · effect {pct(f.effect)}</div>
        <div className="font-mono text-[11px] text-dim">
          {f.ci ? `CI [${f.ci[0].toFixed(3)}, ${f.ci[1].toFixed(3)}]` : ''}{f.q_value !== null ? ` · q ${f.q_value.toFixed(3)}` : ''}
        </div>
        {f.notes.length > 0 && <div className="text-[11.5px] text-dim">{f.notes.join('; ')}</div>}
      </td>
      <td><ScoreBar value={f.score} /></td>
      <td className="whitespace-nowrap"><StatusChip status={f.status} />{f.label && <div className="mt-1"><Badge tone={f.label === 'Strong' ? 'blue' : 'grey'}>{f.label}</Badge></div>}</td>
    </tr>
  )
}

function Matrix({ report }: { report: Report }) {
  const [src, setSrc] = useState<Src>('all')
  const unit = String(report.core.unit ?? '')
  const tested = new Set(report.findings.map((f) => f.key))
  const untested = report.hypotheses.filter((h) => !tested.has(h.id))
  const count = (s: Src) => (s === 'all' ? report.findings.length + untested.length
    : report.findings.filter((f) => f.source === s).length + untested.filter((h) => h.source === s).length)
  const rows = [...report.findings].filter((f) => src === 'all' || f.source === src)
    .sort((a, b) => Number(SUPPORTED.has(b.status)) - Number(SUPPORTED.has(a.status)) || b.share_of_delta - a.share_of_delta)
  return (
    <Card title="Hypothesis lifecycle matrix" icon={<TestTubes className="h-4 w-4" />}
      label={`${report.hypotheses.length} hypotheses · 4 generative sources · BH-FDR q = 0.10`}
      actions={<Tabs size="sm" value={src} onChange={setSrc} items={(['all', 'metric_tree', 'template', 'drilldown', 'llm'] as Src[])
        .filter((s) => s === 'all' || count(s) > 0).map((s) => ({ value: s, label: `${s.replace('_', ' ')} (${count(s)})` }))} />}>
      <div className="-mx-4 overflow-x-auto sm:-mx-5">
        <table className="tbl">
          <thead><tr><th>Hypothesis &amp; vector</th><th>Source</th><th className="text-right">Attributed Δ</th><th className="text-right">Share of Δ</th>
            <th>Statistical validation</th><th>Evidence score</th><th>Status</th></tr></thead>
          <tbody>
            {rows.map((f) => <MatrixRow key={f.key} f={f} unit={unit} />)}
            {untested.filter((h) => src === 'all' || h.source === src).map((h) => (
              <tr key={h.id} className="opacity-60">
                <td><div className="font-mono text-[12px] text-dim">{keyLabel(h.id)}</div><div className="text-[13px] text-dim">{h.statement}</div></td>
                <td><SourceChip source={h.source} /></td><td className="text-right text-dim">—</td><td className="text-right text-dim">—</td>
                <td className="text-[12px] text-dim">{h.status === 'ungrounded' ? 'semantic layer me map nahi hui' : `stop rule: ${report.stop_reason}`}</td>
                <td><ScoreBar value={null} /></td><td><StatusChip status={h.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export default function InvestigationWorkspace() {
  const navigate = useNavigate()
  const id = useAppStore((s) => s.currentExperimentId)
  const exp = useExperiment(id)
  const [bridgeTab, setBridgeTab] = useState<'bridge' | 'mix'>('bridge')
  const report = exp.data?.report
  const running = !!exp.data && ['queued', 'running'].includes(exp.data.status)
  const done = exp.data?.status === 'completed' && report?.status === 'completed'
  const waterfall = useQuery({ queryKey: ['waterfall', id, exp.data?.run?.id], queryFn: () => InvestigateAPI.waterfall(id!), enabled: !!id && done })
  const live = useQuery({ queryKey: ['timeline', id], queryFn: () => InvestigateAPI.timeline(id!), enabled: !!id && running, refetchInterval: running ? 1000 : false })
  const replay = useMutation({ mutationFn: () => InvestigateAPI.replay(id!, 'exact') })
  const exportJson = useMutation({ mutationFn: () => InvestigateAPI.exportFile(id!, 'json') })

  const unit = String(report?.core?.unit ?? '')
  const mix = report?.findings.find((f) => f.key.endsWith('.category_mix'))
  const topTwo = useMemo(() => (report ? report.frontier.map((k) => report.findings.find((f) => f.key === k)!)
    .filter((f) => f && SUPPORTED.has(f.status)).sort((a, b) => b.share_of_delta - a.share_of_delta).slice(0, 2) : []), [report])
  const lineage = useMemo(() => {
    const m = new Map<string, number>()
    report?.queries.forEach((q) => { const k = q.purpose.split(':')[0]; m.set(k, (m.get(k) ?? 0) + 1) })
    return [...m.entries()]
  }, [report])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div className="label">Workspace / Investigate · Q-TRACE+</div>
        <ExperimentPicker />
      </div>
      <Launcher />

      {!id && <Empty icon={<FlaskConical className="h-8 w-8" />} title="Koi investigation select nahi">Upar “kyun?” wala sawaal poochho ya purana experiment chuno.</Empty>}

      {exp.data && (
        <section className="flex flex-col gap-4 rounded-lg border border-line bg-panel p-4 sm:p-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge tone="blue">EXP-{exp.data.id.slice(0, 6).toUpperCase()}</Badge>
              <Badge tone="solid">INVESTIGATE</Badge>
              <StatusChip status={exp.data.status} />
              {exp.data.run?.dataset_version && <Badge className="max-w-full truncate normal-case">{exp.data.run.dataset_version.replace('asof=', 'as_of ').slice(0, 52)}</Badge>}
              {report?.schema_snapshot && <span className="font-mono text-[10.5px] text-accent">● schema {report.schema_snapshot.slice(0, 10)}</span>}
            </div>
            <h1 className="mt-2 text-xl font-semibold tracking-tight sm:text-2xl">“{exp.data.question}”</h1>
            {done && report && (
              <p className="mt-1 font-mono text-sm text-muted">
                {money(Number(report.core.T0), unit)} → {money(Number(report.core.T1), unit)}{' '}
                <span className={Number(report.core.rel_change) < 0 ? 'text-salmon' : 'text-ok'}>({pct(Number(report.core.rel_change))} raw Δ)</span>
                <span className="text-dim"> · {report.spec.metric} {Object.values(report.spec.filters).join(' ')} · {report.spec.period_base} → {report.spec.period_current} · parse: {report.parse_source}</span>
              </p>
            )}
            {exp.data.status === 'failed' && <p className="mt-2 text-sm text-bad">{exp.data.error}</p>}
          </div>
          {done && report && (
            <div className="w-full shrink-0 rounded-md border border-line bg-panel2 p-3 lg:w-80">
              <div className="label">Loop stop reason</div>
              <div className="mt-1 font-mono text-sm text-accent">{report.stop_reason}</div>
              <div className="mt-2 flex items-center justify-between font-mono text-[11px] text-muted">
                <span>explained {pct(report.explained)}</span><span>residual {pct(report.residual_share)}</span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-line">
                <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(0, Math.min(1, report.explained ?? 0)) * 100}%` }} />
              </div>
            </div>
          )}
        </section>
      )}

      {running && (
        <Card title="Live progress" icon={<Loader2 className="h-4 w-4 animate-spin" />} label="experiment_steps — run ke dauraan">
          {live.data?.length ? <Timeline steps={live.data} /> : <p className="text-sm text-dim">Queue me hai…</p>}
        </Card>
      )}

      {report && report.status !== 'completed' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <VerifyCard report={report} />
          <Card title="Early exit" icon={<ShieldCheck className="h-4 w-4" />} label="Verify step ne investigation roki">
            <ClaimsList claims={report.claims} />
          </Card>
        </div>
      )}

      {done && report && (
        <>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <VerifyCard report={report} />
            <Card title="Variance decomposition bridge" icon={<BarChart3 className="h-4 w-4" />}
              label={`log decomposition · ${money(Number(report.core.abs_change), unit)} total Δ`}
              actions={<Tabs size="sm" value={bridgeTab} onChange={setBridgeTab} items={[{ value: 'bridge', label: 'Bridge steps' }, { value: 'mix', label: 'Mix / rate split' }]} />}>
              {bridgeTab === 'bridge' ? (
                waterfall.data ? <Waterfall steps={toSteps(waterfall.data)} unit={unit === 'inr' ? '₹ L' : ''} height={300} /> : <p className="text-sm text-dim">Loading…</p>
              ) : mix ? (
                <div className="overflow-x-auto">
                  <table className="tbl">
                    <thead><tr><th>{String(mix.data.dimension)}</th><th className="text-right">Share base → now</th><th className="text-right">AOV base → now</th><th className="text-right">Mix_i</th><th className="text-right">Rate_i</th></tr></thead>
                    <tbody>
                      {(mix.data.segments as { segment: string; s0: number; s1: number; a0: number; a1: number; mix_i: number; rate_i: number }[]).map((s) => (
                        <tr key={s.segment}>
                          <td className="font-mono text-xs text-ink">{s.segment}</td>
                          <td className="num text-right text-muted">{pct(s.s0)} → {pct(s.s1)}</td>
                          <td className="num text-right text-muted">{money(s.a0, unit)} → {money(s.a1, unit)}</td>
                          <td className={`num text-right ${s.mix_i < 0 ? 'text-salmon' : 'text-ok'}`}>{s.mix_i.toFixed(1)}</td>
                          <td className={`num text-right ${s.rate_i < 0 ? 'text-salmon' : 'text-ok'}`}>{s.rate_i.toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-2 font-mono text-[11px] text-dim">ΔAOV = Mix {Number(mix.data.mix).toFixed(1)} + Rate {Number(mix.data.rate).toFixed(1)} (F4)</p>
                </div>
              ) : <p className="text-sm text-dim">Is run me AOV ka mix/rate drill-down nahi hua (AOV ka share chhota tha).</p>}
              {waterfall.data && (
                <div className="mt-2 grid grid-cols-2 gap-2 border-t border-line pt-3 sm:grid-cols-4">
                  <StatTile label="Starting level" value={money(waterfall.data.base, unit)} />
                  <StatTile label="Explained" value={pct(report.explained)} tone="accent" />
                  <StatTile label="Residual" value={pct(report.residual_share)} />
                  <StatTile label="Terminal level" value={money(waterfall.data.current, unit)} />
                </div>
              )}
              {topTwo.length > 0 && (
                <div className="mt-3 flex items-start gap-2 rounded-md border border-accent/25 bg-accent/5 p-3 text-[13px]">
                  <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                  <p className="text-muted"><b className="text-ink">Key insight: </b>
                    {topTwo.map((f, i) => <span key={f.key}>{i > 0 && ' + '}<b className="text-ink">{pct(f.share_of_delta)}</b> {keyLabel(f.key)}</span>)}
                    {' '}— total change ka {pct(topTwo.reduce((a, f) => a + f.share_of_delta, 0))}.</p>
                  {topTwo[0].score !== null && <Badge tone="blue" className="ml-auto shrink-0">score {topTwo[0].score.toFixed(2)}</Badge>}
                </div>
              )}
            </Card>
          </div>

          <Matrix report={report} />

          <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <Card title="Synthesis & claim provenance ledger" icon={<FileCheck2 className="h-4 w-4" />}
              actions={<Badge tone={report.grounding.violations ? 'red' : 'blue'}>{report.grounding.violations ? `${report.grounding.violations} ungrounded` : '100% numbers grounded'}</Badge>}>
              <ClaimsList claims={report.claims} onSelect={() => navigate('/evidence')} />
              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={() => navigate('/challenge')}><Swords className="h-4 w-4" />Launch counter-challenge</Button>
                <Button variant="secondary" onClick={() => navigate('/evidence')}><GitBranch className="h-4 w-4" />View evidence graph</Button>
                <Button variant="secondary" onClick={() => exportJson.mutate()}><Download className="h-4 w-4" />Export (.json)</Button>
              </div>
            </Card>
            <div className="flex flex-col gap-4">
              <Card title="Integrity audit" icon={<ShieldCheck className="h-4 w-4" />}>
                <p className="mb-3 text-[13px] text-muted">Narrative ka har number deterministic evidence se match hona chahiye (F33).</p>
                <dl className="divide-y divide-line text-sm">
                  <div className="flex justify-between py-2"><dt className="text-muted">Numbers checked</dt><dd className="num text-accent">{report.grounding.checked_numbers ?? 0}</dd></div>
                  <div className="flex justify-between py-2"><dt className="text-muted">Hallucinated numbers blocked</dt><dd className="num text-ink">{report.grounding.violations ?? 0} detected</dd></div>
                  <div className="flex justify-between py-2"><dt className="text-muted">Narrative source</dt><dd className="font-mono text-xs text-ink">{report.grounding.source}</dd></div>
                  <div className="flex items-center justify-between py-2"><dt className="text-muted">Deterministic replay</dt>
                    <dd>{replay.data ? <Badge tone={replay.data.match ? 'green' : 'red'}>{replay.data.matched}/{replay.data.queries} match</Badge>
                      : <button onClick={() => replay.mutate()} disabled={replay.isPending} className="font-mono text-[11px] text-accent hover:underline">{replay.isPending ? 'running…' : 'run exact replay'}</button>}</dd></div>
                </dl>
                <div className="label mb-2 mt-3">Query lineage</div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {lineage.map(([k, n], i) => (
                    <span key={k} className="flex items-center gap-1.5">
                      {i > 0 && <span className="text-dim">→</span>}
                      <span className="rounded border border-accent/30 bg-accent/5 px-1.5 py-0.5 font-mono text-[10.5px] text-accent">{k} ×{n}</span>
                    </span>
                  ))}
                </div>
              </Card>
              <Card label="Execution telemetry">
                <div className="font-mono text-2xl font-semibold text-ink">{(report.duration_ms / 1000).toFixed(2)}s</div>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <StatTile label="SQL queries" value={`${report.budget.queries}/${report.budget.max_queries}`} />
                  <StatTile label="LLM calls" value={`${report.budget.llm_calls}/${report.budget.max_llm_calls}`} />
                </div>
                <p className="mt-2 font-mono text-[11px] text-dim">{exp.data?.run?.model_version} · controls: {report.controls.join(', ') || '—'}</p>
                <Link to="/record" className="mt-2 inline-block font-mono text-[11px] text-accent hover:underline">full timeline + replay →</Link>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
