import { useMemo, useState } from 'react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Pie, PieChart, ReferenceDot, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { ResultProfile } from '../../services/types'
import { fmtMeasure } from '../../utils/format'
import Tabs from '../common/Tabs'
import ResultChart from '../charts/ResultChart'

// Design tokens (tailwind.config) — chart chrome recessive, data ink accent
const ACCENT = '#22d3ee'
const ACCENT_DIM = '#1b7f93'
const SURFACE = '#0d1524'
const GRID = '#1c2940'
const AXIS = '#2a3a57'
const INK2 = '#93a4bd'
// Categorical slots (dataviz reference palette, dark steps) — validator: PASS on #0d1524, fixed order, never cycled
const SERIES = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300']
const MAX_SLICES = 5          // part-to-whole: 5 slices + "Other"
const MAX_BARS = 15

const tick = { fontSize: 11, fill: INK2, fontFamily: 'JetBrains Mono' }
const tooltipStyle = { background: SURFACE, border: `1px solid ${AXIS}`, borderRadius: 6, fontSize: 12 }

type View = 'bar' | 'share' | 'area' | 'column' | 'grouped' | 'heatmap'
interface Pt { label: string; value: number }

export default function SmartChart({ columns, rows, profile, height = 320 }: {
  columns: string[]; rows: unknown[][]; profile: ResultProfile | null | undefined; height?: number
}) {
  const shape = profile?.shape
  const m = profile?.measure
  const d = profile?.dimension
  const fmt = (v: number) => fmtMeasure(v, profile?.format)
  const additive = !!profile?.stats?.additive

  const points: Pt[] = useMemo(() => {
    if (!m || !d) return []
    const im = columns.indexOf(m)
    const id = columns.indexOf(d)
    const pts = rows.filter((r) => typeof r[im] === 'number').map((r) => ({ label: String(r[id]), value: r[im] as number }))
    return shape === 'timeseries' ? pts.sort((a, b) => a.label.localeCompare(b.label, 'en', { numeric: true })) : pts.sort((a, b) => b.value - a.value)
  }, [columns, rows, m, d, shape])

  const canShare = shape === 'breakdown' && additive && points.length >= 2 && points.every((p) => p.value >= 0)
  const views: { value: View; label: string }[] = shape === 'breakdown'
    ? [{ value: 'bar', label: 'Ranked' }, ...(canShare ? [{ value: 'share' as View, label: 'Share' }] : [])]
    : shape === 'timeseries' ? [{ value: 'area', label: 'Trend' }, { value: 'column', label: 'Columns' }]
      : shape === 'matrix' ? [{ value: 'grouped', label: 'Grouped' }, { value: 'heatmap', label: 'Heatmap' }] : []
  const [view, setView] = useState<View | null>(null)
  const active = view && views.some((v) => v.value === view) ? view : views[0]?.value

  if (!profile || shape === 'table' || !m) return <ResultChart columns={columns} rows={rows} height={height} />

  if (shape === 'scalar') {
    const v = rows[0][columns.indexOf(m)] as number
    return (
      <div className="grid place-items-center py-10 text-center" style={{ minHeight: height * 0.6 }}>
        <div className="label">{m}</div>
        <div className="mt-2 font-mono text-5xl font-semibold tracking-tight text-accent sm:text-6xl">{fmtMeasure(v, profile.format, false)}</div>
        {profile.format === 'money' && <div className="mt-2 font-mono text-xs text-dim">₹{v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</div>}
      </div>
    )
  }

  const header = views.length > 1 && (
    <div className="mb-2 flex justify-end"><Tabs size="sm" value={active!} onChange={(v) => setView(v)} items={views} /></div>
  )

  // ---------------- breakdown
  if (shape === 'breakdown') {
    if (active === 'share') {
      const total = points.reduce((a, p) => a + p.value, 0)
      const head = points.slice(0, MAX_SLICES)
      const rest = points.slice(MAX_SLICES).reduce((a, p) => a + p.value, 0)
      const slices = rest > 0 ? [...head, { label: 'Other', value: rest }] : head
      return (
        <>
          {header}
          <div className="grid grid-cols-1 items-center gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <ResponsiveContainer width="100%" height={height - 40}>
              <PieChart>
                <Pie data={slices} dataKey="value" nameKey="label" innerRadius="58%" outerRadius="88%" paddingAngle={1.5}
                  stroke={SURFACE} strokeWidth={2} isAnimationActive={false}>
                  {slices.map((s, i) => <Cell key={s.label} fill={s.label === 'Other' ? '#3a4a66' : SERIES[i]} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: '#e6edf7' }} formatter={(v: number) => [`${fmt(v)} · ${((v / total) * 100).toFixed(1)}%`, m]} />
              </PieChart>
            </ResponsiveContainer>
            <ul className="flex flex-col gap-1.5">
              {slices.map((s, i) => (
                <li key={s.label} className="flex items-center gap-2 text-[13px]">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: s.label === 'Other' ? '#3a4a66' : SERIES[i] }} />
                  <span className="min-w-0 flex-1 truncate text-ink">{s.label}</span>
                  <span className="font-mono text-[12px] tabular-nums text-ink">{((s.value / total) * 100).toFixed(1)}%</span>
                  <span className="w-20 text-right font-mono text-[11px] tabular-nums text-dim">{fmt(s.value)}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )
    }
    const shown = points.slice(0, MAX_BARS)
    const top = shown[0]?.label
    const h = Math.max(160, shown.length * 34 + 24)
    return (
      <>
        {header}
        <ResponsiveContainer width="100%" height={h}>
          <BarChart data={shown} layout="vertical" margin={{ top: 4, right: 72, left: 4, bottom: 4 }} barCategoryGap={6}>
            <CartesianGrid horizontal={false} stroke={GRID} />
            <XAxis type="number" hide domain={[0, 'dataMax']} />
            <YAxis type="category" dataKey="label" tick={{ ...tick, fill: '#e6edf7' }} width={110} axisLine={{ stroke: AXIS }} tickLine={false} />
            <Tooltip cursor={{ fill: 'rgba(255,255,255,0.04)' }} contentStyle={tooltipStyle} itemStyle={{ color: '#e6edf7' }}
              formatter={(v: number) => [fmt(v), m]} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false} maxBarSize={22}>
              {shown.map((p) => <Cell key={p.label} fill={p.label === top ? ACCENT : ACCENT_DIM} />)}
              <LabelList dataKey="value" position="right" formatter={(v: number) => fmt(v)}
                style={{ fill: INK2, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {points.length > MAX_BARS && <p className="mt-1 font-mono text-[11px] text-dim">top {MAX_BARS} of {points.length} — baaki table me</p>}
      </>
    )
  }

  // ---------------- timeseries
  if (shape === 'timeseries') {
    const mean = points.reduce((a, p) => a + p.value, 0) / (points.length || 1)
    const peak = points.reduce((a, p) => (p.value > a.value ? p : a), points[0])
    const trough = points.reduce((a, p) => (p.value < a.value ? p : a), points[0])
    const axes = (
      <>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="label" tick={tick} axisLine={{ stroke: AXIS }} tickLine={false} minTickGap={16} />
        <YAxis tick={tick} tickFormatter={(v) => fmtMeasure(Number(v), profile.format)} width={72} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#e6edf7' }} itemStyle={{ color: ACCENT }}
          cursor={active === 'area' ? { stroke: AXIS, strokeWidth: 1 } : { fill: 'rgba(255,255,255,0.04)' }} formatter={(v: number) => [fmt(v), m]} />
        <ReferenceLine y={mean} stroke={INK2} strokeDasharray="4 4" strokeOpacity={0.6}
          label={{ value: 'avg', position: 'right', fill: INK2, fontSize: 10, fontFamily: 'JetBrains Mono' }} />
      </>
    )
    return (
      <>
        {header}
        <ResponsiveContainer width="100%" height={height}>
          {active === 'column' ? (
            <BarChart data={points} margin={{ top: 16, right: 32, left: 0, bottom: 0 }}>
              {axes}
              <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false} maxBarSize={36}>
                {points.map((p) => <Cell key={p.label} fill={p.label === peak?.label ? ACCENT : ACCENT_DIM} />)}
              </Bar>
            </BarChart>
          ) : (
            <AreaChart data={points} margin={{ top: 16, right: 32, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="qhArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={ACCENT} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={ACCENT} stopOpacity={0} />
                </linearGradient>
              </defs>
              {axes}
              <Area dataKey="value" stroke={ACCENT} strokeWidth={2} fill="url(#qhArea)" isAnimationActive={false}
                dot={points.length <= 24 ? { r: 3, fill: ACCENT, stroke: SURFACE, strokeWidth: 2 } : false}
                activeDot={{ r: 5, fill: ACCENT, stroke: SURFACE, strokeWidth: 2 }} />
              {peak && <ReferenceDot x={peak.label} y={peak.value} r={5} fill="#34d399" stroke={SURFACE} strokeWidth={2}
                label={{ value: `▲ ${fmt(peak.value)}`, position: 'top', fill: '#34d399', fontSize: 10, fontFamily: 'JetBrains Mono' }} />}
              {trough && trough.label !== peak?.label && <ReferenceDot x={trough.label} y={trough.value} r={5} fill="#f87171" stroke={SURFACE} strokeWidth={2}
                label={{ value: `▼ ${fmt(trough.value)}`, position: 'bottom', fill: '#f87171', fontSize: 10, fontFamily: 'JetBrains Mono' }} />}
            </AreaChart>
          )}
        </ResponsiveContainer>
      </>
    )
  }

  // ---------------- matrix (2 dimensions × measure)
  const dims = columns.filter((c) => profile.roles[c] === 'time' || profile.roles[c] === 'dimension').slice(0, 2)
  if (dims.length < 2) return <ResultChart columns={columns} rows={rows} height={height} />
  const [a, b] = dims
  const ia = columns.indexOf(a)
  const ib = columns.indexOf(b)
  const im = columns.indexOf(m)
  const aVals = [...new Set(rows.map((r) => String(r[ia])))]
  const bVals = [...new Set(rows.map((r) => String(r[ib])))].sort()
  const cell = new Map(rows.map((r) => [`${r[ia]}|${r[ib]}`, typeof r[im] === 'number' ? (r[im] as number) : null]))

  if (active === 'grouped' && bVals.length <= SERIES.length) {
    const data = aVals.map((x) => ({ label: x, ...Object.fromEntries(bVals.map((y) => [y, cell.get(`${x}|${y}`) ?? 0])) }))
    return (
      <>
        {header}
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }} barGap={2}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" tick={tick} axisLine={{ stroke: AXIS }} tickLine={false} />
            <YAxis tick={tick} tickFormatter={(v) => fmtMeasure(Number(v), profile.format)} width={72} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: 'rgba(255,255,255,0.04)' }} contentStyle={tooltipStyle} labelStyle={{ color: '#e6edf7' }} formatter={(v: number, k) => [fmt(v), k]} />
            <Legend wrapperStyle={{ fontSize: 12, color: INK2 }} iconType="square" />
            {bVals.map((y, i) => <Bar key={y} dataKey={y} fill={SERIES[i]} radius={[3, 3, 0, 0]} isAnimationActive={false} maxBarSize={28} />)}
          </BarChart>
        </ResponsiveContainer>
      </>
    )
  }
  const max = Math.max(...[...cell.values()].map((v) => v ?? 0), 1)
  return (
    <>
      {header}
      {active === 'grouped' && <p className="mb-2 font-mono text-[11px] text-dim">{bVals.length} {b} values — grouped bars ke liye zyada, heatmap dikhaya</p>}
      <div className="overflow-x-auto">
        <table className="w-full border-separate" style={{ borderSpacing: 2 }}>
          <thead><tr><th className="label px-2 py-1 text-left">{a} \ {b}</th>{bVals.map((y) => <th key={y} className="label px-2 py-1 text-right">{y}</th>)}</tr></thead>
          <tbody>
            {aVals.map((x) => (
              <tr key={x}>
                <td className="whitespace-nowrap px-2 py-1.5 text-[12.5px] text-ink">{x}</td>
                {bVals.map((y) => {
                  const v = cell.get(`${x}|${y}`)
                  const t = v === null || v === undefined ? 0 : v / max
                  return (
                    <td key={y} className="rounded px-2 py-1.5 text-right font-mono text-[11.5px] tabular-nums"
                      style={{ background: `rgba(34,211,238,${(0.06 + t * 0.6).toFixed(3)})`, color: t > 0.55 ? '#03202a' : '#e6edf7' }}
                      title={`${x} × ${y}: ${v === null || v === undefined ? '—' : fmt(v)}`}>
                      {v === null || v === undefined ? '—' : fmt(v)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
