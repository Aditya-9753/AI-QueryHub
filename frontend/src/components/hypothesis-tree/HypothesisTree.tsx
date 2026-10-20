import { SourceChip, StatusChip } from '../qtrace/badges'

export interface TreeHypothesis {
  id: string
  statement: string
  source: 'metric_tree' | 'drilldown' | 'template' | 'llm'
  status: string
  parent_id: string | null
  depth: number
  priority?: number
}

/** Parent-child order me hypotheses + status chips + source badge. */
export default function HypothesisTree({ hypotheses }: { hypotheses: TreeHypothesis[] }) {
  const ids = new Set(hypotheses.map((h) => h.id))
  const roots = hypotheses.filter((h) => !h.parent_id || !ids.has(h.parent_id))
  const ordered: TreeHypothesis[] = []
  const walk = (h: TreeHypothesis) => {
    ordered.push(h)
    hypotheses.filter((c) => c.parent_id === h.id).forEach(walk)
  }
  roots.sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0)).forEach(walk)
  return (
    <ul className="divide-y divide-line/70">
      {ordered.map((h) => (
        <li key={h.id} className="flex flex-wrap items-center gap-2 py-2" style={{ paddingLeft: h.depth * 22 }}>
          {h.depth > 0 && <span className="font-mono text-dim">└</span>}
          <StatusChip status={h.status} />
          <span className="min-w-0 flex-1 text-sm text-muted">{h.statement}</span>
          <SourceChip source={h.source} />
        </li>
      ))}
    </ul>
  )
}
