import type { ReactNode } from 'react'
import Badge, { type Tone } from '../common/Badge'

const STATUS_TONE: Record<string, Tone> = {
  supported: 'solid', upheld: 'solid', revised: 'amber', rejected: 'red', overturned: 'red',
  inconclusive: 'amber', challenged: 'amber', not_tested: 'grey', tested: 'blue', grounded: 'blue',
  proposed: 'grey', ungrounded: 'red', planned: 'blue', passed: 'green', failed: 'red',
  completed: 'green', running: 'blue', queued: 'blue', created: 'grey', data_issue: 'red', within_normal: 'green',
}
const LABEL_TONE: Record<string, Tone> = { Strong: 'blue', Moderate: 'amber', Weak: 'grey', Insufficient: 'red' }
const CLAIM_TONE: Record<string, Tone> = { fact: 'solid', association: 'blue', interpretation: 'grey', recommendation: 'amber' }
const SOURCE: Record<string, string> = { metric_tree: 'metric tree', drilldown: 'drill-down', template: 'template', llm: 'LLM extra' }

export const StatusChip = ({ status }: { status: string }) => <Badge tone={STATUS_TONE[status] ?? 'grey'}>{status.replace('_', ' ')}</Badge>
export const LabelChip = ({ label }: { label: string | null }) => (label ? <Badge tone={LABEL_TONE[label] ?? 'grey'}>{label}</Badge> : null)
export const ClaimChip = ({ type }: { type: string }) => <Badge tone={CLAIM_TONE[type] ?? 'grey'}>{type}</Badge>
export const SourceChip = ({ source }: { source: string }) => <Badge tone="grey">{SOURCE[source] ?? source}</Badge>

export const pct = (x: number | null | undefined, digits = 1) => (x === null || x === undefined ? '—' : `${(x * 100).toFixed(digits)}%`)
export const money = (v: number | null | undefined, unit?: string) => {
  if (v === null || v === undefined) return '—'
  if (unit !== 'inr') return v.toLocaleString('en-IN', { maximumFractionDigits: 2 })
  const a = Math.abs(v)
  const s = v < 0 ? '-' : ''
  if (a >= 1e7) return `${s}₹${(a / 1e7).toFixed(2)} Cr`
  if (a >= 1e5) return `${s}₹${(a / 1e5).toFixed(2)} L`
  return `${s}₹${a.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

const NUM = /(-?₹?\d[\d,]*(?:\.\d+)?%?(?:\s?(?:L|Cr|din))?)/g
/** Narrative ke numbers highlight (sab evidence-grounded hain). */
export function emphasizeNumbers(text: string): ReactNode[] {
  // display-only: LLM narrative kabhi raw floats copy karta hai (-0.17503190587261797) -> 4 decimals
  const tidy = text.replace(/-?\d+\.\d{5,}/g, (m) => Number(m).toFixed(4))
  return tidy.split(NUM).map((part, i) => (i % 2 === 1 ? <b key={i} className="font-semibold text-ink">{part}</b> : part))
}

export const keyLabel = (key: string) => {
  const k = key.split('.').slice(1).join('.')
  if (k.includes('>')) return k.split('>')[1].replace('=', ' · ')
  return k.replace('dim:', 'dimension · ').replace(/_/g, ' ')
}
