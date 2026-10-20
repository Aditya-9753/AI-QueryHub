import { useExperiments } from '../../hooks/useExperiment'
import { useAppStore } from '../../store/useAppStore'

export default function ExperimentPicker() {
  const { data } = useExperiments()
  const { currentExperimentId, setCurrentExperimentId } = useAppStore()
  const items = data?.filter((e) => e.mode === 'INVESTIGATE') ?? []
  return (
    <select value={currentExperimentId ?? ''} onChange={(e) => setCurrentExperimentId(e.target.value || null)}
      className="input max-w-full py-1.5 sm:w-80">
      <option value="">— experiment chuno —</option>
      {items.map((e) => <option key={e.id} value={e.id}>EXP-{e.id.slice(0, 6).toUpperCase()} · {e.question.slice(0, 60)} · {e.status}</option>)}
    </select>
  )
}
