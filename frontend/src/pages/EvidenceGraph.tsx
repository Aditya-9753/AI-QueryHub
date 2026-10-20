import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import type { Edge, Node } from '@xyflow/react'
import { FileCheck2, GitBranch, Network, ShieldCheck, Swords, X } from 'lucide-react'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import Empty from '../components/common/Empty'
import PageHeader from '../components/common/PageHeader'
import ScoreBar from '../components/common/ScoreBar'
import SqlBlock from '../components/common/SqlBlock'
import Tabs from '../components/common/Tabs'
import EvidenceGraphView from '../components/evidence-graph/EvidenceGraphView'
import ClaimsList from '../components/qtrace/ClaimsList'
import ExperimentPicker from '../components/qtrace/ExperimentPicker'
import { LabelChip, StatusChip, keyLabel, pct } from '../components/qtrace/badges'
import { useExperiment } from '../hooks/useExperiment'
import { InvestigateAPI, type GraphNode, type Report, type ReportFinding } from '../services/qtrace'
import { useAppStore } from '../store/useAppStore'

const SUPPORTED = new Set(['supported', 'upheld', 'revised'])
const STATUS_COLOR: Record<string, string> = {
  supported: '#34d399', upheld: '#34d399', revised: '#fbbf24', rejected: '#f87171', overturned: '#f87171',
  inconclusive: '#62728b', not_tested: '#2a3a57',
}
export const TEST_DESC: Record<string, string> = {
  seasonality: 'Pichhle saal isi mahine bhi aisa hua tha? Finding ka YoY excess check',
  calendar: 'Kya effect sirf din kam/zyada hone se hai? (per-day share)',
  data_quality: 'Dono periods ka data health — missing days, nulls, duplicates',
  small_sample: 'Sample adequacy: n vs n_required (SA ≥ 0.5)',
  alternative_segment: 'Koi doosra dimension change ko zyada concentrate karta hai?',
  simpson: 'Mix vs rate — dominant effect claim ke type se match?',
  market_wide: 'Control market me bhi same change? (DiD confidence interval)',
}
const COMPONENT: Record<string, string> = {
  DC: 'Directional consistency', SA: 'Sample adequacy', ES: 'Effect size', SS: 'Statistical significance',
  CR: 'Challenge robustness', RC: 'Reconciliation', TS: 'Temporal stability',
}

type View = 'graph' | 'battery' | 'claims'

function nodeLabel(kind: string, title: string, sub?: string) {
  return (
    <div className="text-left">
      <div className="font-mono text-[9.5px] uppercase tracking-[0.14em] text-[#62728b]">{kind}</div>
      <div className="mt-0.5 line-clamp-3 text-[11.5px] leading-snug text-[#e6edf7]">{title}</div>
      {sub && <div className="mt-1 font-mono text-[10px] text-[#93a4bd]">{sub}</div>}
    </div>
  )
}

const ROWS = 7   // har column me max nodes; zyada hon to agla sub-column (graph readable rahe)

function layout(graph: Report['graph'], findings: ReportFinding[], highlight: Set<string>, selected: string | null,
  show: { queries: boolean; challenges: boolean }) {
  const depth = new Map(findings.map((f) => [`F:${f.key}`, f.depth]))
  const groups: GraphNode[][] = [[], [], [], [], []]
  for (const n of graph.nodes) {
    const k = n.data.kind
    if (k === 'insight' || k === 'fact' || k === 'verify') groups[0].push(n)
    else if (k === 'finding') groups[(depth.get(n.id) ?? 0) > 0 ? 2 : 1].push(n)
    else if (k === 'challenge') { if (show.challenges) groups[3].push(n) }
    else if (show.queries) groups[4].push(n)
  }
  const nodes: Node[] = []
  const visible = new Set<string>()
  let col = 0
  groups.forEach((list, g) => {
    if (!list.length) return
    list.forEach((n, i) => place(n, col + Math.floor(i / ROWS), i % ROWS, g))
    col += Math.ceil(list.length / ROWS)
  })
  function place(n: GraphNode, c: number, r: number, g: number) {
    visible.add(n.id)
    const d = n.data
    let border = '#2a3a57'
    let label
    if (d.kind === 'finding') {
      border = STATUS_COLOR[String(d.status)] ?? '#2a3a57'
      label = nodeLabel(`finding · ${String(d.status)}`, String(d.label), `share ${pct(d.share as number)} · score ${typeof d.score === 'number' ? d.score.toFixed(2) : '—'}`)
    } else if (d.kind === 'challenge') {
      const pass = String(d.label).endsWith('pass')
      border = pass ? '#34d399' : '#f87171'
      label = nodeLabel('challenge', String(d.label))
    } else if (d.kind === 'query') {
      label = nodeLabel(`query ${n.id}`, String(d.purpose ?? ''), `${String(d.row_count ?? '')} rows · ${String(d.checksum ?? '').slice(0, 10)}`)
    } else {
      border = n.id === 'I' ? '#22d3ee' : '#2b5c68'
      label = nodeLabel(String(d.kind), String(d.label))
    }
    const hot = highlight.has(n.id) || selected === n.id
    nodes.push({
      id: n.id, position: { x: c * 255 + g * 45, y: r * 112 }, data: { label },
      style: {
        width: 225, padding: 10, borderRadius: 8, background: hot ? '#0b3340' : '#0d1524', color: '#e6edf7',
        border: `${hot ? 2 : 1}px solid ${hot ? '#22d3ee' : border}`, boxShadow: hot ? '0 0 18px rgba(34,211,238,.35)' : 'none',
      },
    })
  }
  const edges: Edge[] = graph.edges.filter((e) => visible.has(e.source) && visible.has(e.target)).map((e) => {
    const bad = e.label === 'contradicted_by'
    return {
      id: e.id, source: e.source, target: e.target, animated: bad, label: bad ? 'contradicted_by' : undefined,
      style: { stroke: bad ? '#f87171' : '#2a3a57', strokeDasharray: bad ? '5 4' : undefined },
      labelStyle: { fill: '#f87171', fontSize: 10 }, labelBgStyle: { fill: '#070c16' },
    }
  })
  return { nodes, edges }
}

function Provenance({ node, linked, onPick, onClose }: { node: GraphNode; linked: GraphNode[]; onPick: (id: string) => void; onClose: () => void }) {
  const d = node.data
  const rows: [string, unknown][] = d.kind === 'query' ? [
    ['Metric definition', d.metric_definition],
    ['Filters', d.filters && Object.keys(d.filters as object).length ? JSON.stringify(d.filters) : 'none'],
    ['Time window', Array.isArray(d.time_window) ? (d.time_window as string[]).join(' → ') : d.time_window],
    ['Group by', Array.isArray(d.group_by) ? (d.group_by as string[]).join(', ') : d.group_by],
    ['Dataset version', d.dataset_version],
    ['Schema snapshot', typeof d.schema_snapshot === 'string' ? d.schema_snapshot.slice(0, 16) : d.schema_snapshot],
    ['Analysis method', d.analysis_method],
    ['Rows · latency', `${String(d.row_count)} · ${Number(d.duration_ms ?? 0).toFixed(0)} ms`],
    ['Linked claims', Array.isArray(d.claim_ids) && d.claim_ids.length ? (d.claim_ids as string[]).join(', ') : '—'],
  ] : Object.entries(d).filter(([k]) => !['label', 'kind'].includes(k))
  return (
    <Card label={`Node provenance · ${String(d.kind)}`} title={<span className="font-mono text-accent">{node.id}</span>}
      actions={<button onClick={onClose} aria-label="close" className="rounded p-1 text-dim hover:bg-white/5 hover:text-ink"><X className="h-4 w-4" /></button>}>
      <p className="mb-3 text-sm text-ink">{String(d.label)}</p>
      {d.kind === 'query' && typeof d.sql === 'string' && <div className="mb-3"><SqlBlock sql={d.sql} maxHeight={200} /></div>}
      <dl className="divide-y divide-line text-[12.5px]">
        {rows.map(([k, v]) => (
          <div key={k} className="flex gap-3 py-1.5">
            <dt className="w-32 shrink-0 text-muted">{k}</dt>
            <dd className="min-w-0 break-all font-mono text-[11.5px] text-ink">{v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd>
          </div>
        ))}
      </dl>
      {linked.length > 0 && (
        <div className="mt-3">
          <div className="label mb-1.5">Linked evidence ({linked.length})</div>
          <div className="flex flex-wrap gap-1.5">
            {linked.map((q) => (
              <button key={q.id} onClick={() => onPick(q.id)} title={String(q.data.label)}
                className="rounded border border-accent/30 bg-accent/5 px-1.5 py-0.5 font-mono text-[10.5px] text-accent hover:bg-accent/15">
                {q.data.kind === 'query' ? `${q.id} · ${String(q.data.purpose ?? '').split(':')[0]}` : q.id}
              </button>
            ))}
          </div>
        </div>
      )}
      {d.kind === 'query' && (
        <>
          <div className="mt-3 break-all rounded border border-line bg-panel2 p-2 font-mono text-[10.5px] text-dim">sha256(rows) = {String(d.checksum)}</div>
          <div className="mt-2 flex flex-wrap gap-1.5"><Badge tone="green">read-only connection</Badge><Badge tone="blue">firewall passed</Badge><Badge>aggregates only</Badge></div>
        </>
      )}
    </Card>
  )
}

function GatedScore({ f }: { f: ReportFinding }) {
  return (
    <Card label="Gated evidence score" title={keyLabel(f.key)} icon={<ShieldCheck className="h-4 w-4" />}>
      <div className="flex items-end gap-3">
        <div className="font-mono text-3xl font-semibold text-accent">{f.score !== null ? f.score.toFixed(2) : '—'}</div>
        <div className="mb-1 flex gap-1.5"><LabelChip label={f.label} /><StatusChip status={f.status} /></div>
      </div>
      <ul className="mt-3 flex flex-col gap-1.5">
        {Object.entries(f.components).map(([k, v]) => (
          <li key={k} className="flex items-center gap-2 text-[12px]">
            <span className="w-8 font-mono text-accent">{k}</span>
            <span className="min-w-0 flex-1 truncate text-muted">{COMPONENT[k] ?? k}</span>
            <ScoreBar value={v} width="w-16" />
          </li>
        ))}
      </ul>
      {f.contradiction_penalty > 0 && <p className="mt-2 font-mono text-[11px] text-bad">contradiction penalty −{f.contradiction_penalty.toFixed(2)}</p>}
      <p className="mt-2 font-mono text-[10.5px] text-dim">gate: DC ≥ 0.7 aur SA ≥ 0.5, warna “Insufficient”</p>
    </Card>
  )
}

export default function EvidenceGraph() {
  const navigate = useNavigate()
  const id = useAppStore((s) => s.currentExperimentId)
  const exp = useExperiment(id)
  const ev = useQuery({ queryKey: ['evidence', id, exp.data?.run?.id], queryFn: () => InvestigateAPI.evidence(id!), enabled: !!id && exp.data?.status === 'completed' })
  const [view, setView] = useState<View>('graph')
  const [selected, setSelected] = useState<string | null>(null)
  const [highlight, setHighlight] = useState<Set<string>>(new Set())
  const [show, setShow] = useState({ queries: false, challenges: true })
  const findings = useMemo(() => exp.data?.report?.findings ?? [], [exp.data])
  const flow = useMemo(() => (ev.data ? layout(ev.data.graph, findings, highlight, selected, show) : { nodes: [], edges: [] }),
    [ev.data, findings, highlight, selected, show])
  const node = ev.data?.graph.nodes.find((n) => n.id === selected)
  const linked = ev.data && node ? ev.data.graph.edges.filter((e) => e.source === node.id)
    .map((e) => ev.data.graph.nodes.find((n) => n.id === e.target)!).filter((n) => n && n.data.kind === 'query') : []
  const highlightClaim = (ids: string[]) => {
    setHighlight(new Set(ids))
    if (ids.some((i) => ev.data?.graph.nodes.find((n) => n.id === i)?.data.kind === 'query')) setShow((s) => ({ ...s, queries: true }))
  }
  const toggle = (k: keyof typeof show) => (
    <button onClick={() => setShow((s) => ({ ...s, [k]: !s[k] }))}
      className={`rounded border px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider ${show[k] ? 'border-accent/50 bg-accent/10 text-accent' : 'border-line text-dim hover:text-muted'}`}>
      {show[k] ? '✓ ' : ''}{k === 'queries' ? 'SQL nodes' : 'challenge nodes'}
    </button>
  )
  const top = [...findings].filter((f) => SUPPORTED.has(f.status)).sort((a, b) => b.share_of_delta - a.share_of_delta)[0]
  const battery = findings.flatMap((f) => f.challenges.map((c) => ({ ...c, finding: f })))
  const counts = ev.data ? {
    query: ev.data.graph.nodes.filter((n) => n.data.kind === 'query').length,
    finding: ev.data.graph.nodes.filter((n) => n.data.kind === 'finding').length,
    challenge: ev.data.graph.nodes.filter((n) => n.data.kind === 'challenge').length,
    contra: ev.data.graph.edges.filter((e) => e.label === 'contradicted_by').length,
  } : null

  return (
    <>
      <PageHeader crumbs={['Workspace', 'Evidence graph']} title="Evidence graph"
        subtitle="Har claim → finding → SQL query (checksum) tak trace. Node par click = poori provenance.">
        <ExperimentPicker />
      </PageHeader>
      {!id && <Empty icon={<Network className="h-8 w-8" />} title="Koi experiment select nahi">Pehle Investigations page se “kyun?” wala sawaal chalao.</Empty>}
      {id && exp.data && exp.data.status !== 'completed' && <Empty title={`Experiment ${exp.data.status}`}>Graph run complete hone ke baad banta hai.</Empty>}

      {ev.data && counts && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs value={view} onChange={setView} items={[
              { value: 'graph', label: 'Graph topology' }, { value: 'battery', label: `Challenge battery (${battery.length})` },
              { value: 'claims', label: `Claim provenance (${ev.data.claims.length})` }]} />
            <div className="flex flex-wrap gap-1.5 font-mono text-[11px]">
              <Badge>{counts.query} queries</Badge><Badge>{counts.finding} findings</Badge><Badge>{counts.challenge} challenges</Badge>
              <Badge tone={counts.contra ? 'red' : 'green'}>{counts.contra} contradicted_by</Badge>
            </div>
          </div>

          {view === 'graph' && (
            <div className="flex flex-col gap-4">
              <Card pad={false} className="p-2">
                <div className="flex flex-wrap items-center justify-between gap-2 px-2 pb-2 pt-1">
                  <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-[0.12em] text-dim">
                    <span>insight / facts</span><span>→ findings</span><span>→ drill-down</span>{show.challenges && <span>→ challenges</span>}{show.queries && <span>→ SQL evidence</span>}
                  </div>
                  <div className="flex gap-1.5">{toggle('challenges')}{toggle('queries')}</div>
                </div>
                <EvidenceGraphView key={`${show.queries}-${show.challenges}`} nodes={flow.nodes} edges={flow.edges} height={680}
                  onNodeClick={(_, n) => setSelected(n.id)} />
                {!show.queries && <p className="px-2 pt-2 text-[12px] text-dim">Finding par click karo — uske linked SQL queries provenance panel me milenge (ya “SQL nodes” on karo).</p>}
              </Card>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
                <div className="flex flex-col gap-4">
                  {node ? <Provenance node={node} linked={linked} onPick={setSelected} onClose={() => setSelected(null)} />
                    : <Card label="Node provenance"><p className="text-sm text-dim">Graph me kisi node par click karo — SQL, metric definition, filters, time window, dataset version aur checksum yahan dikhega.</p></Card>}
                </div>
                {top && <GatedScore f={top} />}
                <Card label="Claims → highlight evidence" className="lg:col-span-2 xl:col-span-1">
                  <div className="max-h-[560px] overflow-y-auto pr-1">
                    <ClaimsList claims={ev.data.claims} onSelect={highlightClaim} />
                  </div>
                  {highlight.size > 0 && <button onClick={() => setHighlight(new Set())} className="mt-2 font-mono text-[11px] text-accent hover:underline">clear highlight</button>}
                </Card>
              </div>
            </div>
          )}

          {view === 'battery' && (
            <Card title="Challenge battery" icon={<Swords className="h-4 w-4" />} label="Top findings par automatic 7-check battery + user challenges"
              actions={<Button variant="secondary" onClick={() => navigate('/challenge')}><Swords className="h-4 w-4" />Challenge a finding</Button>}>
              {battery.length === 0 && <p className="text-sm text-dim">Is run me koi challenge nahi chala.</p>}
              <div className="-mx-4 overflow-x-auto sm:-mx-5">
                <table className="tbl">
                  <thead><tr><th>Finding</th><th>Test</th><th>What it checks</th><th>Observed</th><th>Verdict</th></tr></thead>
                  <tbody>
                    {battery.map((c, i) => (
                      <tr key={i}>
                        <td className="font-mono text-[12px] text-accent">{keyLabel(c.finding.key)}</td>
                        <td className="whitespace-nowrap font-mono text-[12px] text-ink">{c.type}</td>
                        <td className="min-w-[220px] text-[12.5px] text-muted">{TEST_DESC[c.type] ?? '—'}</td>
                        <td className="min-w-[200px] font-mono text-[11.5px] text-muted">{c.detail}</td>
                        <td><Badge tone={c.passed ? 'green' : 'red'}>{c.passed ? 'pass' : 'fail'}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {view === 'claims' && (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
              <Card title="Claim provenance ledger" icon={<FileCheck2 className="h-4 w-4" />} label="Har sentence ke saath evidence node ids">
                <ClaimsList claims={ev.data.claims} onSelect={(ids) => { setHighlight(new Set(ids)); setView('graph') }} />
              </Card>
              <Card label="SQL evidence" title={`${ev.data.queries.length} queries`} icon={<GitBranch className="h-4 w-4" />}>
                <ul className="flex max-h-[520px] flex-col gap-1 overflow-y-auto">
                  {ev.data.queries.map((q) => (
                    <li key={q.id}>
                      <button onClick={() => { setSelected(q.id); setView('graph') }} className="w-full rounded px-2 py-1.5 text-left hover:bg-white/5">
                        <div className="flex items-center gap-2 font-mono text-[11.5px]"><span className="text-accent">{q.id}</span><span className="truncate text-ink">{q.purpose}</span></div>
                        <div className="font-mono text-[10.5px] text-dim">{q.row_count} rows · {q.checksum.slice(0, 16)}…</div>
                      </button>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>
          )}
        </div>
      )}
    </>
  )
}
