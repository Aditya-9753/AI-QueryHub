import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Lock, Pencil, Save, X } from 'lucide-react'
import Badge from '../components/common/Badge'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import { useRole } from '../hooks/useRole'
import { api, MetricsAPI } from '../services/api'
import type { MetricDefinition } from '../services/types'
import { errorMessage } from '../utils/format'

/** Business metrics ki official definitions. Admin edit -> version++ -> ASK + INVESTIGATE dono naya formula use
 * karte hain; purane runs ke replay me "definition badli" warning aati hai (Ch 17). */
export default function SemanticLayer() {
  const qc = useQueryClient()
  const { isAdmin } = useRole()
  const { data, error } = useQuery({ queryKey: ['metrics'], queryFn: MetricsAPI.list })
  const [edit, setEdit] = useState<MetricDefinition | null>(null)
  const save = useMutation({
    mutationFn: (m: MetricDefinition) =>
      api.post('/api/metrics', { name: m.name, definition: m.definition, formula_sql: m.formula_sql, grain: m.grain }),
    onSuccess: () => {
      setEdit(null)
      qc.invalidateQueries({ queryKey: ['metrics'] })
    },
  })

  return (
    <>
      <PageHeader crumbs={['Data', 'Semantic layer']} title="Semantic layer"
        subtitle="Business metrics ki official SQL definitions — LLM formula nahi likhta, sirf metric ka naam chunta hai">
        {isAdmin ? <Badge tone="blue">admin · edit enabled</Badge> : <Badge><Lock className="mr-1 h-3 w-3" />read-only</Badge>}
      </PageHeader>
      {error && <p className="mb-3 text-sm text-bad">{errorMessage(error)}</p>}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {data?.map((m) => {
          const editing = edit?.id === m.id
          return (
            <Card key={m.id} className={editing ? 'border-accent/50' : ''} label={`grain · ${m.grain}`}
              title={<span className="font-mono text-accent">{m.name}</span>} icon={<BookOpen className="h-4 w-4" />}
              actions={<div className="flex items-center gap-1.5">
                <Badge>v{m.version}</Badge>
                {isAdmin && !editing && <button onClick={() => setEdit(m)} className="rounded p-1.5 text-dim hover:bg-white/5 hover:text-accent" aria-label="Edit"><Pencil className="h-4 w-4" /></button>}
                {editing && <>
                  <button onClick={() => save.mutate(edit)} className="rounded p-1.5 text-ok hover:bg-ok/10" aria-label="Save"><Save className="h-4 w-4" /></button>
                  <button onClick={() => { setEdit(null); save.reset() }} className="rounded p-1.5 text-dim hover:bg-white/5" aria-label="Cancel"><X className="h-4 w-4" /></button>
                </>}
              </div>}>
              {editing ? (
                <div className="flex flex-col gap-2">
                  <label className="label">Definition<input className="input mt-1 normal-case tracking-normal" value={edit.definition} onChange={(e) => setEdit({ ...edit, definition: e.target.value })} /></label>
                  <label className="label">Formula SQL<textarea rows={3} className="input mt-1 font-mono text-xs normal-case tracking-normal" value={edit.formula_sql} onChange={(e) => setEdit({ ...edit, formula_sql: e.target.value })} /></label>
                  {save.isError && <p className="text-sm text-bad">{errorMessage(save.error)}</p>}
                  <p className="text-xs text-dim">Save se pehle formula render hokar 4-layer SQL firewall se check hota hai.</p>
                </div>
              ) : (
                <>
                  <p className="text-[13.5px] text-muted">{m.definition}</p>
                  <pre className="mt-3 overflow-x-auto rounded-md border border-line bg-bg p-2.5 font-mono text-[12px] text-ink">{m.formula_sql}</pre>
                </>
              )}
            </Card>
          )
        })}
      </div>
      {!isAdmin && <p className="mt-4 text-xs text-dim">Definitions sirf admin badal sakta hai — badalne par version++ hota hai aur purane runs ke replay me warning aati hai.</p>}
    </>
  )
}
