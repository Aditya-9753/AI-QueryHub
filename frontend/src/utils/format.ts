import type { QueryErrorDetail } from '../services/types'

export const pct = (x: number, digits = 1) => `${(x * 100).toFixed(digits)}%`

export const lakh = (rupees: number, digits = 1) => `₹${(rupees / 1e5).toFixed(digits)} L`

export const crore = (rupees: number, digits = 2) => `₹${(rupees / 1e7).toFixed(digits)} Cr`

const NUM = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })
const COMPACT = new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 })

export const fmtNumber = (v: number) => NUM.format(v)
export const fmtCompact = (v: number) => COMPACT.format(v)

export const fmtCell = (v: unknown) => (typeof v === 'number' ? fmtNumber(v) : v === null || v === undefined ? '—' : String(v))

export const timeAgo = (iso: string) => {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'abhi'
  if (s < 3600) return `${Math.floor(s / 60)} min pehle`
  if (s < 86400) return `${Math.floor(s / 3600)} ghante pehle`
  return new Date(iso).toLocaleDateString()
}

type AxiosLike = { response?: { data?: { detail?: unknown } }; message?: string }

export const errorDetail = (e: unknown): QueryErrorDetail | null => {
  const d = (e as AxiosLike)?.response?.data?.detail
  return d && typeof d === 'object' && !Array.isArray(d) && 'message' in d ? (d as QueryErrorDetail) : null
}

export const errorMessage = (e: unknown): string => {
  const d = (e as AxiosLike)?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return d.map((x: { msg?: string; loc?: unknown[] }) => `${(x.loc ?? []).slice(1).join('.')}: ${x.msg}`).join('; ')
  }
  const obj = errorDetail(e)
  if (obj) return obj.message
  return (e as AxiosLike)?.message ?? 'Unknown error'
}

/** Measure value ko uske format ke hisaab se: money → ₹ Cr / L, pct (0..1) → %, number → en-IN compact. */
export function fmtMeasure(v: number | null | undefined, format?: 'pct' | 'money' | 'number', compact = true): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  if (format === 'pct') return `${(v * 100).toFixed(1)}%`
  if (format === 'money') {
    const a = Math.abs(v)
    if (a >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`
    if (a >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`
    return `₹${NUM.format(Math.round(v))}`
  }
  return compact && Math.abs(v) >= 1e4 ? COMPACT.format(v) : NUM.format(v)
}
