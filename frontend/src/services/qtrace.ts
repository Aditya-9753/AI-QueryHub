/** INVESTIGATE (Q-TRACE+) API types + calls. */
import { api } from './api'

export type FindingStatus =
  | 'tested' | 'supported' | 'rejected' | 'inconclusive' | 'challenged' | 'upheld' | 'revised' | 'overturned' | 'not_tested'

export interface HealthCheck { check_name: string; expected: string; observed: string; passed: boolean; severity: string }
export interface Gate {
  method: 'ets' | 'yoy' | 'none'
  z: number | null
  status: 'anomaly' | 'within_normal' | 'insufficient_history'
  actual?: number
  unit?: string
  months_available?: number
  band?: { forecast: number; sigma: number; low: number; high: number; sigma_resid?: number; current_se?: number }
  yoy?: { ty: number; ly: number; excess: number; se_excess: number; z: number }
}
export interface ClaimT {
  sentence: string
  claim_type: 'fact' | 'association' | 'interpretation' | 'recommendation'
  evidence_node_ids: string[]
  finding_key?: string | null
}
export interface ReportFinding {
  key: string
  hypothesis_id: string
  statement: string
  status: FindingStatus
  share_of_delta: number
  effect: number
  amount: number | null
  ci: [number, number] | null
  p_value: number | null
  q_value: number | null
  score: number | null
  label: 'Strong' | 'Moderate' | 'Weak' | 'Insufficient' | null
  components: Record<string, number>
  contradiction_penalty: number
  challenges: { type: string; passed: boolean; detail: string; origin: string }[]
  method: string
  source: string
  depth: number
  parent_id: string | null
  notes: string[]
  data: Record<string, unknown>
}
export interface ReportHypothesis {
  id: string
  statement: string
  source: 'metric_tree' | 'drilldown' | 'template' | 'llm'
  status: string
  priority: number
  prior: number
  parent_id: string | null
  depth: number
}
export interface QueryRec { id: string; purpose: string; sql: string; sql_hash: string; checksum: string; row_count: number; duration_ms: number; hypothesis_key: string | null }
export interface GraphNode { id: string; data: Record<string, unknown> & { label: string; kind: string } }
export interface GraphEdge { id: string; source: string; target: string; label: string; animated: boolean }
export interface Report {
  status: 'completed' | 'data_issue' | 'within_normal' | 'no_change'
  question: string | null
  spec: { metric: string; filters: Record<string, string>; period_current: string; period_base: string; controls: string[] }
  parse_source: string
  verify: { health: { ok: boolean; days_with_data: number; expected_days: number; checks: HealthCheck[] }; gate: Gate }
  core: Record<string, number | string>
  findings: ReportFinding[]
  frontier: string[]
  hypotheses: ReportHypothesis[]
  claims: ClaimT[]
  graph: { nodes: GraphNode[]; edges: GraphEdge[] }
  queries: QueryRec[]
  stop_reason: string | null
  explained: number | null
  residual_share: number | null
  controls: string[]
  reconciliation: Record<string, unknown>
  grounding: { source?: string; violations?: number; checked_numbers?: number }
  budget: { queries: number; llm_calls: number; max_queries: number; max_llm_calls: number }
  duration_ms: number
  notes: string[]
  dataset_version?: string
  schema_snapshot?: string
  steps?: { phase: string; type: string; ref: string | null; from: string | null; to: string | null; ts: string }[]
}
export interface RunMeta { id: string; created_at: string; replay_mode: string; dataset_version: string | null; model_version: string | null; semantic_layer_version: string | null; duration_ms: number | null }
export interface ExperimentFull {
  id: string
  question: string
  mode: string
  status: 'created' | 'queued' | 'running' | 'completed' | 'failed'
  error: string | null
  datasource_id: string | null
  created_at: string
  user_id?: string | null
  run: RunMeta | null
  report: Report | null
}
export interface WaterfallData {
  status: string
  unit?: string
  base?: number
  current?: number
  period_base?: string
  period_current?: string
  residual?: number
  steps: { key: string; factor: string; amount: number; share: number; status: string; label: string | null; dimension?: string }[]
}
export interface FindingRow {
  id: string
  key: string
  statement: string
  status: string
  label: string | null
  score: number | null
  share: number | null
  challenges: { id: string; type: string; origin: string; status: string; result: Record<string, unknown> | null }[]
}
export interface ReplayResult {
  mode: 'exact' | 'rederive'
  run_id: string
  warnings?: string[]
  queries?: number
  matched?: number
  match?: boolean
  details?: { purpose: string; original: string; replayed: string | null; match: boolean }[]
  stable?: boolean
  findings?: { key: string; status_old: string | null; status_new: string | null; share_old: number | null; share_new: number | null; same: boolean }[]
}

const d = <T,>(p: Promise<{ data: T }>) => p.then((r) => r.data)

export const InvestigateAPI = {
  create: (question: string, datasource_id: string | null) =>
    d(api.post<{ id: string; status: string }>('/api/experiments', { question, mode: 'INVESTIGATE', datasource_id })),
  run: (id: string) => d(api.post<{ status: string; runner: string }>(`/api/experiments/${id}/run`)),
  get: (id: string) => d(api.get<ExperimentFull>(`/api/experiments/${id}`)),
  waterfall: (id: string) => d(api.get<WaterfallData>(`/api/experiments/${id}/decomposition`)),
  evidence: (id: string) => d(api.get<{ graph: Report['graph']; claims: ClaimT[]; queries: QueryRec[] }>(`/api/experiments/${id}/evidence`)),
  timeline: (id: string) => d(api.get<{ type: string; ref: string | null; from: string | null; to: string | null; ts: string }[]>(`/api/experiments/${id}/timeline`)),
  findings: (id: string) => d(api.get<FindingRow[]>(`/api/experiments/${id}/findings`)),
  replay: (id: string, mode: 'exact' | 'rederive') => d(api.post<ReplayResult>(`/api/experiments/${id}/replay`, { mode })),
  challenge: (finding_id: string, type: string, description?: string) =>
    d(api.post('/api/challenges', { finding_id, type, description })),
  exportFile: async (id: string, format: 'json' | 'pdf') => {
    const r = await api.get(`/api/experiments/${id}/export`, { params: { format }, responseType: 'blob' })
    const url = URL.createObjectURL(r.data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `experiment-${id.slice(0, 8)}.${format}`
    a.click()
    URL.revokeObjectURL(url)
  },
}

export const EvalAPI = {
  latest: () => d(api.get<Record<string, unknown | null>>('/api/eval/latest')),
}
