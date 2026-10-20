import {
  Activity, AlertTriangle, ArrowUpDown, Crown, Grid3x3, Hash, Mountain, PieChart, TrendingDown, TrendingUp, Zap,
} from 'lucide-react'
import type { Insight } from '../../services/types'
import { emphasizeNumbers } from '../qtrace/badges'

const ICON: Record<string, typeof Crown> = {
  top: Crown, concentration: PieChart, spread: ArrowUpDown, outlier: AlertTriangle, peak: Mountain, move: Zap,
  slope: Activity, pattern: Grid3x3, value: Hash,
}
// tone sirf icon + border ka rang; meaning hamesha title + text me bhi hai (color-alone nahi)
const TONE: Record<Insight['tone'], string> = {
  accent: 'border-l-accent text-accent', ok: 'border-l-ok text-ok', bad: 'border-l-bad text-bad',
  warn: 'border-l-warn text-warn', neutral: 'border-l-line2 text-muted',
}

export default function InsightCards({ insights, rows }: { insights: Insight[]; rows: number }) {
  if (!insights.length) return <p className="text-sm text-dim">Is result shape ke liye koi insight nahi bani.</p>
  return (
    <div className="flex flex-col">
      <ul className="flex flex-col gap-2">
        {insights.map((ins, i) => {
          const Icon = ins.kind === 'trend'
            ? (Number(ins.values.change ?? 0) < 0 ? TrendingDown : TrendingUp)
            : ICON[ins.kind] ?? Activity
          return (
            <li key={i} className={`rounded-md border border-line border-l-2 bg-panel2/50 px-3 py-2.5 ${TONE[ins.tone].split(' ')[0]}`}>
              <div className="flex items-center gap-2">
                <Icon className={`h-4 w-4 shrink-0 ${TONE[ins.tone].split(' ')[1]}`} />
                <span className="text-[13px] font-semibold text-ink">{ins.title}</span>
              </div>
              <p className="mt-1 text-[13px] leading-relaxed text-muted">{emphasizeNumbers(ins.text)}</p>
            </li>
          )
        })}
      </ul>
      <p className="pt-3 font-mono text-[10.5px] text-dim">deterministic · computed from {rows.toLocaleString('en-IN')} result rows · no LLM</p>
    </div>
  )
}
