import { useQuery } from '@tanstack/react-query'
import { ExperimentAPI } from '../services/api'
import { InvestigateAPI } from '../services/qtrace'
import { useRole } from './useRole'

/** Experiment + latest report; queued/running ho to 1.5s par poll. */
export function useExperiment(id: string | null) {
  return useQuery({
    queryKey: ['experiment', id],
    queryFn: () => InvestigateAPI.get(id!),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data?.status === 'running' || q.state.data?.status === 'queued' ? 1500 : false),
  })
}

/** scope: mine = apne runs, team = sabke completed runs (team library). Viewer ke liye hamesha team. */
export function useExperiments(scope?: 'mine' | 'team' | 'all') {
  const { can } = useRole()
  const s = !can.investigate ? 'team' : scope ?? 'mine'
  return useQuery({ queryKey: ['experiments', s], queryFn: () => ExperimentAPI.list(s) })
}
