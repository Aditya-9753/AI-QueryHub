import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ScrollText, ShieldCheck, Users } from 'lucide-react'
import Badge from '../components/common/Badge'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import StatTile from '../components/common/StatTile'
import Tabs from '../components/common/Tabs'
import { ROLE_INFO } from '../hooks/useRole'
import { AdminAPI } from '../services/api'
import type { Role } from '../services/types'
import { useAuthStore } from '../store/useAuthStore'
import { errorMessage } from '../utils/format'

const LAYERS = [
  ['01', 'DB role', 'Read-only connection: Postgres queryhub_ro (sirf SELECT) / SQLite PRAGMA query_only, statement timeout'],
  ['02', 'AST rules', 'sqlglot: ek statement, root SELECT/UNION, no DML/DDL, function blacklist'],
  ['03', 'Policy', 'RBAC tables/columns, app tables + system catalogs hidden, sensitive columns block'],
  ['04', 'Cost guard', 'Auto LIMIT, timeout, EXPLAIN cost threshold'],
]
const ROLES: Role[] = ['admin', 'analyst', 'viewer']

export default function AdminSecurity() {
  const qc = useQueryClient()
  const me = useAuthStore((s) => s.user)
  const [filter, setFilter] = useState<'all' | 'blocked'>('all')
  const users = useQuery({ queryKey: ['admin-users'], queryFn: AdminAPI.users })
  const audit = useQuery({ queryKey: ['audit'], queryFn: AdminAPI.audit })
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: { role?: Role; is_active?: boolean } }) => AdminAPI.updateUser(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })
  const u = users.data ?? []
  const a = audit.data ?? []
  const shown = filter === 'blocked' ? a.filter((x) => x.blocked) : a

  return (
    <>
      <PageHeader crumbs={['Governance', 'Audit trail & RBAC']} title="Users & security" subtitle="RBAC, SQL firewall layers, audit log — sirf admin" />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatTile label="Users" value={u.length} />
        {ROLES.map((r) => <StatTile key={r} label={ROLE_INFO[r].label} value={u.filter((x) => x.role === r).length} />)}
        <StatTile label="Audit events" value={a.length} />
        <StatTile label="Blocked" value={a.filter((x) => x.blocked).length} tone="bad" />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card label="RBAC" title="Users" icon={<Users className="h-4 w-4" />} pad={false}>
          {(users.error || update.error) && <p className="mb-2 px-4 text-sm text-bad sm:px-5">{errorMessage(users.error ?? update.error)}</p>}
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead><tr><th>User</th><th>Role</th><th>Active</th><th>Joined</th></tr></thead>
              <tbody>
                {u.map((x) => {
                  const self = x.id === me?.id
                  return (
                    <tr key={x.id}>
                      <td><div className="text-ink">{x.name}{self && <span className="ml-1 font-mono text-[10.5px] text-accent">(you)</span>}</div>
                        <div className="font-mono text-[11px] text-dim">{x.email}</div></td>
                      <td>
                        <select value={x.role} disabled={self} className="input w-auto py-1 text-xs"
                          onChange={(e) => update.mutate({ id: x.id, patch: { role: e.target.value as Role } })}>
                          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
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

      <Card label="Audit trail" title="Every query, every block" icon={<ScrollText className="h-4 w-4" />} className="mt-4"
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
                  <td><Badge tone={x.blocked ? 'red' : x.reason ? 'amber' : 'green'}>{x.blocked ? 'blocked' : x.reason ? 'error' : 'ok'}</Badge></td>
                  <td className="max-w-md truncate text-[12.5px] text-muted">{x.reason}</td>
                  <td className="font-mono text-xs text-dim">{x.sql_hash?.slice(0, 12)}</td>
                </tr>
              ))}
              {shown.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-dim">Koi event nahi.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
