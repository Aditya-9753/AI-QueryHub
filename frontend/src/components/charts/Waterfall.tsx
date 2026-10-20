import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { WaterfallStep } from '../../services/types'

interface Row extends WaterfallStep { base: number; bar: number; idx: number }

/** Decomposition bridge — stacked-bar trick (invisible base + visible delta). */
export default function Waterfall({ steps, unit = '₹ L', height = 320 }: { steps: WaterfallStep[]; unit?: string; height?: number }) {
  const data = useMemo<Row[]>(() => {
    let running = 0
    return steps.map((s, idx) => {
      if (s.kind === 'total') {
        running = s.value
        return { ...s, base: 0, bar: s.value, idx }
      }
      const start = running
      running += s.value
      return { ...s, base: Math.min(start, running), bar: Math.abs(s.value), idx }
    })
  }, [steps])
  const last = data.length - 1

  const fill = (d: Row) => {
    if (d.kind === 'total') return d.idx === last ? '#22d3ee' : '#2b5c68'
    if (d.dim) return '#2a3a57'
    return d.value < 0 ? '#e8968c' : '#34d399'
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 28, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid vertical={false} stroke="#1c2940" />
        <XAxis dataKey="label" tick={{ fontSize: 10.5, fill: '#93a4bd', fontFamily: 'JetBrains Mono' }} interval={0}
          axisLine={{ stroke: '#2a3a57' }} tickLine={false} />
        <YAxis tick={{ fontSize: 10.5, fill: '#62728b', fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} width={52} />
        <Tooltip
          cursor={{ fill: 'rgba(255,255,255,0.03)' }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const r = payload[0].payload as Row
            return (
              <div className="rounded-md border border-line2 bg-panel px-3 py-2 text-xs shadow-xl">
                <div className="font-medium text-ink">{r.label}</div>
                <div className="font-mono text-muted">{r.value > 0 && r.kind === 'delta' ? '+' : ''}{r.value.toFixed(2)} {unit}</div>
                {r.note && <div className="mt-0.5 text-dim">{r.note}</div>}
              </div>
            )
          }}
        />
        <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
        <Bar dataKey="bar" stackId="w" isAnimationActive={false} radius={[2, 2, 0, 0]}>
          {data.map((d) => <Cell key={d.idx} fill={fill(d)} />)}
          <LabelList dataKey="value" position="top" fontSize={10.5} fill="#e6edf7" fontFamily="JetBrains Mono"
            formatter={(v: number) => (v > 0 ? '' : '') + v.toFixed(1)} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
