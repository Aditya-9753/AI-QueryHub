import { ArrowUpRight } from 'lucide-react'
import { ClaimChip, emphasizeNumbers } from './badges'
import type { ClaimT } from '../../services/qtrace'

/** Synthesis & claim provenance ledger: har sentence = claim type + evidence node IDs. */
export default function ClaimsList({ claims, onSelect }: { claims: ClaimT[]; onSelect?: (nodeIds: string[]) => void }) {
  return (
    <ol className="flex flex-col gap-2.5">
      {claims.map((c, i) => (
        <li key={i} className="rounded-md border border-line bg-panel2/60 p-3">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <ClaimChip type={c.claim_type} />
            <button onClick={() => onSelect?.(c.evidence_node_ids)} disabled={!onSelect}
              className="flex min-w-0 items-center gap-1 truncate font-mono text-[10.5px] text-accent enabled:hover:underline disabled:cursor-default">
              #{c.evidence_node_ids.slice(0, 2).join(' #')}{c.evidence_node_ids.length > 2 ? ` +${c.evidence_node_ids.length - 2}` : ''}
              {onSelect && <ArrowUpRight className="h-3 w-3 shrink-0" />}
            </button>
          </div>
          <p className="text-sm leading-relaxed text-muted">{emphasizeNumbers(c.sentence)}</p>
        </li>
      ))}
    </ol>
  )
}
