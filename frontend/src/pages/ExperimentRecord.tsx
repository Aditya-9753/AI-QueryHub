import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Download, History, RefreshCcw, RotateCcw } from 'lucide-react'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import Empty from '../components/common/Empty'
import PageHeader from '../components/common/PageHeader'
import SqlBlock from '../components/common/SqlBlock'
import StatTile from '../components/common/StatTile'
import ExperimentPicker from '../components/qtrace/ExperimentPicker'
import Timeline from '../components/qtrace/Timeline'
import { StatusChip, keyLabel, pct } from '../components/qtrace/badges'
import { useExperiment } from '../hooks/useExperiment'
import { InvestigateAPI } from '../services/qtrace'
import { useRole } from '../hooks/useRole'
import { useAppStore } from '../store/useAppStore'
import { errorMessage } from '../utils/format'

export default function ExperimentRecord() {
  const id = useAppStore((s) => s.currentExperimentId)
  const { data } = useExperiment(id)
  const { can, isAdmin, userId } = useRole()
  const owns = isAdmin || (!!data?.user_id && data.user_id === userId)
  const [open, setOpen] = useState<string | null>(null)
  const replay = useMutation({ mutationFn: (mode: 'exact' | 'rederive') => InvestigateAPI.replay(id!, mode) })
  const exportF = useMutation({ mutationFn: (f: 'json' | 'pdf') => InvestigateAPI.exportFile(id!, f) })
  const r = replay.data

  return (
    <>
      <PageHeader crumbs={['Workspace', 'Runs & replays']} title="Experiment record"
        subtitle="Versions, har SQL ka checksum, timeline, replay (exact vs re-derive), export">
        <ExperimentPicker />
      </PageHeader>
      {!data && <Empty icon={<History className="h-8 w-8" />} title="Experiment chuno">Upar picker se koi run select karo.</Empty>}
      {data && (
        <div className="flex flex-col gap-4">
          <Card label={`EXP-${data.id.slice(0, 6).toUpperCase()}`} title={`“${data.question}”`} actions={
            <div className="flex flex-wrap gap-2">
              {can.replay && <Button variant="secondary" onClick={() => replay.mutate('exact')} disabled={replay.isPending || !data.run}><RotateCcw className="h-4 w-4" />Exact replay</Button>}
              {can.replay && owns && <Button variant="secondary" onClick={() => replay.mutate('rederive')} disabled={replay.isPending || !data.run}><RefreshCcw className="h-4 w-4" />Re-derive</Button>}
              <Button variant="ghost" onClick={() => exportF.mutate('json')} disabled={!data.run}><Download className="h-4 w-4" />JSON</Button>
              <Button variant="ghost" onClick={() => exportF.mutate('pdf')} disabled={!data.run}><Download className="h-4 w-4" />PDF</Button>
            </div>}>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
              <StatTile label="Status" value={<StatusChip status={data.status} />} />
              <StatTile label="Duration" value={data.run?.duration_ms ? `${(data.run.duration_ms / 1000).toFixed(2)}s` : '—'} />
              <StatTile label="SQL queries" value={data.report?.queries.length ?? '—'} />
              <StatTile label="Dataset version" value={<span className="text-xs">{data.run?.dataset_version ?? '—'}</span>} />
              <StatTile label="Model version" value={<span className="text-xs">{data.run?.model_version ?? '—'}</span>} />
              <StatTile label="Semantic layer" value={<span className="text-xs">{data.run?.semantic_layer_version ?? '—'}</span>} />
            </div>
            {(replay.isError || exportF.isError) && <p className="mt-2 text-sm text-bad">{errorMessage(replay.error ?? exportF.error)}</p>}
          </Card>

          {r?.warnings?.map((w) => <Card key={w} className="border-warn/40 bg-warn/5"><p className="text-sm text-warn">{w}</p></Card>)}
          {r && r.mode === 'exact' && (
            <Card label="Exact replay" title={<span className="flex items-center gap-2">Same SQL, same data <Badge tone={r.match ? 'green' : 'red'}>{r.matched}/{r.queries} checksums match</Badge></span>}>
              <ul className="flex max-h-72 flex-col gap-0.5 overflow-y-auto">{r.details?.map((d, i) => (
                <li key={i} className="flex items-center gap-2 font-mono text-[11.5px]"><Badge tone={d.match ? 'green' : 'red'}>{d.match ? 'match' : 'diff'}</Badge>
                  <span className="min-w-0 flex-1 truncate text-ink">{d.purpose}</span><span className="hidden text-dim sm:inline">{d.original.slice(0, 16)}…</span></li>))}</ul>
            </Card>
          )}
          {r && r.mode === 'rederive' && (
            <Card label="Re-derive" title={<span className="flex items-center gap-2">Pipeline dobara chala <Badge tone={r.stable ? 'green' : 'amber'}>{r.stable ? 'stable' : 'changed'}</Badge></span>}>
              <div className="overflow-x-auto"><table className="tbl">
                <thead><tr><th>Finding</th><th>Status old → new</th><th className="text-right">Share old → new</th><th /></tr></thead>
                <tbody>
                  {r.findings?.map((f) => (
                    <tr key={f.key}><td className="font-mono text-xs text-accent">{keyLabel(f.key)}</td>
                      <td className="whitespace-nowrap">{f.status_old ? <StatusChip status={f.status_old} /> : '—'} <span className="text-dim">→</span> {f.status_new ? <StatusChip status={f.status_new} /> : '—'}</td>
                      <td className="num text-right text-muted">{pct(f.share_old)} → {pct(f.share_new)}</td>
                      <td>{f.same ? <Badge tone="green">same</Badge> : <Badge tone="amber">≠</Badge>}</td></tr>))}
                </tbody>
              </table></div>
            </Card>
          )}

          {data.report && (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
              <Card label="Sirf aggregates + SHA-256 — raw rows store nahi" title={`Queries (${data.report.queries.length})`} pad={false}>
                <ul className="max-h-[560px] divide-y divide-line overflow-y-auto">
                  {data.report.queries.map((q) => (
                    <li key={q.id}>
                      <button onClick={() => setOpen(open === q.id ? null : q.id)} className="flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-white/5 sm:px-5">
                        {open === q.id ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-dim" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-dim" />}
                        <span className="font-mono text-[11.5px] text-accent">{q.id}</span>
                        <span className="min-w-0 flex-1 truncate text-[13px] text-ink">{q.purpose}</span>
                        <span className="font-mono text-[11px] text-dim">{q.row_count} rows</span>
                      </button>
                      {open === q.id && (
                        <div className="px-4 pb-3 sm:px-5">
                          <SqlBlock sql={q.sql} maxHeight={220} />
                          <div className="mt-1.5 break-all font-mono text-[10.5px] text-dim">sha256 {q.checksum} · {q.duration_ms.toFixed(0)} ms</div>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </Card>
              <Card label="experiment_steps" title="Timeline">{data.report.steps ? <Timeline steps={data.report.steps} /> : <p className="text-sm text-dim">Is run ke steps record nahi hue.</p>}</Card>
            </div>
          )}
        </div>
      )}
    </>
  )
}
