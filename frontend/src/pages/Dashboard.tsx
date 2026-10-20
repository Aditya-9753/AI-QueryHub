import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Activity, AlertTriangle, CheckCircle2, Database, FlaskConical, MessageSquareText, ShieldCheck, Star, XCircle } from 'lucide-react'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import StatTile from '../components/common/StatTile'
import { StatusChip } from '../components/qtrace/badges'
import { useExperiments } from '../hooks/useExperiment'
import { useRole } from '../hooks/useRole'
import { api, QueryAPI, SavedAPI, SchemaAPI } from '../services/api'
import { useAppStore } from '../store/useAppStore'
import { useAuthStore } from '../store/useAuthStore'
import { errorMessage, timeAgo } from '../utils/format'

const LAUNCH = [
  { to: '/query?mode=ASK', title: 'Ask', text: 'Ek seedha sawaal → SQL → jawab', icon: MessageSquareText },
  { to: '/query?mode=ANALYZE', title: 'Analyze', text: 'Breakdown / comparison + chart', icon: Activity },
  { to: '/investigate', title: 'Investigate', text: '“Kyun?” — Q-TRACE+ root cause', icon: FlaskConical },
  { to: '/datasources', title: 'Database', text: 'Connections + schema viewer', icon: Database },
]

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const { role, info } = useRole()
  const navigate = useNavigate()
  const setExp = useAppStore((s) => s.setCurrentExperimentId)
  const datasourceId = useAppStore((s) => s.datasourceId)
  const history = useQuery({ queryKey: ['history'], queryFn: () => QueryAPI.history(50) })
  const saved = useQuery({ queryKey: ['saved'], queryFn: SavedAPI.list })
  const experiments = useExperiments()
  const schema = useQuery({ queryKey: ['schema', datasourceId], queryFn: () => SchemaAPI.get(datasourceId), staleTime: 300_000 })
  const llm = useQuery({
    queryKey: ['llm-status'],
    queryFn: () => api.get<{ configured: boolean; providers: string[] }>('/api/llm/status').then((r) => r.data),
  })

  const h = history.data ?? []
  const ok = h.filter((x) => x.status === 'ok').length
  const blocked = h.filter((x) => x.status === 'blocked').length
  const exps = experiments.data ?? []
  const alerts: { kind: string; tone: 'red' | 'amber'; text: string }[] = [
    ...exps.filter((e) => e.status === 'failed').slice(0, 3).map((e) => ({ kind: 'investigation failed', tone: 'red' as const, text: e.question })),
    ...h.filter((x) => x.status === 'blocked').slice(0, 3).map((x) => ({ kind: 'firewall block', tone: 'red' as const, text: `${x.question} — ${x.error ?? ''}` })),
    ...(llm.data && !llm.data.configured ? [{ kind: 'LLM not configured', tone: 'amber' as const, text: '.env me GROQ_API_KEY / GEMINI_API_KEY set karke backend restart karo' }] : []),
  ]
  const sensitive = schema.data?.tables.flatMap((t) => t.columns.filter((c) => c.sensitive).map((c) => `${t.name}.${c.name}`)) ?? []

  return (
    <>
      <PageHeader crumbs={['Workbench']} title={`Namaste${user?.name ? `, ${user.name}` : ''}`}
        subtitle="Business sawaal → safe, evidence-driven, reproducible jawab">
        <Button onClick={() => navigate('/investigate')}><FlaskConical className="h-4 w-4" />New investigation</Button>
      </PageHeader>
      {history.error && <p className="mb-4 text-sm text-bad">Backend: {errorMessage(history.error)}</p>}

      {alerts.length > 0 && (
        <Card label="Alerts" className="mb-4 border-warn/30">
          <ul className="flex flex-col gap-1.5 text-sm">
            {alerts.map((a, i) => (
              <li key={i} className="flex items-start gap-2"><AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${a.tone === 'red' ? 'text-bad' : 'text-warn'}`} />
                <Badge tone={a.tone}>{a.kind}</Badge><span className="min-w-0 truncate text-muted">{a.text}</span></li>
            ))}
          </ul>
        </Card>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatTile label="Queries (last 50)" value={h.length} />
        <StatTile label="Successful" value={ok} tone="ok" />
        <StatTile label="Firewall blocks" value={blocked} tone={blocked ? 'bad' : 'default'} />
        <StatTile label="Saved queries" value={saved.data?.length ?? '—'} />
        <StatTile label="Investigations" value={exps.length} sub={`${exps.filter((e) => e.status === 'completed').length} completed`} />
        <StatTile label="LLM" value={llm.data?.configured ? 'online' : 'off'} tone={llm.data?.configured ? 'accent' : 'warn'}
          sub={llm.data?.providers.join(' → ') || 'deterministic mode'} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            {LAUNCH.map((l) => (
              <Link key={l.title} to={l.to} className="group rounded-lg border border-line bg-panel p-4 transition hover:border-accent/50 hover:shadow-glow">
                <l.icon className="h-5 w-5 text-accent" />
                <div className="mt-3 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-ink group-hover:text-accent">{l.title}</div>
                <div className="mt-1 text-[13px] text-muted">{l.text}</div>
              </Link>
            ))}
          </div>
          <Card label="Recent investigations" pad={false}>
            <div className="overflow-x-auto">
              <table className="tbl">
                <thead><tr><th>ID</th><th>Question</th><th>Status</th><th>When</th></tr></thead>
                <tbody>
                  {exps.slice(0, 8).map((e) => (
                    <tr key={e.id} className="cursor-pointer" onClick={() => { setExp(e.id); navigate('/investigate') }}>
                      <td className="font-mono text-xs text-accent">EXP-{e.id.slice(0, 6).toUpperCase()}</td>
                      <td className="max-w-[420px] truncate">{e.question}</td>
                      <td><StatusChip status={e.status} /></td>
                      <td className="whitespace-nowrap font-mono text-xs text-dim">{timeAgo(e.created_at)}</td>
                    </tr>
                  ))}
                  {exps.length === 0 && <tr><td colSpan={4} className="py-6 text-center text-dim">Abhi koi investigation nahi.</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>
          <Card label="Recent questions" pad={false}>
            <div className="overflow-x-auto">
              <table className="tbl">
                <thead><tr><th>Question</th><th>Mode</th><th>Status</th><th className="text-right">Rows</th><th>When</th></tr></thead>
                <tbody>
                  {h.slice(0, 8).map((x) => (
                    <tr key={x.id}>
                      <td className="max-w-[420px] truncate">{x.question}</td>
                      <td className="font-mono text-xs text-muted">{x.mode}</td>
                      <td><StatusChip status={x.status === 'ok' ? 'passed' : x.status === 'blocked' ? 'failed' : 'inconclusive'} /></td>
                      <td className="num text-right text-muted">{x.row_count ?? '—'}</td>
                      <td className="whitespace-nowrap font-mono text-xs text-dim">{timeAgo(x.created_at)}</td>
                    </tr>
                  ))}
                  {h.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-dim">Abhi koi query nahi — <Link to="/query" className="text-accent">pehla sawaal poochho</Link>.</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          <Card label="Access profile" title={<span className="flex items-center gap-2">{info.label} <Badge tone="blue">{role}</Badge></span>}
            icon={<ShieldCheck className="h-4 w-4" />}>
            <p className="mb-3 text-[13px] text-muted">{info.desc}</p>
            <ul className="flex flex-col gap-1.5 text-[13px]">
              {info.can.map((c) => <li key={c} className="flex items-center gap-2 text-ink"><CheckCircle2 className="h-4 w-4 shrink-0 text-ok" />{c}</li>)}
              {info.cannot.map((c) => <li key={c} className="flex items-center gap-2 text-dim"><XCircle className="h-4 w-4 shrink-0 text-bad/70" />{c}</li>)}
            </ul>
            <div className="mt-4 border-t border-line pt-3">
              <div className="label mb-1.5">Tables visible to you</div>
              <div className="flex flex-wrap gap-1">
                {schema.data?.tables.map((t) => <span key={t.name} className="rounded border border-line px-1.5 py-0.5 font-mono text-[11px] text-muted">{t.name}</span>)}
              </div>
              {sensitive.length > 0 && <div className="mt-2 font-mono text-[11px] text-warn">locked: {sensitive.join(', ')}</div>}
            </div>
          </Card>
          <Card label="Saved queries" icon={<Star className="h-4 w-4" />} title="Quick rerun"
            actions={<Link to="/saved" className="font-mono text-[11px] text-accent">all →</Link>}>
            {(saved.data ?? []).length === 0 && <p className="text-sm text-dim">Ask page par “Save” dabao.</p>}
            <ul className="flex flex-col gap-1">
              {saved.data?.slice(0, 5).map((s) => <li key={s.id} className="truncate text-sm text-muted">• {s.name}</li>)}
            </ul>
          </Card>
        </div>
      </div>
    </>
  )
}
