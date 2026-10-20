import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Database, Lock, PlugZap, Trash2, XCircle } from 'lucide-react'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import SchemaExplorer from '../components/schema-explorer/SchemaExplorer'
import { useRole } from '../hooks/useRole'
import { DataSourceAPI } from '../services/api'
import type { ConnectionTest, DataSource } from '../services/types'
import { useAppStore } from '../store/useAppStore'
import { errorMessage } from '../utils/format'

const EMPTY = { name: '', kind: 'postgres' as DataSource['kind'], conn_secret_ref: 'DS_' }

export default function Datasources() {
  const qc = useQueryClient()
  const { isAdmin } = useRole()
  const { datasourceId, setDatasourceId } = useAppStore()
  const [tests, setTests] = useState<Record<string, ConnectionTest>>({})
  const [form, setForm] = useState(EMPTY)

  const list = useQuery({ queryKey: ['datasources'], queryFn: DataSourceAPI.list })
  const test = useMutation({
    mutationFn: (id: string) => DataSourceAPI.test(id),
    onSuccess: (r, id) => setTests((t) => ({ ...t, [id]: r })),
  })
  const create = useMutation({
    mutationFn: () => DataSourceAPI.create(form),
    onSuccess: (ds) => {
      qc.invalidateQueries({ queryKey: ['datasources'] })
      setForm(EMPTY)
      test.mutate(ds.id)
    },
  })
  const remove = useMutation({
    mutationFn: (id: string) => DataSourceAPI.remove(id),
    onSuccess: (_, id) => {
      if (id === datasourceId) setDatasourceId('default')
      qc.invalidateQueries({ queryKey: ['datasources'] })
    },
  })

  const active = list.data?.find((d) => d.id === datasourceId) ?? list.data?.[0]
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate()
  }

  return (
    <>
      <PageHeader crumbs={['Data', 'Database']} title="Database"
        subtitle="Connections aur live schema — har query read-only connection par, aapke role ke hisaab se filtered" />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card label="Connections" title={`${list.data?.length ?? 0} data sources`} icon={<Database className="h-4 w-4" />}>
          {list.error && <p className="text-sm text-bad">{errorMessage(list.error)}</p>}
          <ul className="flex flex-col gap-2">
            {list.data?.map((ds) => {
              const t = tests[ds.id]
              const isActive = ds.id === active?.id
              return (
                <li key={ds.id} className={`flex flex-wrap items-center gap-3 rounded-md border p-3 ${isActive ? 'border-accent/40 bg-accent/5' : 'border-line'}`}>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
                      {ds.name}<Badge>{ds.kind}</Badge>{isActive && <Badge tone="solid">active</Badge>}{ds.is_default && <Badge tone="blue">demo</Badge>}
                    </div>
                    <div className="mt-0.5 font-mono text-[11px] text-dim">{ds.conn_secret_ref}</div>
                    {t && (
                      <div className={`mt-1 flex items-center gap-1 font-mono text-[11px] ${t.ok ? 'text-ok' : 'text-bad'}`}>
                        {t.ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                        {t.ok ? `connected · ${t.dialect} · ${t.tables} tables · ${t.duration_ms} ms` : t.error}
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="secondary" onClick={() => test.mutate(ds.id)} disabled={test.isPending && test.variables === ds.id}><PlugZap className="h-4 w-4" />Test</Button>
                    {!isActive && <Button variant="secondary" onClick={() => setDatasourceId(ds.id)}>Use</Button>}
                    {isAdmin && !ds.is_default && (
                      <button onClick={() => remove.mutate(ds.id)} className="rounded p-2 text-dim hover:bg-bad/10 hover:text-bad" aria-label="Delete"><Trash2 className="h-4 w-4" /></button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        </Card>

        {isAdmin ? (
          <Card label="Admin" title="Add connection">
            <form onSubmit={onSubmit} className="flex flex-col gap-3 text-sm">
              <label className="label">Name<input className="input mt-1 normal-case tracking-normal" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Sales DB" /></label>
              <label className="label">Type
                <select className="input mt-1 normal-case tracking-normal" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as DataSource['kind'] })}>
                  <option value="postgres">PostgreSQL</option><option value="sqlite">SQLite</option>
                </select>
              </label>
              <label className="label">Env var name
                <input className="input mt-1 font-mono normal-case tracking-normal" required pattern="DS_[A-Z0-9_]+" value={form.conn_secret_ref}
                  onChange={(e) => setForm({ ...form, conn_secret_ref: e.target.value.toUpperCase() })} />
              </label>
              <p className="text-xs leading-relaxed text-dim">
                Password / URL yahan <b className="text-warn">kabhi</b> mat daalo. Backend <code>.env</code> me likho, e.g.{' '}
                <code className="break-all text-muted">DS_SALES_URL=postgresql+psycopg://queryhub_ro:***@host:5432/db</code>, server restart karo,
                phir yahan sirf <code className="text-muted">DS_SALES_URL</code> daalo. Read-only DB user use karo.
              </p>
              {create.isError && <p className="text-bad">{errorMessage(create.error)}</p>}
              <Button type="submit" disabled={create.isPending}>Add &amp; test</Button>
            </form>
          </Card>
        ) : (
          <Card label="Governance" title="Connections admin manage karta hai" icon={<Lock className="h-4 w-4" />}>
            <p className="text-sm text-muted">Aap connections test kar sakte ho aur active source chun sakte ho. Naya database jodna / hatana sirf admin ke paas hai.</p>
          </Card>
        )}
      </div>

      <Card label="Schema (role-filtered)" title={active?.name ?? '…'} className="mt-4">
        {active && <SchemaExplorer datasourceId={active.id} detailed />}
      </Card>
    </>
  )
}
