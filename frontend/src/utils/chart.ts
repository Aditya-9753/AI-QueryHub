/** Result shape se chart type: 1 row sirf numbers => KPI, date x-axis => line, category => bar. */
export type ChartKind = 'kpi' | 'bar' | 'line' | 'none'

export interface ChartSpec {
  kind: ChartKind
  x?: string
  ys: string[]
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isDateLike = (v: unknown) => typeof v === 'string' && /^\d{4}-\d{2}(-\d{2})?/.test(v)

export function inferChart(columns: string[], rows: unknown[][]): ChartSpec {
  if (!rows.length || !columns.length) return { kind: 'none', ys: [] }
  const numeric = columns.filter((_, i) => rows.every((r) => r[i] === null || isNum(r[i])) && rows.some((r) => isNum(r[i])))
  const others = columns.filter((c) => !numeric.includes(c))
  if (rows.length === 1 && others.length === 0) return { kind: 'kpi', ys: numeric }
  if (!numeric.length || !others.length || rows.length > 200) return { kind: 'none', ys: [] }
  const x = others[0]
  const xi = columns.indexOf(x)
  return { kind: rows.every((r) => isDateLike(r[xi])) ? 'line' : 'bar', x, ys: numeric.slice(0, 3) }
}

export const toChartData = (columns: string[], rows: unknown[][]) =>
  rows.map((r) => Object.fromEntries(columns.map((c, i) => [c, r[i]])))
