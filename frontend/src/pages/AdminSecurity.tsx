import { Fragment, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import {
  Activity, AlertTriangle, BrainCircuit, CheckCircle2, ChevronDown, ChevronRight, Cog, Gauge, ScrollText, ShieldCheck,
  UserPlus, Users, XCircle,
} from 'lucide-react'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import SqlBlock from '../components/common/SqlBlock'
import StatTile from '../components/common/StatTile'
import Tabs from '../components/common/Tabs'
import { ROLE_INFO } from '../hooks/useRole'
import { AdminAPI } from '../services/api'
import type { Role } from '../services/types'
import { useAuthStore } from '../store/useAuthStore'
import { errorMessage, timeAgo } from '../utils/format'

type Tab = 'overview' | 'users' | 'queries' | 'audit' | 'system'
const ROLES: Role[] = ['admin', 'analyst', 'viewer']
const LAYERS = [
  ['01', 'DB role', 'Read-only connection: Postgres queryhub_ro (sirf SELECT) / SQLite PRAGMA query_only, statement timeout'],
  ['02', 'AST rules', 'sqlglot: ek statement, root SELECT/UNION, no DML/DDL, function blacklist'],
  ['03', 'Policy', 'RBAC tables/columns, app tables + system catalogs hidden, sensitive columns block'],
  ['04', 'Cost guard', 'Auto LIMIT, timeout, EXPLAIN cost threshold'],
]
// status colors (reserved meaning) — legend + labels saath, color-alone nahi
const STATUS = { ok: '#34d399', blocked: '#f87171', errors: '#fbbf24' }
const tick = { fontSize: 11, fill: '#93a4bd', fontFamily: 'JetBrains Mono' }
const nf = new Intl.NumberFormat('en-IN')

function RoleBadge({ role }: { role: string | null }) {
  const info = role && role in ROLE_INFO ? ROLE_INFO[role as Role] : null
  return <Badge tone={info?.tone ?? 'grey'}>{role ?? '—'}</Badge>
}

// ------------------------------------------------------------------ overview
function Overview() {
  const [days, setDays] = useState<'7' | '14' | '30'>('14')
  const { data: o, error } = useQuery({ queryKey: ['admin-overview', days], queryFn: () => AdminAPI.overview(Number(days)) })
  if (error) return <p className="text-sm text-bad">{errorMessage(error)}</p>
  if (!o) return <p className="text-sm text-dim">Loading…</p>
  const q = o.queries
  const success = q.total ? q.ok / q.total : null
  const tokens = o.llm.reduce((a, m) => a + m.tokens_in + m.tokens_out, 0)
  const exp = o.experiments
  const roleRows = Object.entries(q.by_role).sort((a, b) => b[1].total - a[1].total)
  const maxRole = Math.max(1, ...roleRows.map(([, v]) => v.total))
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div className="label">Org-wide usage · last {o.days} days</div>
        <Tabs size="sm" value={days} onChange={setDays} items={[{ value: '7', label: '7d' }, { value: '14', label: '14d' }, { value: '30', label: '30d' }]} />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <StatTile label="Active users" value={`${o.users.active}/${o.users.total}`} />
        <StatTile label="Queries" value={nf.format(q.total)} tone="accent" />
        <StatTile label="Success rate" value={success === null ? '—' : `${(success * 100).toFixed(0)}%`} tone={success !== null && success < 0.8 ? 'warn' : 'ok'} />
        <StatTile label="Firewall blocks" value={q.blocked} tone={q.blocked ? 'bad' : 'default'} sub={`${o.firewall_blocks} in audit`} />
        <StatTile label="Errors" value={q.errors} tone={q.errors ? 'warn' : 'default'} />
        <StatTile label="Manual SQL" value={q.manual_sql} sub="analyst / admin" />
        <StatTile label="LLM tokens" value={nf.format(tokens)} sub={`${o.llm.reduce((a, m) => a + m.calls, 0)} calls`} />
        <StatTile label="Investigations" value={Object.values(exp).reduce((a, n) => a + n, 0)} sub={`${exp.completed ?? 0} done · ${exp.failed ?? 0} failed`} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card label="Daily query volume" title="Outcomes per day" icon={<Activity className="h-4 w-4" />}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={q.daily.map((d) => ({ ...d, day: d.date.slice(5) }))} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#1c2940" />
              <XAxis dataKey="day" tick={tick} axisLine={{ stroke: '#2a3a57' }} tickLine={false} minTickGap={8} />
              <YAxis tick={tick} allowDecimals={false} axisLine={false} tickLine={false} width={40} />
              <Tooltip cursor={{ fill: 'rgba(255,255,255,0.04)' }} contentStyle={{ background: '#0d1524', border: '1px solid #2a3a57', borderRadius: 6, fontSize: 12 }}
                labelStyle={{ color: '#e6edf7' }} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#93a4bd' }} iconType="square" />
              <Bar dataKey="ok" name="ok" stackId="s" fill={STATUS.ok} stroke="#0d1524" strokeWidth={1} isAnimationActive={false} maxBarSize={28} />
              <Bar dataKey="errors" name="errors" stackId="s" fill={STATUS.errors} stroke="#0d1524" strokeWidth={1} isAnimationActive={false} maxBarSize={28} />
              <Bar dataKey="blocked" name="blocked" stackId="s" fill={STATUS.blocked} stroke="#0d1524" strokeWidth={1} radius={[3, 3, 0, 0]} isAnimationActive={false} maxBarSize={28} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card label="Who uses it" title="Usage by role" icon={<Users className="h-4 w-4" />}>
          {roleRows.length === 0 && <p className="text-sm text-dim">Is period me koi query nahi.</p>}
          <ul className="flex flex-col gap-3">
            {roleRows.map(([role, v]) => (
              <li key={role}>
                <div className="flex items-center justify-between text-[13px]">
                  <span className="flex items-center gap-2"><RoleBadge role={role} /><span className="text-muted">{o.users.by_role[role as Role] ?? 0} users</span></span>
                  <span className="font-mono text-ink">{v.total} <span className="text-dim">· {v.blocked} blocked</span></span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-line">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${(v.total / maxRole) * 100}%` }} />
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-4 border-t border-line pt-3">
            <div className="label mb-2">LLM usage by model</div>
            {o.llm.length === 0 && <p className="text-sm text-dim">Koi LLM call nahi (deterministic mode).</p>}
            <ul className="flex flex-col gap-1.5">
              {o.llm.map((m) => (
                <li key={m.model} className="flex items-center justify-between gap-2 font-mono text-[11.5px]">
                  <span className="min-w-0 truncate text-ink" title={m.model}>{m.model}</span>
                  <span className="shrink-0 text-muted">{m.calls} calls · {nf.format(m.tokens_in + m.tokens_out)} tok · {m.avg_latency_ms?.toFixed(0) ?? '—'} ms</span>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </div>

      <Card label="Most active" title="Top users" pad={false}>
        <div className="overflow-x-auto">
          <table className="tbl">
            <thead><tr><th>User</th><th>Role</th><th className="text-right">Queries</th><th className="text-right">OK</th><th className="text-right">Blocked</th><th>Success</th></tr></thead>
            <tbody>
              {o.top_users.map((u) => (
                <tr key={u.id}>
                  <td><div className="text-ink">{u.name || u.email.split('@')[0]}</div><div className="font-mono text-[11px] text-dim">{u.email}</div></td>
                  <td><RoleBadge role={u.role} /></td>
                  <td className="num text-right text-ink">{u.total}</td>
                  <td className="num text-right text-ok">{u.ok}</td>
                  <td className={`num text-right ${u.blocked ? 'text-bad' : 'text-dim'}`}>{u.blocked}</td>
                  <td className="w-40">
                    <div className="h-1.5 overflow-hidden rounded-full bg-line"><div className="h-full rounded-full bg-ok" style={{ width: `${(u.ok / (u.total || 1)) * 100}%` }} /></div>
                  </td>
                </tr>
              ))}
              {o.top_users.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-dim">Is period me koi activity nahi.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------ users
function UsersTab() {
  const qc = useQueryClient()
  const me = useAuthStore((s) => s.user)
  const users = useQuery({ queryKey: ['admin-users'], queryFn: AdminAPI.users })
  const [form, setForm] = useState({ email: '', name: '', password: '', role: 'viewer' as Role })
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: { role?: Role; is_active?: boolean } }) => AdminAPI.updateUser(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })
  const create = useMutation({
    mutationFn: () => AdminAPI.createUser({ ...form, name: form.name || undefined }),
    onSuccess: () => { setForm({ email: '', name: '', password: '', role: 'viewer' }); qc.invalidateQueries({ queryKey: ['admin-users'] }) },
  })
  const submit = (e: FormEvent) => { e.preventDefault(); create.mutate() }
  const u = users.data ?? []
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Card label="RBAC" title={`${u.length} accounts`} icon={<Users className="h-4 w-4" />} pad={false}>
        {(users.error || update.error) && <p className="mb-2 px-4 text-sm text-bad sm:px-5">{errorMessage(users.error ?? update.error)}</p>}
        <div className="overflow-x-auto">
          <table className="tbl">
            <thead><tr><th>User</th><th>Role</th><th>Active</th><th>Joined</th></tr></thead>
            <tbody>
              {u.map((x) => {
                const self = x.id === me?.id
                return (
                  <tr key={x.id} className={x.is_active ? '' : 'opacity-50'}>
                    <td><div className="text-ink">{x.name}{self && <span className="ml-1 font-mono text-[10.5px] text-accent">(you)</span>}</div>
                      <div className="font-mono text-[11px] text-dim">{x.email}</div></td>
                    <td>
                      <select value={x.role} disabled={self} className="input w-auto py-1 text-xs"
                        onChange={(e) => update.mutate({ id: x.id, patch: { role: e.target.value as Role } })}>
                        {ROLES.map((r) => <option key={r} value={r}>{r} · {ROLE_INFO[r].persona}</option>)}
                      </select>
                    </td>
                    <td><input type="checkbox" className="accent-cyan-400" checked={x.is_active} disabled={self}
                      onChange={(e) => update.mutate({ id: x.id, patch: { is_active: e.target.checked } })} /></td>
                    <td className="whitespace-nowrap font-mono text-xs text-dim">{x.created_at ? new Date(x.created_at).toLocaleDateString() : ''}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="flex flex-col gap-4">
        <Card label="Onboard" title="Add team member" icon={<UserPlus className="h-4 w-4" />}>
          <form onSubmit={submit} className="flex flex-col gap-2.5">
            <input className="input" type="email" required placeholder="email@company.com" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <input className="input" placeholder="Name (optional)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input className="input" type="password" required minLength={8} placeholder="Temporary password (min 8)" value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
              {ROLES.map((r) => <option key={r} value={r}>{r} · {ROLE_INFO[r].persona}</option>)}
            </select>
            <p className="text-xs text-dim">{ROLE_INFO[form.role].desc}</p>
            {create.isError && <p className="text-sm text-bad">{errorMessage(create.error)}</p>}
            {create.isSuccess && <p className="text-sm text-ok">Account ban gaya — password user ko safe tarike se bhejo.</p>}
            <Button type="submit" disabled={create.isPending}><UserPlus className="h-4 w-4" />Create account</Button>
          </form>
        </Card>
        <Card label="Role matrix" title="Kaun kya kar sakta hai">
          <ul className="flex flex-col gap-3">
            {ROLES.map((r) => (
              <li key={r}>
                <div className="flex items-center gap-2"><RoleBadge role={r} /><span className="text-[13px] text-ink">{ROLE_INFO[r].persona}</span></div>
                <p className="mt-1 text-[12px] text-muted">{ROLE_INFO[r].can.slice(0, 3).join(' · ')}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ query log
function QueryLog() {
  const [status, setStatus] = useState<'all' | 'ok' | 'blocked' | 'error'>('all')
  const [open, setOpen] = useState<string | null>(null)
  const log = useQuery({ queryKey: ['admin-queries', status], queryFn: () => AdminAPI.queries(status === 'all' ? undefined : status) })
  return (
    <Card label="Every question, every user" title="Org query log" icon={<ScrollText className="h-4 w-4" />}
      actions={<Tabs size="sm" value={status} onChange={setStatus} items={[{ value: 'all', label: 'All' }, { value: 'ok', label: 'OK' }, { value: 'blocked', label: 'Blocked' }, { value: 'error', label: 'Errors' }]} />}>
      {log.error && <p className="text-sm text-bad">{errorMessage(log.error)}</p>}
      <div className="-mx-4 overflow-x-auto sm:-mx-5">
        <table className="tbl">
          <thead><tr><th /><th>When</th><th>User</th><th>Question</th><th>Mode</th><th>Status</th><th className="text-right">Rows</th><th className="text-right">ms</th></tr></thead>
          <tbody>
            {log.data?.map((x) => (
              <Fragment key={x.id}>
                <tr className="cursor-pointer" onClick={() => setOpen(open === x.id ? null : x.id)}>
                  <td className="w-6 text-dim">{open === x.id ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}</td>
                  <td className="whitespace-nowrap font-mono text-xs text-dim">{timeAgo(x.created_at)}</td>
                  <td className="whitespace-nowrap"><span className="mr-1.5 text-[13px] text-ink">{x.user.name || x.user.email?.split('@')[0] || 'dev'}</span><RoleBadge role={x.user.role} /></td>
                  <td className="max-w-[360px] truncate text-[13px]">{x.question}</td>
                  <td className="font-mono text-[11px] text-muted">{x.mode}{x.generated ? '' : ' · SQL'}</td>
                  <td><Badge tone={x.status === 'ok' ? 'green' : x.status === 'blocked' ? 'red' : 'amber'}>{x.status}</Badge></td>
                  <td className="num text-right text-muted">{x.row_count ?? '—'}</td>
                  <td className="num text-right text-dim">{x.duration_ms?.toFixed(0) ?? '—'}</td>
                </tr>
                {open === x.id && (
                  <tr>
                    <td colSpan={8} className="bg-panel2/40">
                      {x.error && <p className="mb-2 flex items-start gap-1.5 text-[13px] text-bad"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{x.error}</p>}
                      {x.sql ? <SqlBlock sql={x.sql} maxHeight={180} /> : <p className="text-xs text-dim">SQL generate nahi hua.</p>}
                      <p className="mt-1.5 font-mono text-[10.5px] text-dim">{x.user.email} · {new Date(x.created_at).toLocaleString()} · {x.llm_calls} LLM calls</p>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {log.data?.length === 0 && <tr><td colSpan={8} className="py-6 text-center text-dim">Koi query nahi.</td></tr>}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

// ------------------------------------------------------------------ audit
function AuditTab() {
  const [filter, setFilter] = useState<'all' | 'blocked'>('all')
  const audit = useQuery({ queryKey: ['audit'], queryFn: AdminAPI.audit })
  const a = audit.data ?? []
  const shown = filter === 'blocked' ? a.filter((x) => x.blocked) : a
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card label="Audit trail" title="Every action, every block" icon={<ScrollText className="h-4 w-4" />}
        actions={<Tabs size="sm" value={filter} onChange={setFilter} items={[{ value: 'all', label: `All (${a.length})` }, { value: 'blocked', label: 'Blocked only' }]} />}>
        {audit.error && <p className="text-sm text-bad">{errorMessage(audit.error)}</p>}
        <div className="-mx-4 overflow-x-auto sm:-mx-5">
          <table className="tbl">
            <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Status</th><th>Reason</th><th>SQL hash</th></tr></thead>
            <tbody>
              {shown.map((x) => (
                <tr key={x.id}>
                  <td className="whitespace-nowrap font-mono text-xs text-muted">{new Date(x.ts).toLocaleString()}</td>
                  <td className="font-mono text-xs text-dim">{x.user_id?.slice(0, 8)}</td>
                  <td className="font-mono text-xs text-ink">{x.action}</td>
                  <td><Badge tone={x.blocked ? 'red' : x.reason ? 'amber' : 'green'}>{x.blocked ? 'blocked' : x.reason ? 'note' : 'ok'}</Badge></td>
                  <td className="max-w-md truncate text-[12.5px] text-muted" title={x.reason ?? ''}>{x.reason}</td>
                  <td className="font-mono text-xs text-dim">{x.sql_hash?.slice(0, 12)}</td>
                </tr>
              ))}
              {shown.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-dim">Koi event nahi.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
      <Card label="Defense in depth" title="SQL firewall" icon={<ShieldCheck className="h-4 w-4" />}>
        <ol className="flex flex-col gap-2">
          {LAYERS.map(([n, l, d]) => (
            <li key={n} className="flex gap-3 rounded-md border border-line bg-panel2/60 p-2.5">
              <span className="font-mono text-sm text-accent">{n}</span>
              <div><div className="text-sm font-semibold text-ink">{l}</div><div className="text-[12.5px] text-muted">{d}</div></div>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------ system
function Flag({ on, label }: { on: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-[13px] ${on ? 'text-ok' : 'text-dim'}`}>
      {on ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}{label}
    </span>
  )
}

function SystemTab() {
  const { data: s, error } = useQuery({ queryKey: ['admin-system'], queryFn: AdminAPI.system })
  if (error) return <p className="text-sm text-bad">{errorMessage(error)}</p>
  if (!s) return <p className="text-sm text-dim">Loading…</p>
  const llm = s.llm as Record<string, { configured?: boolean; model?: string; url?: string } | number | boolean>
  const auth = s.auth as { supabase: boolean; jwt_default_secret: boolean; token_ttl_min: number }
  const kv = (o: unknown) => Object.entries(o as Record<string, unknown>)
  return (
    <div className="flex flex-col gap-4">
      {auth.jwt_default_secret && (
        <Card className="border-bad/40 bg-bad/5">
          <p className="flex items-center gap-2 text-sm text-bad"><AlertTriangle className="h-4 w-4" />JWT_SECRET abhi default (“change-me”) hai — production se pehle .env me random secret daalo.</p>
        </Card>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Card label="Providers (keys kabhi dikhaye nahi jaate)" title="LLM chain" icon={<BrainCircuit className="h-4 w-4" />}>
          <ul className="flex flex-col gap-2">
            {(['groq', 'gemini', 'ollama'] as const).map((p) => {
              const v = llm[p] as { configured?: boolean; model?: string; url?: string }
              return (
                <li key={p} className="flex items-center justify-between gap-2">
                  {p === 'ollama' ? <span className="text-[13px] text-muted">ollama (local)</span> : <Flag on={!!v.configured} label={p} />}
                  <span className="truncate font-mono text-[11px] text-dim">{v.model}</span>
                </li>
              )
            })}
          </ul>
          <p className="mt-3 font-mono text-[11px] text-dim">temperature {String(llm.temperature)} · SQL repair retries {String(llm.sql_repair_retries)}</p>
        </Card>
        <Card label="Layer 4 limits" title="Firewall" icon={<ShieldCheck className="h-4 w-4" />}>
          <dl className="divide-y divide-line text-sm">{kv(s.firewall).map(([k, v]) => (
            <div key={k} className="flex justify-between py-1.5"><dt className="text-muted">{k.replace(/_/g, ' ')}</dt><dd className="font-mono text-ink">{typeof v === 'number' ? nf.format(v) : String(v)}</dd></div>))}</dl>
        </Card>
        <Card label="Investigation budgets" title="Q-TRACE+" icon={<Gauge className="h-4 w-4" />}>
          <dl className="divide-y divide-line text-sm">{kv(s.qtrace).map(([k, v]) => (
            <div key={k} className="flex justify-between py-1.5"><dt className="text-muted">{k.replace(/_/g, ' ')}</dt><dd className="font-mono text-ink">{String(v)}</dd></div>))}</dl>
        </Card>
        <Card label="Identity" title="Auth" icon={<Users className="h-4 w-4" />}>
          <div className="flex flex-col gap-2">
            <Flag on={auth.supabase} label="Supabase / Google login" />
            <Flag on={!auth.jwt_default_secret} label="Custom JWT secret" />
            <span className="font-mono text-[11px] text-dim">token ttl {auth.token_ttl_min} min</span>
          </div>
        </Card>
        <Card label="Runtime" title="Platform" icon={<Cog className="h-4 w-4" />}>
          <dl className="divide-y divide-line text-sm">
            <div className="flex justify-between py-1.5"><dt className="text-muted">environment</dt><dd className="font-mono text-ink">{String(s.environment)}</dd></div>
            <div className="flex justify-between py-1.5"><dt className="text-muted">app database</dt><dd className="font-mono text-ink">{String((s.database as Record<string, string>).app)}</dd></div>
            <div className="flex justify-between py-1.5"><dt className="text-muted">query database</dt><dd className="font-mono text-ink">{String((s.database as Record<string, string>).readonly)}</dd></div>
            <div className="flex justify-between py-1.5"><dt className="text-muted">schema RAG</dt><dd className="font-mono text-ink">{String((s.rag as Record<string, string>).schema_rag)}</dd></div>
            <div className="flex justify-between py-1.5"><dt className="text-muted">Sentry</dt><dd><Flag on={!!(s.monitoring as Record<string, boolean>).sentry} label={(s.monitoring as Record<string, boolean>).sentry ? 'on' : 'off'} /></dd></div>
          </dl>
        </Card>
      </div>
    </div>
  )
}

export default function AdminSecurity() {
  const [tab, setTab] = useState<Tab>('overview')
  return (
    <>
      <PageHeader crumbs={['Governance', 'Control center']} title="Control center"
        subtitle="Sirf admin: poore org ki usage, har user ki queries, accounts, audit aur system config">
        <Badge tone="amber">admin · workspace owner</Badge>
      </PageHeader>
      <div className="mb-4 overflow-x-auto">
        <Tabs value={tab} onChange={setTab} items={[
          { value: 'overview', label: 'Overview' }, { value: 'users', label: 'Users' }, { value: 'queries', label: 'Query log' },
          { value: 'audit', label: 'Audit' }, { value: 'system', label: 'System' }]} />
      </div>
      {tab === 'overview' && <Overview />}
      {tab === 'users' && <UsersTab />}
      {tab === 'queries' && <QueryLog />}
      {tab === 'audit' && <AuditTab />}
      {tab === 'system' && <SystemTab />}
    </>
  )
}
