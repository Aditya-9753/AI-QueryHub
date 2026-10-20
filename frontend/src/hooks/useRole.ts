import { useAuthStore } from '../store/useAuthStore'
import type { Role } from '../services/types'

export const ROLE_INFO: Record<Role, { label: string; desc: string; can: string[]; cannot: string[] }> = {
  admin: {
    label: 'Admin',
    desc: 'Poora control: users, connections, semantic layer, audit log',
    can: ['Ask / Analyze / Investigate', 'Challenge + Replay', 'Users ke roles badalna', 'Database connections jodna',
      'Metric definitions edit karna', 'Audit log dekhna'],
    cannot: [],
  },
  analyst: {
    label: 'Analyst',
    desc: 'Analysis ka poora workflow — governance admin ke paas',
    can: ['Ask / Analyze / Investigate', 'Challenge + Replay + Export', 'Queries save karna', 'Saari business tables'],
    cannot: ['Sensitive columns (email, phone)', 'Users / connections / metric edit', 'Audit log'],
  },
  viewer: {
    label: 'Viewer',
    desc: 'Read-mostly: semantic tables par sawaal aur reports',
    can: ['Ask / Analyze (orders, payments)', 'Investigations dekhna + chalana', 'Saved queries'],
    cannot: ['Customers / products tables', 'Sensitive columns', 'Admin settings'],
  },
}

export function useRole() {
  const role = (useAuthStore((s) => s.user?.role) ?? 'viewer') as Role
  return { role, isAdmin: role === 'admin', info: ROLE_INFO[role] }
}
