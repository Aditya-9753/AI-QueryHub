import type { ReactNode } from 'react'
import { ShieldAlert } from 'lucide-react'
import Empty from '../common/Empty'
import { useRole } from '../../hooks/useRole'
import type { Role } from '../../services/types'

/** UI-level guard (backend bhi har request par role check karta hai). */
export default function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { role } = useRole()
  if (!roles.includes(role)) {
    return (
      <Empty icon={<ShieldAlert className="h-8 w-8" />} title="Is page ke liye access nahi hai">
        Aapka role <b className="text-ink">{role}</b> hai. Ye section sirf {roles.join(' / ')} ke liye hai — admin se role badalne ko kaho.
      </Empty>
    )
  }
  return <>{children}</>
}
