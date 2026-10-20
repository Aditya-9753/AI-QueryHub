import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Lock, RefreshCw, Table2 } from 'lucide-react'
import { SchemaAPI } from '../../services/api'
import { errorMessage } from '../../utils/format'

/** Live schema viewer — role-filtered (app tables hidden, sensitive columns locked). */
export default function SchemaExplorer({ datasourceId, detailed = false }: { datasourceId: string; detailed?: boolean }) {
  const qc = useQueryClient()
  const [refreshing, setRefreshing] = useState(false)
  const { data, isLoading, error } = useQuery({
    queryKey: ['schema', datasourceId],
    queryFn: () => SchemaAPI.get(datasourceId),
    staleTime: 5 * 60_000,
  })

  const refresh = async () => {
    setRefreshing(true)
    try {
      qc.setQueryData(['schema', datasourceId], await SchemaAPI.get(datasourceId, true))
    } finally {
      setRefreshing(false)
    }
  }

  if (isLoading) return <p className="text-sm text-dim">Schema load ho raha hai…</p>
  if (error) return <p className="text-sm text-bad">{errorMessage(error)}</p>
  if (!data) return null

  return (
    <div className="flex flex-col gap-2 text-sm">
      <div className="flex items-center justify-between">
        <span className="label">{data.tables.length} tables · {data.dialect}</span>
        <button onClick={refresh} disabled={refreshing} className="flex items-center gap-1 font-mono text-[11px] text-muted hover:text-accent" title="Re-scan schema">
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />refresh
        </button>
      </div>
      {data.tables.length === 0 && <p className="text-dim">Is datasource me aapke role ke liye koi table nahi.</p>}
      <div className={detailed ? 'grid gap-2 md:grid-cols-2' : 'flex flex-col gap-2'}>
        {data.tables.map((t, i) => (
          <details key={t.name} open={detailed || i === 0} className="rounded-md border border-line bg-panel2/50 px-3 py-2">
            <summary className="flex cursor-pointer items-center gap-2 font-mono text-[13px] font-medium text-ink">
              <Table2 className="h-4 w-4 text-accent" />{t.name}
              <span className="ml-auto text-[11px] font-normal text-dim">{t.columns.length} cols</span>
            </summary>
            <ul className="mt-2 flex flex-col gap-1.5 pb-1">
              {t.columns.map((c) => (
                <li key={c.name} className="text-muted">
                  <span className="font-mono text-xs text-ink">{c.name}</span>
                  {c.sensitive && <Lock className="ml-1 inline h-3 w-3 text-warn" aria-label="sensitive — blocked for your role" />}
                  {detailed && <span className="ml-2 font-mono text-[11px] text-dim">{c.type}</span>}
                  {detailed && c.min && <span className="ml-2 font-mono text-[11px] text-dim">{c.min.slice(0, 10)} → {c.max?.slice(0, 10)}</span>}
                  {detailed && c.values.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {c.values.slice(0, 12).map((v) => <span key={v} className="rounded border border-line px-1.5 font-mono text-[10.5px] text-muted">{v}</span>)}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </div>
  )
}
