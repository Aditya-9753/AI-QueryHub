import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'

const STYLES: Record<Variant, string> = {
  primary: 'bg-accent font-semibold text-accent-ink hover:bg-cyan-300 disabled:bg-accent/30 disabled:text-accent-ink/60',
  secondary: 'border border-line2 bg-panel2 text-ink hover:border-accent/60 hover:text-accent disabled:opacity-50',
  danger: 'border border-bad/50 bg-bad/10 text-bad hover:bg-bad/20',
  ghost: 'text-muted hover:bg-white/5 hover:text-ink',
}

export default function Button({ variant = 'primary', className = '', ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm transition-colors disabled:cursor-not-allowed ${STYLES[variant]} ${className}`}
      {...props}
    />
  )
}
