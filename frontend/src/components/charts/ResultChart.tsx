import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { inferChart, toChartData } from '../../utils/chart'
import { fmtCompact, fmtNumber } from '../../utils/format'

const COLORS = ['#22d3ee', '#fbbf24', '#34d399']
const tick = { fontSize: 11, fill: '#93a4bd', fontFamily: 'JetBrains Mono' }
const tooltipFmt = (v: unknown) => (typeof v === 'number' ? fmtNumber(v) : String(v))
const tooltipStyle = { background: '#0d1524', border: '1px solid #2a3a57', borderRadius: 6, fontSize: 12 }

export default function ResultChart({ columns, rows, height = 300 }: { columns: string[]; rows: unknown[][]; height?: number }) {
  const spec = useMemo(() => inferChart(columns, rows), [columns, rows])
  const data = useMemo(() => toChartData(columns, rows), [columns, rows])

  if (spec.kind === 'none') {
    return <p className="py-8 text-center text-sm text-dim">Is result ke liye chart nahi banta — table dekho.</p>
  }
  if (spec.kind === 'kpi') {
    return (
      <div className="flex flex-wrap gap-10 py-5">
        {spec.ys.map((y) => (
          <div key={y}>
            <div className="label">{y}</div>
            <div className="mt-1 font-mono text-4xl font-semibold tabular-nums text-accent">{fmtNumber(Number(rows[0][columns.indexOf(y)]))}</div>
          </div>
        ))}
      </div>
    )
  }
  const axes = (
    <>
      <CartesianGrid vertical={false} stroke="#1c2940" />
      <XAxis dataKey={spec.x} tick={tick} axisLine={{ stroke: '#2a3a57' }} tickLine={false} />
      <YAxis tick={tick} tickFormatter={(v) => fmtCompact(Number(v))} width={64} axisLine={false} tickLine={false} />
      <Tooltip formatter={tooltipFmt} contentStyle={tooltipStyle} labelStyle={{ color: '#e6edf7' }} itemStyle={{ color: '#93a4bd' }} />
      {spec.ys.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: '#93a4bd' }} />}
    </>
  )
  return (
    <ResponsiveContainer width="100%" height={height}>
      {spec.kind === 'line' ? (
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          {axes}
          {spec.ys.map((y, i) => <Line key={y} dataKey={y} stroke={COLORS[i]} strokeWidth={2} dot={false} isAnimationActive={false} />)}
        </LineChart>
      ) : (
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          {axes}
          {spec.ys.map((y, i) => <Bar key={y} dataKey={y} fill={COLORS[i]} radius={[3, 3, 0, 0]} isAnimationActive={false} />)}
        </BarChart>
      )}
    </ResponsiveContainer>
  )
}
