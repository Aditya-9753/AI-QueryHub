import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AppState {
  datasourceId: string
  setDatasourceId: (id: string) => void
  currentExperimentId: string | null
  setCurrentExperimentId: (id: string | null) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      datasourceId: 'default',
      setDatasourceId: (datasourceId) => set({ datasourceId }),
      currentExperimentId: null,
      setCurrentExperimentId: (currentExperimentId) => set({ currentExperimentId }),
    }),
    { name: 'qh_app' },
  ),
)
