import { useQuery } from '@tanstack/react-query'
import { ExperimentAPI } from '../services/api'
import { InvestigateAPI } from '../services/qtrace'

/** Experiment + latest report; queued/running ho to 1.5s par poll. */
export function useExperiment(id: string | null) {
  return useQuery({
    queryKey: ['experiment', id],
    queryFn: () => InvestigateAPI.get(id!),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data?.status === 'running' || q.state.data?.status === 'queued' ? 1500 : false),
  })
}

export function useExperiments() {
  return useQuery({ queryKey: ['experiments'], queryFn: ExperimentAPI.list })
}
