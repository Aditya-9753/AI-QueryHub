import { useEffect, useState, type FormEvent } from 'react'
import Editor from '@monaco-editor/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { AlertTriangle, BookmarkPlus, FlaskConical, History, Play, ShieldAlert, Sparkles, Star } from 'lucide-react'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import DataTable from '../components/common/DataTable'
import PageHeader from '../components/common/PageHeader'
import Tabs from '../components/common/Tabs'
import ResultChart from '../components/charts/ResultChart'
import SchemaExplorer from '../components/schema-explorer/SchemaExplorer'
import { DataSourceAPI, QueryAPI, SavedAPI } from '../services/api'
import { InvestigateAPI } from '../services/qtrace'
import type { HistoryItem, QueryResult } from '../services/types'
import { useAppStore } from '../store/useAppStore'
import { errorDetail, errorMessage, timeAgo } from '../utils/format'

type ModeChoice = 'AUTO' | 'ASK' | 'ANALYZE'
interface RunVars { sql?: string }
interface RunError { message: string; status?: string; sql?: string | null }

const EXAMPLES: Record<ModeChoice, string[]> = {
  AUTO: ['February mein Delhi ka revenue kitna tha?', 'Feb 2026 me city-wise revenue', 'Feb me Delhi revenue kyun gira?'],
  ASK: ['February mein Delhi ka revenue kitna tha?', 'Pune me Feb 2026 ka cancellation rate kya tha?', 'Dec 2025 me UPI se kitna payment aaya?'],
  ANALYZE: ['Feb 2026 me city-wise revenue', '2025 me month-wise total revenue', 'Delhi revenue category-wise, Feb 2026'],
}
const STATUS_TONE: Record<string, 'green' | 'red' | 'amber' | 'grey'> = { ok: 'green', blocked: 'red', error: 'amber', llm_error: 'amber' }

export default function QueryWorkspace() {
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const urlMode = (params.get('mode') as ModeChoice | null) ?? 'AUTO'
  const { datasourceId, setDatasourceId, setCurrentExperimentId } = useAppStore()
  const navigate = useNavigate()
  const [question, setQuestion] = useState(EXAMPLES[urlMode]?.[0] ?? EXAMPLES.AUTO[0])
  const [mode, setMode] = useState<ModeChoice>(urlMode)
  const [sql, setSql] = useState('')
  const [result, setResult] = useState<QueryResult | null>(null)
  const [runError, setRunError] = useState<RunError | null>(null)
  const [view, setView] = useState<'chart' | 'table'>('chart')

  useEffect(() => { setMode(urlMode) }, [urlMode])
  const changeMode = (m: ModeChoice) => {
    setMode(m)
    setParams(m === 'AUTO' ? {} : { mode: m })
  }

  const datasources = useQuery({ queryKey: ['datasources'], queryFn: DataSourceAPI.list })
  const history = useQuery({ queryKey: ['history'], queryFn: () => QueryAPI.history(30) })
  const saved = useQuery({ queryKey: ['saved'], queryFn: SavedAPI.list })

  const onDone = {
    onMutate: () => setRunError(null),
    onSuccess: (r: QueryResult) => { setResult(r); setSql(r.sql); setQuestion(r.question) },
    onError: (e: unknown) => {
      const d = errorDetail(e)
      setResult(null)
      setRunError({ message: d?.message ?? errorMessage(e), status: d?.status, sql: d?.sql })
      if (d?.sql) setSql(d.sql)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['history'] }),
  }
  const run = useMutation({
    mutationFn: (v: RunVars) => QueryAPI.run({ question, mode: mode === 'AUTO' ? null : mode, sql: v.sql ?? null, datasource_id: datasourceId }),
    ...onDone,
  })
  const runSaved = useMutation({ mutationFn: (id: string) => SavedAPI.run(id), ...onDone })
  const save = useMutation({
    mutationFn: () => SavedAPI.create({ name: question.slice(0, 120), question, sql, mode: result?.mode === 'ANALYZE' ? 'ANALYZE' : 'ASK', datasource_id: datasourceId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['saved'] }),
  })
  const investigate = useMutation({
    mutationFn: async () => {
      const e = await InvestigateAPI.create(question, datasourceId)
      await InvestigateAPI.run(e.id)
      return e.id
    },
    onSuccess: (id) => { setCurrentExperimentId(id); navigate('/investigate') },
  })

  const busy = run.isPending || runSaved.isPending
  const ask = (e?: FormEvent) => {
    e?.preventDefault()
    if (question.trim()) run.mutate({})
  }
  const loadHistory = (h: HistoryItem) => { setQuestion(h.question); setSql(h.sql ?? '') }

  return (
    <>
      <PageHeader crumbs={['Workspace', mode === 'ANALYZE' ? 'Analyze' : 'Ask']} title="Ask & Analyze"
        subtitle="Sawaal → semantic layer + schema context → LLM SQL → 4-layer firewall → read-only result" />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-4">
          <Card>
            <form onSubmit={ask} className="flex flex-col gap-3">
              <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) ask(e) }}
                className="input resize-none text-base" placeholder="e.g. February mein Delhi ka revenue kitna tha?" />
              <div className="flex flex-wrap items-center gap-2">
                <Tabs value={mode} onChange={changeMode} items={[{ value: 'AUTO', label: 'Auto' }, { value: 'ASK', label: 'Ask' }, { value: 'ANALYZE', label: 'Analyze' }]} />
                <select value={datasourceId} onChange={(e) => setDatasourceId(e.target.value)} className="input w-auto py-1.5">
                  {datasources.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
                <div className="flex-1" />
                <Button type="submit" disabled={busy || !question.trim()}><Sparkles className="h-4 w-4" />{busy ? 'Thinking…' : 'Run'}</Button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(EXAMPLES[mode] ?? EXAMPLES.AUTO).map((ex) => (
                  <button key={ex} type="button" onClick={() => setQuestion(ex)}
                    className="rounded border border-line px-2 py-0.5 text-xs text-muted hover:border-accent/50 hover:text-accent">{ex}</button>
                ))}
              </div>
            </form>
          </Card>

          {runError && (
            <Card className="border-bad/40 bg-bad/5">
              <div className="flex items-start gap-2 text-sm text-bad">
                {runError.status === 'blocked' ? <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />}
                <div className="min-w-0">
                  <b>{runError.status === 'blocked' ? 'SQL firewall ne block kiya' : 'Query nahi chal paayi'}</b>
                  <div className="break-words text-muted">{runError.message}</div>
                </div>
              </div>
            </Card>
          )}

          {result && (
            <>
              <Card className="border-accent/30">
                <div className="label mb-1.5">Answer</div>
                <p className="text-lg leading-snug text-ink">{result.answer}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <Badge tone="solid">{result.mode}</Badge>
                  <Badge tone={result.answer_source === 'llm' ? 'green' : 'grey'}>{result.answer_source === 'llm' ? 'AI answer · numbers verified' : 'answer from result'}</Badge>
                  <Badge>{result.generated ? `AI SQL · ${result.attempts} attempt${result.attempts > 1 ? 's' : ''}` : 'manual SQL'}</Badge>
                  <Badge>{result.row_count} rows · {result.duration_ms} ms</Badge>
                </div>
                {result.warnings.map((w) => (
                  <p key={w} className="mt-3 flex items-start gap-1.5 text-sm text-warn"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{w}</p>
                ))}
                {result.warnings.length > 0 && (
                  <Button variant="secondary" className="mt-3" onClick={() => investigate.mutate()} disabled={investigate.isPending}>
                    <FlaskConical className="h-4 w-4" />Investigate karo (Q-TRACE+)
                  </Button>
                )}
              </Card>
              <Card label="Result" actions={<Tabs size="sm" value={view} onChange={setView} items={[{ value: 'chart', label: 'Chart' }, { value: 'table', label: 'Table' }]} />}>
                {view === 'chart' ? <ResultChart columns={result.columns} rows={result.rows} /> : <DataTable columns={result.columns} rows={result.rows} />}
                {result.row_count > result.rows.length && <p className="mt-2 text-xs text-dim">Pehli {result.rows.length} rows (total {result.row_count}).</p>}
              </Card>
            </>
          )}

          <Card label="Validated SQL" title="Monaco editor" actions={
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => save.mutate()} disabled={!sql.trim() || save.isPending}>
                <BookmarkPlus className="h-4 w-4" />{save.isSuccess ? 'Saved' : 'Save'}
              </Button>
              <Button variant="secondary" onClick={() => run.mutate({ sql })} disabled={!sql.trim() || busy}><Play className="h-4 w-4" />Run SQL</Button>
            </div>}>
            <div className="overflow-hidden rounded-md border border-line">
              <Editor height="190px" defaultLanguage="sql" theme="vs-dark" value={sql} onChange={(v) => setSql(v ?? '')}
                options={{ minimap: { enabled: false }, fontSize: 13, fontFamily: 'JetBrains Mono', wordWrap: 'on', scrollBeyondLastLine: false }} />
            </div>
            {save.isError && <p className="mt-2 text-sm text-bad">{errorMessage(save.error)}</p>}
            {result && <p className="mt-2 break-all font-mono text-[10.5px] text-dim">sha256(rows) {result.checksum}</p>}
            <p className="mt-1 text-xs text-dim">Edit karke “Run SQL” — ye bhi firewall se guzarta hai (LLM skip).</p>
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          <Card label="Saved" icon={<Star className="h-4 w-4" />}>
            {saved.data?.length === 0 && <p className="text-sm text-dim">Abhi kuch saved nahi.</p>}
            <ul className="flex flex-col gap-0.5">
              {saved.data?.slice(0, 8).map((s) => (
                <li key={s.id}><button onClick={() => runSaved.mutate(s.id)} className="w-full truncate rounded px-2 py-1.5 text-left text-sm text-muted hover:bg-white/5 hover:text-ink" title="Run">{s.name}</button></li>
              ))}
            </ul>
          </Card>
          <Card label="History" icon={<History className="h-4 w-4" />}>
            <ul className="flex max-h-96 flex-col gap-0.5 overflow-y-auto">
              {history.data?.map((h) => (
                <li key={h.id}>
                  <button onClick={() => loadHistory(h)} className="w-full rounded px-2 py-1.5 text-left hover:bg-white/5">
                    <div className="truncate text-sm text-ink">{h.question}</div>
                    <div className="mt-1 flex items-center gap-1.5 font-mono text-[10.5px] text-dim">
                      <Badge tone={STATUS_TONE[h.status] ?? 'grey'}>{h.status}</Badge>{h.mode} · {timeAgo(h.created_at)}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          <Card label="Schema"><SchemaExplorer datasourceId={datasourceId} /></Card>
        </div>
      </div>
    </>
  )
}
