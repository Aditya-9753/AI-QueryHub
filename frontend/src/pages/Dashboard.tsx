import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, AlertTriangle, BookOpen, CheckCircle2, Code2, Database, FlaskConical, MessageSquareText, ShieldCheck, Sparkles,
  Star, Users, XCircle,
} from 'lucide-react'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import StatTile from '../components/common/StatTile'
import { StatusChip } from '../components/qtrace/badges'
import { useExperiments } from '../hooks/useExperiment'
import { useRole } from '../hooks/useRole'
import { AdminAPI, api, QueryAPI, SavedAPI, SchemaAPI } from '../services/api'
import type { Experiment } from '../services/types'
import { useAppStore } from '../store/useAppStore'
import { useAuthStore } from '../store/useAuthStore'
import { errorMessage, timeAgo } from '../utils/format'

const SUBTITLE = {
  viewer: 'Plain-language sawaal poochho aur team ki published investigations padho',
  analyst: 'Investigator console — anomalies ka root cause dhoondho, challenge karo, replay karo',
  admin: 'Workspace control — analysis ke saath users, connections aur audit',
}

function AccessProfile() {
  const { role, info } = useRole()
  const datasourceId = useAppStore((s) => s.datasourceId)
  const schema = useQuery({ queryKey: ['schema', datasourceId], queryFn: () => SchemaAPI.get(datasourceId), staleTime: 300_000 })
  const sensitive = schema.data?.tables.flatMap((t) => t.columns.filter((c) => c.sensitive).map((c) => `${t.name}.${c.name}`)) ?? []
  return (
    <Card label="Access profile" title={<span className="flex items-center gap-2">{info.label} <Badge tone={info.tone}>{role} · {info.persona}</Badge></span>}
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
  )
}

function ExperimentTable({ items, showOwner, empty }: { items: Experiment[]; showOwner?: boolean; empty: string }) {
  const navigate = useNavigate()
  const setExp = useAppStore((s) => s.setCurrentExperimentId)
  return (
    <div className="overflow-x-auto">
      <table className="tbl">
        <thead><tr><th>ID</th><th>Question</th>{showOwner && <th>By</th>}<th>Status</th><th>When</th></tr></thead>
        <tbody>
          {items.slice(0, 8).map((e) => (
            <tr key={e.id} className="cursor-pointer" onClick={() => { setExp(e.id); navigate('/investigate') }}>
              <td className="font-mono text-xs text-accent">EXP-{e.id.slice(0, 6).toUpperCase()}</td>
              <td className="max-w-[420px] truncate">{e.question}</td>
              {showOwner && <td className="whitespace-nowrap text-[12.5px] text-muted">{e.owner ?? '—'}</td>}
              <td><StatusChip status={e.status} /></td>
              <td className="whitespace-nowrap font-mono text-xs text-dim">{timeAgo(e.created_at)}</td>
            </tr>
          ))}
          {items.length === 0 && <tr><td colSpan={showOwner ? 5 : 4} className="py-6 text-center text-dim">{empty}</td></tr>}
        </tbody>
      </table>
    </div>
  )
}

function RecentQuestions() {
  const history = useQuery({ queryKey: ['history'], queryFn: () => QueryAPI.history(50) })
  const h = history.data ?? []
  return (
    <Card label="Recent questions" pad={false}>
      <div className="overflow-x-auto">
        <table className="tbl">
          <thead><tr><th>Question</th><th>Mode</th><th>Status</th><th className="text-right">Rows</th><th>When</th></tr></thead>
          <tbody>
            {h.slice(0, 6).map((x) => (
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
  )
}

function SavedCard() {
  const saved = useQuery({ queryKey: ['saved'], queryFn: SavedAPI.list })
  return (
    <Card label="Saved queries" icon={<Star className="h-4 w-4" />} title="Quick rerun" actions={<Link to="/saved" className="font-mono text-[11px] text-accent">all →</Link>}>
      {(saved.data ?? []).length === 0 && <p className="text-sm text-dim">Ask page par “Save” dabao.</p>}
      <ul className="flex flex-col gap-1">{saved.data?.slice(0, 5).map((s) => <li key={s.id} className="truncate text-sm text-muted">• {s.name}</li>)}</ul>
    </Card>
  )
}

/** Viewer: bada ask box — sawaal /query par le jaata hai aur wahan turant chalta hai. */
function AskHero() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const go = (mode: 'ASK' | 'ANALYZE') => (e?: FormEvent) => {
    e?.preventDefault()
    if (q.trim()) navigate(`/query?mode=${mode}&q=${encodeURIComponent(q.trim())}`)
  }
  return (
    <Card className="relative overflow-hidden border-accent/30">
      <div className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-accent/10 blur-3xl" />
      <div className="label mb-2">Ask your data</div>
      <form onSubmit={go('ASK')} className="flex flex-col gap-2 sm:flex-row">
        <input value={q} onChange={(e) => setQ(e.target.value)} className="input flex-1 py-2.5 text-base"
          placeholder="e.g. Feb 2026 me city-wise revenue" />
        <div className="flex gap-2">
          <Button type="submit" disabled={!q.trim()}><Sparkles className="h-4 w-4" />Ask</Button>
          <Button type="button" variant="secondary" onClick={() => go('ANALYZE')()} disabled={!q.trim()}><Activity className="h-4 w-4" />Analyze</Button>
        </div>
      </form>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {['Feb 2026 me city-wise revenue', '2025 me month-wise total revenue', 'Dec 2025 me UPI se kitna payment aaya?'].map((ex) => (
          <button key={ex} onClick={() => setQ(ex)} className="rounded border border-line px-2 py-0.5 text-xs text-muted hover:border-accent/50 hover:text-accent">{ex}</button>
        ))}
      </div>
    </Card>
  )
}

/** Sirf admin: poore org ki pulse (last 7 din) — Control center ka shortcut. */
function OrgPulse() {
  const { data: o } = useQuery({ queryKey: ['admin-overview', '7'], queryFn: () => AdminAPI.overview(7) })
  const audit = useQuery({ queryKey: ['audit'], queryFn: AdminAPI.audit })
  const blocked = (audit.data ?? []).filter((a) => a.blocked)
  const q = o?.queries
  return (
    <Card label="Org pulse · 7 days" title="Control center" icon={<Users className="h-4 w-4" />}
      actions={<Link to="/admin" className="font-mono text-[11px] text-accent">open →</Link>}>
      <div className="grid grid-cols-3 gap-2">
        {(['admin', 'analyst', 'viewer'] as const).map((r) => <StatTile key={r} label={r} value={o?.users.by_role[r] ?? 0} />)}
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <StatTile label="Org queries" value={q?.total ?? '—'} sub={q ? `${q.ok} ok · ${q.errors} err` : undefined} tone="accent" />
        <StatTile label="LLM tokens" value={o ? new Intl.NumberFormat('en-IN', { notation: 'compact' }).format(o.llm.reduce((a, m) => a + m.tokens_in + m.tokens_out, 0)) : '—'} />
      </div>
      <div className="mt-3 flex items-center justify-between text-sm">
        <span className="text-muted">Firewall blocks</span>
        <Badge tone={blocked.length ? 'red' : 'green'}>{blocked.length}</Badge>
      </div>
      {blocked.slice(0, 3).map((a) => <p key={a.id} className="mt-1 truncate font-mono text-[11px] text-dim">✕ {a.reason}</p>)}
    </Card>
  )
}

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const { role, can, isAdmin, isViewer } = useRole()
  const navigate = useNavigate()
  const history = useQuery({ queryKey: ['history'], queryFn: () => QueryAPI.history(50) })
  const mine = useExperiments('mine')
  const team = useExperiments('team')
  const org = useExperiments('all')
  const llm = useQuery({
    queryKey: ['llm-status'],
    queryFn: () => api.get<{ configured: boolean; providers: string[] }>('/api/llm/status').then((r) => r.data),
  })

  const h = history.data ?? []
  const myExps = can.investigate ? mine.data ?? [] : []
  const teamExps = team.data ?? []
  const alerts: { kind: string; tone: 'red' | 'amber'; text: string }[] = [
    ...myExps.filter((e) => e.status === 'failed').slice(0, 3).map((e) => ({ kind: 'investigation failed', tone: 'red' as const, text: e.question })),
    ...h.filter((x) => x.status === 'blocked').slice(0, 3).map((x) => ({ kind: 'firewall block', tone: 'red' as const, text: `${x.question} — ${x.error ?? ''}` })),
    ...(llm.data && !llm.data.configured ? [{ kind: 'LLM not configured', tone: 'amber' as const, text: '.env me GROQ_API_KEY / GEMINI_API_KEY set karke backend restart karo' }] : []),
  ]
  const launch = [
    { to: '/query?mode=ASK', title: 'Ask', text: 'Ek seedha sawaal → SQL → jawab', icon: MessageSquareText },
    { to: '/query?mode=ANALYZE', title: 'Analyze', text: 'Breakdown, trend, insights + chart', icon: Activity },
    { to: '/investigate', title: 'Investigate', text: '“Kyun?” — Q-TRACE+ root cause', icon: FlaskConical },
    { to: '/query?mode=ASK', title: 'SQL console', text: 'Monaco editor, firewalled', icon: Code2 },
  ]

  return (
    <>
      <PageHeader crumbs={['Workbench', isViewer ? 'Reader' : isAdmin ? 'Control' : 'Investigator']}
        title={`Namaste${user?.name ? `, ${user.name}` : ''}`} subtitle={SUBTITLE[role]}>
        {can.investigate
          ? <Button onClick={() => navigate('/investigate')}><FlaskConical className="h-4 w-4" />New investigation</Button>
          : <Button variant="secondary" onClick={() => navigate('/investigate')}><BookOpen className="h-4 w-4" />Team investigations</Button>}
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
        <StatTile label="My questions" value={h.length} sub={`${h.filter((x) => x.status === 'ok').length} answered`} />
        {can.investigate && <StatTile label="My investigations" value={myExps.length} sub={`${myExps.filter((e) => e.status === 'completed').length} completed`} />}
        <StatTile label="Team library" value={teamExps.length} sub="published runs" tone="accent" />
        {can.investigate && <StatTile label="Firewall blocks" value={h.filter((x) => x.status === 'blocked').length} />}
        {isViewer && <StatTile label="Tables" value="2" sub="orders · payments" />}
        <StatTile label="LLM" value={llm.data?.configured ? 'online' : 'off'} tone={llm.data?.configured ? 'ok' : 'warn'} sub={llm.data?.providers[0] ?? 'deterministic mode'} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-4">
          {isViewer ? <AskHero /> : (
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
              {launch.map((l) => (
                <Link key={l.title} to={l.to} className="group rounded-lg border border-line bg-panel p-4 transition hover:border-accent/50 hover:shadow-glow">
                  <l.icon className="h-5 w-5 text-accent" />
                  <div className="mt-3 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-ink group-hover:text-accent">{l.title}</div>
                  <div className="mt-1 text-[13px] text-muted">{l.text}</div>
                </Link>
              ))}
            </div>
          )}
          {can.investigate && (
            <Card label="My investigations" pad={false}>
              <ExperimentTable items={myExps} empty="Abhi koi investigation nahi — “New investigation” se shuru karo." />
            </Card>
          )}
          {isAdmin ? (
            <Card label="Whole organisation · incl. running / failed" title="All investigations" pad={false}>
              <ExperimentTable items={org.data ?? []} showOwner empty="Org me abhi koi investigation nahi." />
            </Card>
          ) : (
            <Card label={isViewer ? 'Published by your team' : 'Team library'} title={isViewer ? 'Team investigations' : undefined} pad={false}>
              <ExperimentTable items={teamExps} showOwner empty="Team ne abhi tak koi investigation complete nahi ki." />
            </Card>
          )}
          <RecentQuestions />
        </div>

        <div className="flex flex-col gap-4">
          {isAdmin && <OrgPulse />}
          <AccessProfile />
          <SavedCard />
          {!isViewer && (
            <Card label="Data" icon={<Database className="h-4 w-4" />} title="Sources">
              <p className="text-sm text-muted">Active datasource aur schema <Link to="/datasources" className="text-accent">Database</Link> page par.</p>
            </Card>
          )}
        </div>
      </div>
    </>
  )
}
