import type { ReactNode } from 'react'

import { cn } from '../lib/format'

export type Tone = 'idle' | 'live' | 'done' | 'bad'

const PILL: Record<Tone, string> = {
  idle: 'bg-ink/8 text-ink-dim',
  live: 'bg-accent/20 text-ink',
  done: 'bg-ok/15 text-ok',
  bad: 'bg-danger/15 text-danger',
}

/** A small label for where a stage stands: waiting, working, done or failed. */
export function StatusPill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] font-medium',
        PILL[tone],
      )}
    >
      {tone === 'live' && <span className="size-1.5 rounded-full bg-accent" aria-hidden />}
      {children}
    </span>
  )
}

interface Props {
  id: string
  title: string
  hint: string
  status: ReactNode
  /** A stage that cannot start yet is dimmed, so the eye goes to the one that can. */
  waiting?: boolean
  aside?: ReactNode
  children: ReactNode
}

/** One stage of the story: a heading, where it stands, and its content. */
export function Panel({ id, title, hint, status, waiting, aside, children }: Props) {
  return (
    <section
      aria-labelledby={id}
      className={cn(
        'flex min-w-0 flex-col gap-5 rounded-3xl border border-line bg-raised p-5 transition-opacity duration-500 sm:p-6',
        waiting && 'opacity-60',
      )}
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id={id} className="font-display text-2xl font-semibold tracking-tight">
            {title}
          </h2>
          <p className="mt-1 max-w-[44ch] text-sm leading-relaxed text-ink-dim">{hint}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {aside}
          {status}
        </div>
      </header>
      {children}
    </section>
  )
}
