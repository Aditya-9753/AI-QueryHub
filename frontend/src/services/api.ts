import axios from 'axios'
import { useAuthStore } from '../store/useAuthStore'
import type {
  AuditEntry, AuthResponse, ConnectionTest, DataSource, Experiment, ExperimentDetail, HistoryItem, Hypothesis, MetricDefinition,
  QueryRequest, QueryResult, QuestionSpec, SavedQuery, SchemaInfo, User,
} from './types'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '' })

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    // token expire / user disable => logout (ProtectedRoute login par bhej dega)
    if (err?.response?.status === 401 && useAuthStore.getState().token) useAuthStore.getState().logout()
    return Promise.reject(err)
  },
)

const data = <T,>(p: Promise<{ data: T }>) => p.then((r) => r.data)

export const AuthAPI = {
  login: (email: string, password: string) => data(api.post<AuthResponse>('/api/auth/login', { email, password })),
  signup: (email: string, password: string, name?: string) =>
    data(api.post<AuthResponse>('/api/auth/signup', { email, password, name })),
  me: () => data(api.get<User>('/api/auth/me')),
}

export const QueryAPI = {
  run: (req: QueryRequest) => data(api.post<QueryResult>('/api/query', req)),
  history: (limit = 50) => data(api.get<HistoryItem[]>('/api/query/history', { params: { limit } })),
}

export const SavedAPI = {
  list: () => data(api.get<SavedQuery[]>('/api/saved-queries')),
  create: (body: Omit<SavedQuery, 'id' | 'created_at' | 'chart_spec'> & { chart_spec?: Record<string, unknown> | null }) =>
    data(api.post<SavedQuery>('/api/saved-queries', body)),
  run: (id: string) => data(api.post<QueryResult>(`/api/saved-queries/${id}/run`)),
  remove: (id: string) => api.delete(`/api/saved-queries/${id}`),
}

export const DataSourceAPI = {
  list: () => data(api.get<DataSource[]>('/api/datasources')),
  create: (body: Pick<DataSource, 'name' | 'kind' | 'conn_secret_ref'>) => data(api.post<DataSource>('/api/datasources', body)),
  test: (id: string) => data(api.post<ConnectionTest>(`/api/datasources/${id}/test`)),
  remove: (id: string) => api.delete(`/api/datasources/${id}`),
}

export const SchemaAPI = {
  get: (datasourceId: string, refresh = false) =>
    data(api.get<SchemaInfo>('/api/schema', { params: { datasource_id: datasourceId, refresh } })),
}

export const ExperimentAPI = {
  list: (scope: 'mine' | 'team' = 'mine') => data(api.get<Experiment[]>('/api/experiments', { params: { scope } })),
  create: (question: string) => data(api.post<Experiment>('/api/experiments', { question, mode: 'INVESTIGATE' })),
  get: (id: string) => data(api.get<ExperimentDetail>(`/api/experiments/${id}`)),
  run: (id: string) => data(api.post(`/api/experiments/${id}/run`)),
}

export const HypothesisAPI = {
  preview: (spec: QuestionSpec) => data(api.post<Hypothesis[]>('/api/hypotheses/generate', spec)),
}

export const MetricsAPI = {
  list: () => data(api.get<MetricDefinition[]>('/api/metrics')),
}

export const AdminAPI = {
  audit: () => data(api.get<AuditEntry[]>('/api/admin/audit')),
  users: () => data(api.get<User[]>('/api/admin/users')),
  updateUser: (id: string, patch: Partial<Pick<User, 'role' | 'is_active'>>) =>
    data(api.patch<User>(`/api/admin/users/${id}`, patch)),
}
