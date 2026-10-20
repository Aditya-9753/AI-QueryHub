export type Mode = 'ASK' | 'ANALYZE' | 'INVESTIGATE'
export type Role = 'admin' | 'analyst' | 'viewer'

export interface User {
  id: string
  email: string
  name?: string | null
  role: Role
  is_active: boolean
  created_at?: string | null
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface QueryRequest {
  question: string
  mode?: 'ASK' | 'ANALYZE' | null
  sql?: string | null
  datasource_id?: string | null
}

export interface QueryResult {
  history_id: string
  question: string
  mode: Mode
  datasource_id: string
  generated: boolean
  attempts: number
  sql: string
  columns: string[]
  rows: unknown[][]
  row_count: number
  duration_ms: number
  checksum: string
  answer: string
  answer_source: 'llm' | 'template'
  warnings: string[]
}

export interface QueryErrorDetail {
  message: string
  status: string
  sql?: string | null
  history_id?: string
}

export interface HistoryItem {
  id: string
  question: string
  mode: string
  datasource_id: string | null
  sql: string | null
  generated: boolean
  status: 'ok' | 'blocked' | 'error' | 'llm_error' | string
  error: string | null
  row_count: number | null
  duration_ms: number | null
  created_at: string
}

export interface SavedQuery {
  id: string
  name: string
  question: string
  sql: string
  mode: 'ASK' | 'ANALYZE'
  datasource_id: string | null
  chart_spec: Record<string, unknown> | null
  created_at: string
}

export interface DataSource {
  id: string
  name: string
  kind: 'postgres' | 'sqlite'
  conn_secret_ref: string
  readonly_role: string | null
  owner_id: string
  is_default: boolean
}

export interface ConnectionTest {
  ok: boolean
  dialect: string
  tables: number
  duration_ms: number
  error: string | null
}

export interface SchemaColumn {
  name: string
  type: string
  sensitive: boolean
  values: string[]
  min: string | null
  max: string | null
}

export interface SchemaTable {
  name: string
  columns: SchemaColumn[]
}

export interface SchemaInfo {
  datasource_id: string
  dialect: string
  tables: SchemaTable[]
}

export interface Experiment {
  id: string
  question: string
  mode: Mode
  status: string
  created_at: string
}

export interface ExperimentDetail extends Experiment {
  run_id: string | null
  stop_reason: string | null
  residual_share: number | null
  findings: { id: string; statement: string; share_of_delta: number | null; score: number | null; label: string | null }[]
}

export interface QuestionSpec {
  metric: string
  filters: Record<string, string>
  period_current: string
  period_base: string
  period_yoy?: string | null
  intent: 'lookup' | 'compare' | 'trend' | 'root_cause'
}

export type HypStatus =
  | 'proposed' | 'grounded' | 'ungrounded' | 'planned' | 'tested' | 'supported'
  | 'rejected' | 'inconclusive' | 'challenged' | 'upheld' | 'revised' | 'overturned'

export interface Hypothesis {
  id: string
  statement: string
  metric: string
  source: 'metric_tree' | 'drilldown' | 'template' | 'llm'
  prior: number
  priority: number
  parent_id: string | null
  depth: number
  test_type: string
  status: HypStatus
}

export interface MetricDefinition {
  id: string
  name: string
  definition: string
  formula_sql: string
  grain: string
  version: number
}

export interface AuditEntry {
  id: string
  user_id: string | null
  action: string
  object_ref: string | null
  sql_hash: string | null
  blocked: boolean
  reason: string | null
  ts: string
}

export interface WaterfallStep {
  label: string
  value: number
  kind: 'total' | 'delta'
  dim?: boolean
  note?: string
}
