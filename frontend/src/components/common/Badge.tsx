import type { ReactNode } from 'react'

const TONES = {
  green: 'border-ok/40 bg-ok/10 text-ok',
  red: 'border-bad/50 bg-bad/10 text-bad',
  amber: 'border-warn/40 bg-warn/10 text-warn',
  blue: 'border-accent/50 bg-accent/10 text-accent',
  grey: 'border-line2 bg-panel2 text-muted',
  solid: 'border-accent bg-accent text-accent-ink',
}

export type Tone = keyof typeof TONES

export default function Badge({ tone = 'grey', children, className = '' }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[10.5px] font-medium uppercase tracking-wider ${TONES[tone]} ${className}`}>
      {children}
    </span>
  )
}
