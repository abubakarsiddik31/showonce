import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cn } from '../lib/format'

type Variant = 'primary' | 'ghost' | 'quiet'

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-accent text-canvas hover:bg-emerald-300 disabled:bg-white/10 disabled:text-ink-faint',
  ghost:
    'border border-line-strong text-ink hover:bg-white/5 disabled:text-ink-faint disabled:hover:bg-transparent',
  quiet: 'text-ink-dim hover:bg-white/5 hover:text-ink disabled:text-ink-faint',
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  icon?: ReactNode
}

export function Button({ variant = 'ghost', icon, className, children, ...rest }: Props) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex h-9 items-center justify-center gap-2 rounded-lg px-3.5 text-sm font-medium',
        'transition-[transform,background-color,color] duration-200 ease-out-expo',
        'active:scale-[0.98] active:-translate-y-px disabled:cursor-not-allowed disabled:active:scale-100',
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {icon}
      {children}
    </button>
  )
}
