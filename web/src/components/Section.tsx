import type { ReactNode } from 'react'

interface Props {
  index: string
  title: string
  hint: string
  aside?: ReactNode
  children: ReactNode
}

/** A numbered workbench column: heading on top, content below, separated by space and a hairline. */
export function Section({ index, title, hint, aside, children }: Props) {
  return (
    <section aria-labelledby={`sec-${index}`} className="flex min-w-0 flex-col gap-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs text-ink-faint">{index}</p>
          <h2 id={`sec-${index}`} className="mt-1 text-lg font-semibold tracking-tight">
            {title}
          </h2>
          <p className="mt-1 max-w-[46ch] text-sm leading-relaxed text-ink-dim">{hint}</p>
        </div>
        {aside}
      </header>
      {children}
    </section>
  )
}
