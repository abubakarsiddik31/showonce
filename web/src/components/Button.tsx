import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cn } from '../lib/format'

type Variant = 'primary' | 'ghost' | 'quiet'

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-accent text-ink hover:bg-accent-hover disabled:bg-ink/10 disabled:text-ink-faint shadow-[0_1px_0_rgb(255_255_255/0.4)_inset]',
  ghost:
    'border border-line-strong text-ink hover:bg-ink/5 disabled:text-ink-faint disabled:hover:bg-transparent',
  quiet: 'text-ink-dim hover:bg-ink/5 hover:text-ink disabled:text-ink-faint',
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  icon?: ReactNode
  size?: 'md' | 'lg'
}

export function Button({
  variant = 'ghost',
  size = 'md',
  icon,
  className,
  children,
  ...rest
}: Props) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap',
        size === 'lg' ? 'h-12 rounded-xl px-5 text-base' : 'h-9 px-3.5 text-sm',
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
