import { useQuery } from '@tanstack/react-query'
import { Gauge } from 'lucide-react'
import Badge from '../components/common/Badge'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import StatTile from '../components/common/StatTile'
import { EvalAPI } from '../services/qtrace'
import { errorMessage } from '../utils/format'

type Dict = Record<string, unknown>
const num = (v: unknown, pct = false) => (typeof v === 'number' ? (pct ? `${(v * 100).toFixed(1)}%` : v.toFixed(3)) : v === null || v === undefined ? '—' : String(v))
const Cmd = ({ children }: { children: string }) => <code className="rounded border border-line bg-bg px-1.5 py-0.5 font-mono text-[11.5px] text-accent">{children}</code>

// [key, label, is_percent, higher_is_better]
const BENCH: [string, string, boolean, boolean | null][] = [
  ['detection_rate', 'Detection (planted)', true, true],
  ['recall@3_given_detected', 'Recall@3 (detected)', true, true],
  ['segment_localized_given_detected', 'Segment localized', true, true],
  ['attribution_error', 'Attribution error (F32)', false, false],
  ['false_alarm_rate', 'False alarm (noise)', true, false],
  ['data_issue_detection', 'Data-issue detection', true, true],
  ['brier', 'Brier (F31)', false, false],
  ['ece', 'ECE (F31)', false, false],
  ['grounding_violations', 'Grounding violations', false, false],
  ['investigation_completion', 'Completion', true, true],
  ['evidence_coverage', 'Evidence coverage', true, true],
  ['reproducibility', 'Reproducibility', true, true],
  ['avg_queries', 'Avg SQL queries', false, null],
  ['avg_ms', 'Avg latency (ms)', false, null],
]

export default function EvalDashboard() {
  const { data, error } = useQuery({ queryKey: ['eval'], queryFn: EvalAPI.latest })
  const bench = (data?.benchmark as { summary?: Dict } | null)?.summary
  const ablation = (data?.ablation as { rows?: Dict[]; scenarios?: number } | null)
  const calib = data?.calibration as Dict | null
  const safety = data?.safety as Dict | null
  const golden = (data?.golden as { summary?: Dict } | null)?.summary

  return (
    <>
      <PageHeader crumbs={['Quality', 'Eval']} title="Evaluation" subtitle="Benchmark, ablation, calibration, safety — sirf asli runs ke numbers (Ch 18, 21.2)" />
      {error && <p className="mb-3 text-sm text-bad">{errorMessage(error)}</p>}
      <div className="flex flex-col gap-4">
        <Card label={bench ? `${String(bench.scenarios)} scenarios · ${String(bench.generated_at)}` : 'not run yet'} title="Planted-cause benchmark" icon={<Gauge className="h-4 w-4" />}>
          {!bench && <p className="text-sm text-dim">Chalao: <Cmd>python -m tests.eval_suite.benchmark --scenarios 200</Cmd></p>}
          {bench && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
              {BENCH.map(([k, label, p, hib]) => {
                const v = bench[k]
                const tone = typeof v !== 'number' || hib === null ? 'default' : (hib ? v >= 0.8 : v <= 0.15) ? 'ok' : 'warn'
                return <StatTile key={k} label={label} value={num(v, p)} tone={tone} />
              })}
            </div>
          )}
        </Card>

        <Card label={ablation?.scenarios ? `${ablation.scenarios} scenarios` : 'not run yet'} title="Ablation — har component ka yogdaan">
          {!ablation && <p className="text-sm text-dim"><Cmd>python -m tests.eval_suite.run_ablation</Cmd></p>}
          {ablation?.rows && (
            <div className="-mx-4 overflow-x-auto sm:-mx-5"><table className="tbl">
              <thead><tr><th>Variant</th><th>Removed</th><th className="text-right">Recall@3</th><th className="text-right">Attr. error</th><th className="text-right">False alarm</th><th className="text-right">Data issue</th><th className="text-right">False findings</th><th className="text-right">Brier</th></tr></thead>
              <tbody>{ablation.rows.map((r) => (
                <tr key={String(r.variant)} className={r.variant === 'Full' ? 'bg-accent/5' : ''}>
                  <td className={`font-mono text-xs ${r.variant === 'Full' ? 'text-accent' : 'text-ink'}`}>{String(r.variant)}</td><td className="text-[12.5px] text-muted">{String(r.removed)}</td>
                  {r.note ? <td colSpan={6} className="text-dim">{String(r.note)}</td> : <>
                    <td className="num text-right">{num(r['recall@3'], true)}</td><td className="num text-right">{num(r.attribution_error)}</td><td className="num text-right">{num(r.false_alarm_rate, true)}</td>
                    <td className="num text-right">{num(r.data_issue_detection, true)}</td><td className="num text-right">{num(r.false_findings_per_planted)}</td><td className="num text-right">{num(r.brier)}</td></>}
                </tr>))}</tbody>
            </table></div>
          )}
        </Card>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card label="F30 · 5-fold CV" title="Calibration">
            {!calib && <p className="text-sm text-dim"><Cmd>python -m tests.eval_suite.calibrate</Cmd></p>}
            {calib && (
              <dl className="divide-y divide-line text-sm">
                <div className="flex justify-between py-1.5"><dt className="text-muted">Labelled findings</dt><dd className="num text-ink">{String(calib.n)}</dd></div>
                <div className="flex justify-between py-1.5"><dt className="text-muted">Equal weights Brier / ECE</dt><dd className="num text-ink">{num((calib.equal_weights as Dict).brier)} / {num((calib.equal_weights as Dict).ece)}</dd></div>
                <div className="flex justify-between py-1.5"><dt className="text-muted">CV Brier (logistic)</dt><dd className="num text-ink">{num((calib.cv_5fold as Dict | null)?.logistic_brier)}</dd></div>
                <div className="flex justify-between py-1.5"><dt className="text-muted">CV Brier (fitted)</dt><dd className="num text-ink">{num((calib.cv_5fold as Dict | null)?.weighted_brier)}</dd></div>
                <div className="pt-2 font-mono text-[11px] text-dim">weights: {Object.entries((calib.fitted_weights as Dict) ?? {}).map(([k, v]) => `${k} ${num(v)}`).join(' · ')}</div>
              </dl>
            )}
          </Card>
          <Card label="Unsafe SQL suite" title="Safety block rate">
            {!safety && <p className="text-sm text-dim"><Cmd>python -m tests.eval_suite.safety</Cmd></p>}
            {safety && (
              <>
                <div className="font-mono text-4xl font-semibold text-ok">{num(safety.block_rate, true)}</div>
                <p className="mt-1 text-sm text-muted">{String(safety.unsafe_blocked)}/{String(safety.unsafe_total)} unsafe blocked · {String(safety.safe_passed)}/{String(safety.safe_total)} safe passed</p>
              </>
            )}
          </Card>
          <Card label="100 questions" title="Golden NL→SQL accuracy">
            {!golden && <p className="text-sm text-dim">LLM key ke saath: <Cmd>python -m tests.eval_suite.run_golden</Cmd></p>}
            {golden && (
              <>
                <div className="font-mono text-4xl font-semibold text-accent">{num(golden.accuracy, true)}</div>
                <p className="mt-1 text-sm text-muted">{String(golden.passed)}/{String(golden.total)} · {Object.entries((golden.by_mode as Dict) ?? {}).map(([k, v]) => `${k} ${(v as Dict).passed}/${(v as Dict).total}`).join(' · ')}</p>
                {Number(golden.llm_errors) > 0 && <Badge tone="amber" className="mt-2">{String(golden.llm_errors)} LLM errors</Badge>}
              </>
            )}
          </Card>
        </div>
      </div>
    </>
  )
}
