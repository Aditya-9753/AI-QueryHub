import { useState } from 'react'
import { useExperiments } from '../../hooks/useExperiment'
import { useRole } from '../../hooks/useRole'
import { useAppStore } from '../../store/useAppStore'
import Tabs from '../common/Tabs'

/** Analyst / admin: apne runs ya team library. Viewer: sirf team library (completed, read-only). */
export default function ExperimentPicker() {
  const { can } = useRole()
  const [scope, setScope] = useState<'mine' | 'team'>('mine')
  const { data } = useExperiments(scope)
  const { currentExperimentId, setCurrentExperimentId } = useAppStore()
  const items = data?.filter((e) => e.mode === 'INVESTIGATE') ?? []
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      {can.investigate
        ? <Tabs size="sm" value={scope} onChange={setScope} items={[{ value: 'mine', label: 'My runs' }, { value: 'team', label: 'Team library' }]} />
        : <span className="font-mono text-[10.5px] uppercase tracking-wider text-dim">Team library</span>}
      <select value={currentExperimentId ?? ''} onChange={(e) => setCurrentExperimentId(e.target.value || null)}
        className="input max-w-full py-1.5 sm:w-80">
        <option value="">— experiment chuno —</option>
        {items.map((e) => (
          <option key={e.id} value={e.id}>
            EXP-{e.id.slice(0, 6).toUpperCase()} · {e.question.slice(0, 54)}{scope === 'team' || !can.investigate ? ` · by ${e.owner ?? '—'}` : ` · ${e.status}`}
          </option>
        ))}
      </select>
    </div>
  )
}
