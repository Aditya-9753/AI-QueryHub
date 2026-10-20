import { useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, Download } from 'lucide-react'
import type { ResultProfile } from '../../services/types'
import { fmtCell } from '../../utils/format'

function csvEscape(v: unknown): string {
  const s = v === null || v === undefined ? '' : String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function downloadCsv(columns: string[], rows: unknown[][], name = 'queryhub-result') {
  const csv = [columns.map(csvEscape).join(','), ...rows.map((r) => r.map(csvEscape).join(','))].join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `${name}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

/** Sortable result table; primary measure column me inline bar (max ke relative) + additive ho to share %. */
export default function ResultTable({ columns, rows, profile, maxHeight = 420 }: {
  columns: string[]; rows: unknown[][]; profile?: ResultProfile | null; maxHeight?: number
}) {
  const [sort, setSort] = useState<{ col: number; dir: 1 | -1 } | null>(null)
  const im = profile?.measure ? columns.indexOf(profile.measure) : -1
  const max = im >= 0 ? Math.max(...rows.map((r) => (typeof r[im] === 'number' ? Math.abs(r[im] as number) : 0)), 0) : 0
  const total = profile?.stats?.additive && profile.stats.total ? profile.stats.total : null
  const sorted = useMemo(() => {
    if (!sort) return rows
    const { col, dir } = sort
    return [...rows].sort((a, b) => {
      const x = a[col]
      const y = b[col]
      if (typeof x === 'number' && typeof y === 'number') return (x - y) * dir
      return String(x ?? '').localeCompare(String(y ?? ''), 'en', { numeric: true }) * dir
    })
  }, [rows, sort])
  const toggle = (i: number) => setSort((s) => (s?.col === i ? (s.dir === -1 ? { col: i, dir: 1 } : null) : { col: i, dir: -1 }))

  return (
    <div className="overflow-auto rounded-md border border-line" style={{ maxHeight }}>
      <table className="tbl">
        <thead className="sticky top-0 z-10 bg-panel">
          <tr>
            {columns.map((c, i) => (
              <th key={c} className={typeof rows[0]?.[i] === 'number' ? 'text-right' : ''}>
                <button onClick={() => toggle(i)} className="inline-flex items-center gap-1 uppercase hover:text-ink">
                  {c}
                  {sort?.col === i && (sort.dir === -1 ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />)}
                </button>
              </th>
            ))}
            {total !== null && <th className="text-right">share</th>}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, ri) => (
            <tr key={ri}>
              {r.map((v, j) => (
                <td key={j} className={`whitespace-nowrap ${typeof v === 'number' ? 'num text-right' : ''}`}>
                  {j === im && typeof v === 'number' && max > 0 ? (
                    <div className="flex items-center justify-end gap-2">
                      <span className="hidden h-1.5 w-24 overflow-hidden rounded-full bg-line sm:block">
                        <span className="block h-full rounded-full bg-accent/70" style={{ width: `${(Math.abs(v) / max) * 100}%` }} />
                      </span>
                      <span>{fmtCell(v)}</span>
                    </div>
                  ) : fmtCell(v)}
                </td>
              ))}
              {total !== null && <td className="num text-right text-muted">{typeof r[im] === 'number' ? `${(((r[im] as number) / total) * 100).toFixed(1)}%` : '—'}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function CsvButton({ columns, rows, name }: { columns: string[]; rows: unknown[][]; name?: string }) {
  return (
    <button onClick={() => downloadCsv(columns, rows, name)}
      className="inline-flex items-center gap-1.5 rounded border border-line px-2 py-1 font-mono text-[11px] uppercase tracking-wider text-muted hover:border-accent/50 hover:text-accent">
      <Download className="h-3.5 w-3.5" />CSV
    </button>
  )
}
