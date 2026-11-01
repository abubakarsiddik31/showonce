import { Check } from '@phosphor-icons/react'

import { cn } from '../../lib/format'

export type StageState = 'todo' | 'now' | 'done'

export interface Stage {
  label: string
  state: StageState
}

/** Where you are in the story: show it, talk it through, watch the robot. */
export function Stepper({ stages }: { stages: Stage[] }) {
  return (
    <ol aria-label="Progress" className="flex items-center gap-2 text-sm">
      {stages.map((stage, i) => (
        <li
          key={stage.label}
          aria-current={stage.state === 'now' ? 'step' : undefined}
          className="flex items-center gap-2"
        >
          {i > 0 && (
            <span
              aria-hidden
              className={cn(
                'h-px w-5 sm:w-8',
                stage.state === 'todo' ? 'bg-line-strong' : 'bg-ink',
              )}
            />
          )}
          <span
            className={cn(
              'grid size-6 place-items-center rounded-full font-mono text-[11px] font-medium transition-colors',
              stage.state === 'done' && 'bg-ink text-canvas',
              stage.state === 'now' && 'bg-accent text-ink',
              stage.state === 'todo' && 'border border-line-strong text-ink-faint',
            )}
          >
            {stage.state === 'done' ? <Check size={12} weight="bold" /> : i + 1}
          </span>
          <span
            className={cn(
              stage.state === 'todo' ? 'text-ink-faint' : 'font-medium text-ink',
              stage.state !== 'now' && 'hidden sm:inline',
            )}
          >
            {stage.label}
          </span>
        </li>
      ))}
    </ol>
  )
}
