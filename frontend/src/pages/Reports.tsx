import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, Star, Trash2 } from 'lucide-react'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import DataTable from '../components/common/DataTable'
import Empty from '../components/common/Empty'
import PageHeader from '../components/common/PageHeader'
import ResultChart from '../components/charts/ResultChart'
import { SavedAPI } from '../services/api'
import { errorMessage } from '../utils/format'

export default function Reports() {
  const qc = useQueryClient()
  const saved = useQuery({ queryKey: ['saved'], queryFn: SavedAPI.list })
  const run = useMutation({ mutationFn: (id: string) => SavedAPI.run(id) })
  const remove = useMutation({
    mutationFn: (id: string) => SavedAPI.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['saved'] }),
  })

  return (
    <>
      <PageHeader crumbs={['Data', 'Saved queries']} title="Saved queries"
        subtitle="Saved SQL dobara chalao — LLM call nahi, firewall har baar" />
      {saved.error && <p className="mb-3 text-sm text-bad">{errorMessage(saved.error)}</p>}
      {saved.data?.length === 0 && <Empty icon={<Star className="h-8 w-8" />} title="Abhi kuch saved nahi">Ask & Analyze page par “Save” dabao.</Empty>}
      {!!saved.data?.length && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card label={`${saved.data.length} saved`} pad={false}>
            <ul className="divide-y divide-line">
              {saved.data.map((s) => (
                <li key={s.id} className={`flex items-start gap-3 px-4 py-3 sm:px-5 ${run.variables === s.id ? 'bg-accent/5' : ''}`}>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink">{s.name}<Badge>{s.mode}</Badge></div>
                    <div className="mt-1 truncate font-mono text-[11px] text-dim">{s.sql}</div>
                  </div>
                  <Button variant="secondary" onClick={() => run.mutate(s.id)} disabled={run.isPending}><Play className="h-4 w-4" />Run</Button>
                  <button onClick={() => remove.mutate(s.id)} className="rounded p-2 text-dim hover:bg-bad/10 hover:text-bad" aria-label="Delete"><Trash2 className="h-4 w-4" /></button>
                </li>
              ))}
            </ul>
          </Card>
          <Card label="Result" title={run.data ? run.data.question : 'Kisi saved query par Run dabao'}>
            {run.isError && <p className="text-sm text-bad">{errorMessage(run.error)}</p>}
            {run.data && (
              <div className="flex flex-col gap-4">
                <p className="text-ink">{run.data.answer}</p>
                <ResultChart columns={run.data.columns} rows={run.data.rows} height={240} />
                <DataTable columns={run.data.columns} rows={run.data.rows} maxHeight={260} />
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  )
}
