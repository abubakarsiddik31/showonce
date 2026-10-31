import type { ReactNode } from 'react'

interface Props {
  icon: ReactNode
  title: string
  children: ReactNode
}

export function EmptyState({ icon, title, children }: Props) {
  return (
    <div className="flex flex-col items-start gap-3 border-t border-line pt-6 text-ink-dim">
      <span className="text-ink-faint">{icon}</span>
      <p className="text-sm font-medium text-ink">{title}</p>
      <p className="max-w-[40ch] text-sm leading-relaxed">{children}</p>
    </div>
  )
}
