import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { CheckCircle2, FlaskConical, GitBranch, ShieldCheck } from 'lucide-react'
import Button from '../components/common/Button'
import { AuthAPI } from '../services/api'
import { supabase } from '../services/supabase'
import { useAuthStore } from '../store/useAuthStore'
import { errorMessage } from '../utils/format'

const POINTS = [
  { icon: ShieldCheck, title: '4-layer SQL firewall', text: 'Read-only role, sqlglot AST, RBAC, cost guard — har query par.' },
  { icon: FlaskConical, title: 'Q-TRACE+ investigations', text: '“Kyun gira?” ka jawab maths se: calendar, mix, rate, DiD, FDR.' },
  { icon: GitBranch, title: 'Evidence graph + replay', text: 'Har number SQL checksum tak trace hota hai, exact replay ke saath.' },
]

export default function Login() {
  const [tab, setTab] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [info, setInfo] = useState('')
  const { token, setAuth, setToken, setUser } = useAuthStore()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from ?? '/'

  const submit = useMutation({
    mutationFn: async () => {
      if (supabase) {
        const res = tab === 'login'
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({ email, password, options: { data: { full_name: name } } })
        if (res.error) throw new Error(res.error.message)
        if (!res.data.session) {
          setInfo('Email confirm karo, phir login karo.')
          return null
        }
        setToken(res.data.session.access_token)
        const me = await AuthAPI.me()
        setUser(me)
        return me
      }
      const r = tab === 'login' ? await AuthAPI.login(email, password) : await AuthAPI.signup(email, password, name || undefined)
      setAuth(r.access_token, r.user)
      return r.user
    },
    onSuccess: (u) => { if (u) navigate(from, { replace: true }) },
  })

  if (token) return <Navigate to={from} replace />

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    setInfo('')
    submit.mutate()
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden border-r border-line bg-panel p-12 lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute -left-32 -top-32 h-96 w-96 rounded-full bg-accent/10 blur-3xl" />
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-lg bg-accent/15 ring-1 ring-accent/40">
            <span className="flex items-end gap-1">{[10, 16, 22].map((h) => <span key={h} className="w-1 rounded-sm bg-accent" style={{ height: h }} />)}</span>
          </span>
          <div>
            <div className="text-lg font-semibold">AI QueryHub</div>
            <div className="label">Q-TRACE+ evidence engine</div>
          </div>
        </div>
        <div className="max-w-lg">
          <h1 className="text-3xl font-semibold leading-tight tracking-tight">
            Business sawaal → <span className="text-accent">safe, evidence-driven</span>, reproducible jawab.
          </h1>
          <ul className="mt-8 flex flex-col gap-5">
            {POINTS.map((p) => (
              <li key={p.title} className="flex gap-3">
                <p.icon className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
                <div><div className="font-medium">{p.title}</div><div className="text-sm text-muted">{p.text}</div></div>
              </li>
            ))}
          </ul>
        </div>
        <div className="label">ASK → ANALYZE → INVESTIGATE → CHALLENGE → REPLAY</div>
      </div>

      <div className="flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="text-xl font-semibold">AI QueryHub</div>
            <div className="label">Q-TRACE+ evidence engine</div>
          </div>
          <h2 className="text-xl font-semibold">{tab === 'login' ? 'Welcome back' : 'Account banao'}</h2>
          <p className="mt-1 text-sm text-muted">{tab === 'login' ? 'Apne account se sign in karo' : ''}</p>
          <div className="mt-6 grid grid-cols-2 rounded-md border border-line bg-panel2 p-1">
            {(['login', 'signup'] as const).map((t) => (
              <button key={t} type="button" onClick={() => { setTab(t); submit.reset() }}
                className={`rounded py-1.5 font-mono text-[11px] uppercase tracking-wider ${tab === t ? 'bg-accent/15 text-accent' : 'text-muted'}`}>
                {t === 'login' ? 'Login' : 'Sign up'}
              </button>
            ))}
          </div>
          <form onSubmit={onSubmit} className="mt-5 flex flex-col gap-3.5">
            {tab === 'signup' && (
              <label className="text-sm text-muted">Name
                <input className="input mt-1" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
              </label>
            )}
            <label className="text-sm text-muted">Email
              <input className="input mt-1" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </label>
            <label className="text-sm text-muted">Password
              <input className="input mt-1" type="password" required minLength={tab === 'signup' ? 8 : undefined}
                value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={tab === 'login' ? 'current-password' : 'new-password'} />
            </label>
            {submit.isError && <p className="rounded-md border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{errorMessage(submit.error)}</p>}
            {info && <p className="flex items-center gap-2 text-sm text-accent"><CheckCircle2 className="h-4 w-4" />{info}</p>}
            <Button type="submit" disabled={submit.isPending} className="mt-1 py-2.5">
              {submit.isPending ? 'Please wait…' : tab === 'login' ? 'Login' : 'Create account'}
            </Button>
          </form>
          {supabase && (
            <Button variant="secondary" className="mt-3 w-full"
              onClick={() => supabase!.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin } })}>
              Continue with Google
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
