import { useAuthStore } from '../store/useAuthStore'
import type { Role } from '../services/types'

/** Kaun kya kar sakta hai — backend (require_role / firewall policy) ka hi mirror; UI sirf wahi dikhata hai jo chalega. */
export interface Capabilities {
  manualSql: boolean        // Monaco me SQL likh kar chalana
  investigate: boolean      // naya investigation banana / chalana
  challenge: boolean        // finding ko counter-test karna
  replay: boolean           // exact replay / re-derive
  allTables: boolean        // customers / products bhi (viewer: sirf orders, payments)
  governance: boolean       // users, connections, metric edit, audit log
}

export interface RoleInfo {
  label: string
  persona: string
  desc: string
  tone: 'amber' | 'blue' | 'grey'
  can: string[]
  cannot: string[]
  caps: Capabilities
}

export const ROLE_INFO: Record<Role, RoleInfo> = {
  admin: {
    label: 'Admin',
    persona: 'Workspace owner',
    desc: 'Poora control: analysis + org-wide monitoring, users, connections, semantic layer, audit',
    tone: 'amber',
    can: ['Analyst ka sab kuch', 'Poore org ki queries, usage + LLM cost', 'Team accounts banana + roles badalna',
      'Sensitive columns (customers email / phone)', 'Database connections + metric definitions', 'Audit log + system config'],
    cannot: [],
    caps: { manualSql: true, investigate: true, challenge: true, replay: true, allTables: true, governance: true },
  },
  analyst: {
    label: 'Analyst',
    persona: 'Investigator',
    desc: 'Root cause dhoondhna: manual SQL, Q-TRACE+ investigations, challenge, replay',
    tone: 'blue',
    can: ['Ask / Analyze — saari business tables', 'Manual SQL (Monaco, firewalled)', 'Investigations chalana',
      'Findings challenge karna', 'Exact replay + re-derive', 'Team library publish/padhna'],
    cannot: ['Sensitive columns (email, phone)', 'Users / connections / metric edit', 'Audit log'],
    caps: { manualSql: true, investigate: true, challenge: true, replay: true, allTables: true, governance: false },
  },
  viewer: {
    label: 'Viewer',
    persona: 'Report consumer',
    desc: 'Plain-language sawaal + team ki published investigations padhna',
    tone: 'grey',
    can: ['Ask / Analyze in plain language', 'Team investigations + evidence padhna', 'Reports export (JSON / PDF)',
      'Saved queries'],
    cannot: ['Manual SQL', 'Naya investigation / challenge / replay', 'Customers / products tables', 'Admin settings'],
    caps: { manualSql: false, investigate: false, challenge: false, replay: false, allTables: false, governance: false },
  },
}

export function useRole() {
  const user = useAuthStore((s) => s.user)
  const role = (user?.role ?? 'viewer') as Role
  const info = ROLE_INFO[role]
  return { role, userId: user?.id, isAdmin: role === 'admin', isViewer: role === 'viewer', info, can: info.caps }
}
