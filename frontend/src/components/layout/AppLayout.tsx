import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Database, FileText, FlaskConical, GitBranch, LayoutGrid, LogOut, Menu, MessageSquareText, ScrollText,
  Lock, ShieldCheck, Sigma, Swords, Target, X,
} from 'lucide-react'
import Badge from '../common/Badge'
import { api, AuthAPI } from '../../services/api'
import { supabase } from '../../services/supabase'
import { useAuthStore } from '../../store/useAuthStore'
import { useRole, type Capabilities } from '../../hooks/useRole'

type Match = (path: string, search: string) => boolean
const MODES: { label: string; to: string; match: Match; cap?: keyof Capabilities }[] = [
  { label: 'Ask', to: '/query?mode=ASK', match: (p, s) => p === '/query' && !s.includes('ANALYZE') },
  { label: 'Analyze', to: '/query?mode=ANALYZE', match: (p, s) => p === '/query' && s.includes('ANALYZE') },
  { label: 'Investigate', to: '/investigate', match: (p) => p === '/investigate' },
  { label: 'Challenge', to: '/challenge', match: (p) => p === '/challenge' || p === '/evidence', cap: 'challenge' },
  { label: 'Replay', to: '/record', match: (p) => p === '/record', cap: 'replay' },
]

type Item = { to: string; label: string; icon: typeof Database; cap?: keyof Capabilities; viewerLabel?: string }
const SECTIONS: { title: string; adminOnly?: boolean; items: Item[] }[] = [
  {
    title: 'Operational scope', items: [
      { to: '/', label: 'Workbench', icon: LayoutGrid },
      { to: '/query', label: 'Ask & Analyze', icon: MessageSquareText },
      { to: '/investigate', label: 'Investigations', icon: FlaskConical, viewerLabel: 'Team investigations' },
      { to: '/evidence', label: 'Evidence graph', icon: GitBranch },
      { to: '/challenge', label: 'Challenge', icon: Swords, cap: 'challenge' },
      { to: '/record', label: 'Runs & replays', icon: ScrollText, viewerLabel: 'Run records' },
    ],
  },
  {
    title: 'Data', items: [
      { to: '/saved', label: 'Saved queries', icon: FileText },
      { to: '/datasources', label: 'Database', icon: Database },
      { to: '/metrics', label: 'Semantic layer', icon: Sigma },
    ],
  },
  { title: 'Quality', items: [{ to: '/eval', label: 'Eval dashboard', icon: Target }] },
  { title: 'Governance', adminOnly: true, items: [{ to: '/admin', label: 'Control center', icon: ShieldCheck }] },
]

const LOCK_TITLE = 'Analyst / admin ke liye — admin se role badalne ko kaho'

function Logo() {
  return (
    <Link to="/" className="flex shrink-0 items-center gap-2.5">
      <span className="grid h-8 w-8 place-items-center rounded-md bg-accent/15 ring-1 ring-accent/40">
        <span className="flex items-end gap-[3px]">
          {[8, 13, 18].map((h) => <span key={h} className="w-[3px] rounded-sm bg-accent" style={{ height: h }} />)}
        </span>
      </span>
      <span className="leading-tight">
        <span className="block text-[15px] font-semibold text-ink">AI QueryHub</span>
        <span className="block font-mono text-[9.5px] uppercase tracking-[0.18em] text-dim">Q-TRACE+ engine</span>
      </span>
    </Link>
  )
}

export default function AppLayout() {
  const [open, setOpen] = useState(false)
  const { user, setUser, logout } = useAuthStore()
  const { role, isAdmin, isViewer, info, can } = useRole()
  const { pathname, search } = useLocation()

  useEffect(() => setOpen(false), [pathname, search])
  useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const me = await AuthAPI.me()
      setUser(me)
      return me
    },
    staleTime: 60_000,
  })
  const llm = useQuery({
    queryKey: ['llm-status'],
    queryFn: () => api.get<{ configured: boolean; providers: string[] }>('/api/llm/status').then((r) => r.data),
    staleTime: 60_000,
  })
  const signOut = () => {
    void supabase?.auth.signOut()
    logout()
  }

  return (
    <div className="min-h-screen">
      {/* ---------------- top bar ---------------- */}
      <header className="sticky top-0 z-30 border-b border-line bg-bg/95 backdrop-blur">
        <div className="flex h-14 items-center gap-3 px-3 sm:px-4">
          <button className="rounded p-1.5 text-muted hover:bg-white/5 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <Logo />
          <nav className="ml-2 hidden min-w-0 flex-1 items-center gap-1 overflow-x-auto md:flex">
            {MODES.map((m) => {
              const active = m.match(pathname, search)
              if (m.cap && !can[m.cap]) {
                return (
                  <span key={m.label} title={LOCK_TITLE}
                    className="inline-flex cursor-not-allowed items-center gap-1.5 whitespace-nowrap rounded px-3 py-1.5 font-mono text-[11.5px] uppercase tracking-[0.14em] text-dim/60">
                    <Lock className="h-3 w-3" />{m.label}
                  </span>
                )
              }
              return (
                <Link key={m.label} to={m.to}
                  className={`whitespace-nowrap rounded px-3 py-1.5 font-mono text-[11.5px] font-medium uppercase tracking-[0.14em] transition-colors ${
                    active ? 'bg-accent text-accent-ink' : 'text-muted hover:bg-white/5 hover:text-ink'}`}>
                  {m.label}
                </Link>
              )
            })}
          </nav>
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <span className={`hidden items-center gap-1.5 rounded border px-2 py-1 font-mono text-[10.5px] uppercase tracking-wider sm:inline-flex ${
              llm.data?.configured ? 'border-ok/30 text-ok' : 'border-warn/40 text-warn'}`}
              title={llm.data?.providers.join(' -> ') || 'LLM key set nahi'}>
              <span className={`h-1.5 w-1.5 rounded-full ${llm.data?.configured ? 'bg-ok' : 'bg-warn'}`} />
              LLM {llm.data?.configured ? llm.data.providers[0]?.split('/')[0] : 'off'}
            </span>
            <span className="hidden font-mono text-[10.5px] uppercase tracking-wider text-dim xl:inline">₹0 · free tier</span>
            {user && (
              <div className="flex items-center gap-2">
                <div className="hidden text-right leading-tight sm:block">
                  <div className="max-w-[160px] truncate text-xs text-ink">{user.name || user.email}</div>
                  <Badge tone={info.tone} className="mt-0.5">{role} · {info.persona}</Badge>
                </div>
                <span className="grid h-8 w-8 place-items-center rounded-full bg-accent/15 font-mono text-sm font-semibold text-accent ring-1 ring-accent/40">
                  {(user.name || user.email).slice(0, 1).toUpperCase()}
                </span>
              </div>
            )}
            <button onClick={signOut} className="rounded p-1.5 text-muted hover:bg-white/5 hover:text-ink" title="Logout" aria-label="Logout">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
        {/* mobile: mode tabs */}
        <nav className="flex gap-1 overflow-x-auto border-t border-line px-3 py-1.5 md:hidden">
          {MODES.filter((m) => !m.cap || can[m.cap]).map((m) => (
            <Link key={m.label} to={m.to}
              className={`whitespace-nowrap rounded px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider ${
                m.match(pathname, search) ? 'bg-accent text-accent-ink' : 'text-muted'}`}>{m.label}</Link>
          ))}
        </nav>
        {isViewer && (
          <div className="flex items-center gap-2 border-t border-line bg-panel2/70 px-4 py-1.5 font-mono text-[10.5px] uppercase tracking-wider text-muted">
            <Lock className="h-3 w-3 shrink-0 text-dim" />
            <span className="truncate">Viewer workspace · plain-language sawaal + team reports · SQL, investigations aur challenge analyst ke paas</span>
          </div>
        )}
      </header>

      <div className="flex">
        {open && <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={() => setOpen(false)} />}
        {/* ---------------- sidebar ---------------- */}
        <aside className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-line bg-panel transition-transform lg:sticky lg:top-14 lg:z-10 lg:h-[calc(100vh-3.5rem)] lg:w-60 lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'}`}>
          <div className="flex items-center justify-between px-4 py-4 lg:hidden">
            <Logo />
            <button onClick={() => setOpen(false)} aria-label="Close menu" className="text-muted"><X className="h-5 w-5" /></button>
          </div>
          <nav className="flex flex-1 flex-col gap-4 overflow-y-auto px-3 py-4">
            {SECTIONS.filter((s) => !s.adminOnly || isAdmin).map((s) => (
              <div key={s.title}>
                <div className="label mb-1.5 px-2">{s.title}</div>
                {s.items.map((it) => it.cap && !can[it.cap] ? (
                  <span key={it.to} title={LOCK_TITLE}
                    className="flex cursor-not-allowed items-center gap-2.5 rounded-md px-2.5 py-2 text-[13.5px] text-dim/60">
                    <it.icon className="h-4 w-4 shrink-0" />{it.label}<Lock className="ml-auto h-3 w-3" />
                  </span>
                ) : (
                  <NavLink key={it.to} to={it.to} end={it.to === '/'}
                    className={({ isActive }) => `flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13.5px] transition-colors ${
                      isActive ? 'bg-accent/10 font-medium text-accent ring-1 ring-inset ring-accent/25' : 'text-muted hover:bg-white/[0.04] hover:text-ink'}`}>
                    <it.icon className="h-4 w-4 shrink-0" />
                    {isViewer && it.viewerLabel ? it.viewerLabel : it.label}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          <div className="m-3 rounded-md border border-line bg-panel2 p-3">
            <div className="flex items-center justify-between">
              <span className="label">SQL firewall</span>
              <span className="font-mono text-[10px] text-accent">4 layers</span>
            </div>
            <div className="mt-1.5 flex items-center gap-1.5 font-mono text-[11px] text-ok">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ok" />read-only · AST · RBAC · cost
            </div>
            <div className="mt-2 border-t border-line pt-2 text-[11px] leading-snug text-dim">
              <span className="text-muted">{info.label} · {info.persona}:</span> {info.desc}
            </div>
          </div>
        </aside>

        <main className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
