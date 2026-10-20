import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Swords } from 'lucide-react'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import Empty from '../components/common/Empty'
import PageHeader from '../components/common/PageHeader'
import ScoreBar from '../components/common/ScoreBar'
import ExperimentPicker from '../components/qtrace/ExperimentPicker'
import { LabelChip, StatusChip, keyLabel, pct } from '../components/qtrace/badges'
import { InvestigateAPI } from '../services/qtrace'
import { useAppStore } from '../store/useAppStore'
import { errorMessage, timeAgo } from '../utils/format'
import { TEST_DESC } from './EvidenceGraph'

const TYPES = ['battery', 'seasonality', 'calendar', 'data_quality', 'small_sample', 'alternative_segment', 'simpson', 'market_wide', 'custom']
interface Check { type?: string; passed?: boolean; detail?: string; statement?: string; status?: string; share?: number }

export default function ChallengeView() {
  const qc = useQueryClient()
  const id = useAppStore((s) => s.currentExperimentId)
  const findings = useQuery({ queryKey: ['findings', id], queryFn: () => InvestigateAPI.findings(id!), enabled: !!id })
  const [selected, setSelected] = useState<string | null>(null)
  const [type, setType] = useState('battery')
  const [desc, setDesc] = useState('')
  const f = findings.data?.find((x) => x.id === selected) ?? findings.data?.find((x) => x.challenges.length > 0) ?? findings.data?.[0]
  const challenge = useMutation({
    mutationFn: () => InvestigateAPI.challenge(f!.id, type, type === 'custom' ? desc : undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['findings', id] }),
  })

  return (
    <>
      <PageHeader crumbs={['Workspace', 'Challenge']} title="Challenge"
        subtitle="Kisi bhi finding ko counter-test karo. Result naye record me jaata hai — original finding overwrite nahi hoti.">
        <ExperimentPicker />
      </PageHeader>
      {!id && <Empty icon={<Swords className="h-8 w-8" />} title="Koi experiment select nahi">Pehle investigation chalao.</Empty>}
      {id && findings.data?.length === 0 && <Empty title="Is run me koi finding nahi">Gate ne anomaly nahi pakdi ya data issue tha.</Empty>}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
        {!!findings.data?.length && (
          <Card label={`Findings (${findings.data.length})`} pad={false} className="p-2">
            <ul className="flex max-h-[70vh] flex-col gap-0.5 overflow-y-auto">
              {findings.data.map((x) => (
                <li key={x.id}>
                  <button onClick={() => setSelected(x.id)}
                    className={`w-full rounded-md border px-3 py-2 text-left transition ${x.id === f?.id ? 'border-accent/40 bg-accent/5' : 'border-transparent hover:bg-white/5'}`}>
                    <div className="flex flex-wrap items-center gap-1.5"><StatusChip status={x.status} /><LabelChip label={x.label} />
                      <span className="ml-auto font-mono text-[11px] text-muted">{pct(x.share)}</span></div>
                    <div className="mt-1 font-mono text-[11.5px] text-accent">{keyLabel(x.key)}</div>
                    <div className="truncate text-[13px] text-muted">{x.statement}</div>
                    {x.challenges.length > 0 && <div className="mt-1 font-mono text-[10.5px] text-dim">{x.challenges.length} challenge records</div>}
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        )}
        {f && (
          <div className="flex min-w-0 flex-col gap-4">
            <Card label="Selected finding" title={f.statement} icon={<Swords className="h-4 w-4" />}>
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <StatusChip status={f.status} /><LabelChip label={f.label} />
                <span className="font-mono text-xs text-muted">share {pct(f.share)}</span>
                <ScoreBar value={f.score} />
              </div>
              <div className="flex flex-col gap-2 md:flex-row md:items-center">
                <select value={type} onChange={(e) => setType(e.target.value)} className="input md:w-56">
                  {TYPES.map((t) => <option key={t} value={t}>{t === 'battery' ? 'full battery (7 checks)' : t}</option>)}
                </select>
                {type === 'custom' && <input value={desc} onChange={(e) => setDesc(e.target.value)} className="input flex-1"
                  placeholder="Aapka alternative explanation — LLM counter-hypotheses banayega, sab SQL se test" />}
                <Button onClick={() => challenge.mutate()} disabled={challenge.isPending || (type === 'custom' && !desc.trim())}>
                  <Swords className="h-4 w-4" />{challenge.isPending ? 'Testing…' : 'Challenge this finding'}
                </Button>
              </div>
              {type !== 'custom' && type !== 'battery' && <p className="mt-2 text-xs text-dim">{TEST_DESC[type]}</p>}
              {challenge.isError && <p className="mt-2 text-sm text-bad">{errorMessage(challenge.error)}</p>}
            </Card>
            <Card label="Challenge records" title="Results">
              {f.challenges.length === 0 && <p className="text-sm text-dim">Abhi koi challenge nahi (auto battery sirf top findings par chalti hai).</p>}
              <div className="flex flex-col gap-3">
                {f.challenges.map((c) => {
                  const checks = (c.result as { checks?: Check[] } | null)?.checks ?? (Array.isArray(c.result) ? (c.result as Check[]) : [])
                  return (
                    <div key={c.id} className="rounded-md border border-line bg-panel2/60 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={c.origin === 'user' ? 'blue' : 'grey'}>{c.origin}</Badge>
                        <span className="font-mono text-[12px] text-ink">{c.type}</span>
                        <StatusChip status={c.status} />
                      </div>
                      {checks.length === 0 && (c.result as { detail?: string } | null)?.detail && (
                        <p className="mt-2 font-mono text-[11.5px] text-muted">{String((c.result as { detail?: string }).detail)}</p>
                      )}
                      {checks.length > 0 && (
                        <ul className="mt-2 divide-y divide-line">
                          {checks.map((k, i) => (
                            <li key={i} className="flex flex-wrap items-start gap-2 py-1.5 text-[12.5px]">
                              {k.passed !== undefined ? <Badge tone={k.passed ? 'green' : 'red'}>{k.passed ? 'pass' : 'fail'}</Badge> : k.status && <StatusChip status={k.status} />}
                              <span className="font-mono text-ink">{k.type ?? k.statement}</span>
                              <span className="min-w-0 flex-1 font-mono text-[11.5px] text-muted">{k.detail ?? (k.share !== undefined ? `share ${pct(k.share)}` : '')}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )
                })}
              </div>
            </Card>
          </div>
        )}
      </div>
      {findings.dataUpdatedAt > 0 && <p className="mt-3 font-mono text-[10.5px] text-dim">updated {timeAgo(new Date(findings.dataUpdatedAt).toISOString())}</p>}
    </>
  )
}
