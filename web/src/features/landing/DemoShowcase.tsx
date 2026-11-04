import { useState } from 'react'

import type { Demo } from '../../api/schemas'
import { Skeleton } from '../../components/Skeleton'
import { cn } from '../../lib/format'

type View = 'human' | 'robot' | 'shuffled'

const VIEWS: Array<[View, string]> = [
  ['human', 'You show it'],
  ['robot', 'It repeats'],
  ['shuffled', 'Shuffled table'],
]

const urlFor = (demo: Demo, view: View) =>
  view === 'human' ? demo.humanUrl : view === 'robot' ? demo.robotUrl : demo.shuffledUrl

/** The finished pairs: the clip it watched, the arm repeating it, and the same task on a new layout. */
export function DemoShowcase({ demos }: { demos: Demo[] | undefined }) {
  const [picked, setPicked] = useState<string | null>(null)
  const [view, setView] = useState<View>('robot')

  if (!demos) {
    return (
      <section id="watch" className="scroll-mt-24 py-14">
        <Skeleton className="aspect-video w-full rounded-3xl" />
      </section>
    )
  }
  if (demos.length === 0) return null

  const demo = demos.find((d) => d.id === picked) ?? demos[0]
  const shown = urlFor(demo, view) ? view : 'robot'
  const src = urlFor(demo, shown) ?? demo.robotUrl

  return (
    <section id="watch" aria-labelledby="watch-title" className="scroll-mt-24 py-14">
      <h2 id="watch-title" className="font-mono text-xs tracking-wide text-ink-faint uppercase">
        Watch it
      </h2>
      <p className="mt-4 max-w-[26ch] font-display text-4xl leading-[1.02] font-semibold tracking-tight">
        One clip in. The same job, done by an arm.
      </p>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="flex flex-col gap-3">
          <div className="viewport !rounded-3xl shadow-[0_40px_80px_-40px_rgba(17,21,26,0.55)]">
            <video
              key={src}
              src={src}
              autoPlay
              muted
              loop
              playsInline
              controls
              aria-label={`${demo.title}: ${VIEWS.find(([v]) => v === shown)?.[1]}`}
              className="aspect-video w-full object-cover"
            />
          </div>
          <div role="tablist" aria-label="Which video" className="flex flex-wrap gap-2">
            {VIEWS.filter(([v]) => urlFor(demo, v)).map(([v, label]) => (
              <button
                key={v}
                type="button"
                role="tab"
                aria-selected={shown === v}
                onClick={() => setView(v)}
                className={cn(
                  'rounded-full border px-4 py-1.5 text-sm transition-colors',
                  shown === v
                    ? 'border-ink bg-ink text-canvas'
                    : 'border-line-strong text-ink-dim hover:text-ink',
                )}
              >
                {label}
              </button>
            ))}
          </div>
          {demo.steps.length > 0 && (
            <p className="font-mono text-xs leading-relaxed text-ink-faint">
              Learned: {demo.steps.join(' → ')}
            </p>
          )}
        </div>

        <ul className="flex flex-col gap-2">
          {demos.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                onClick={() => setPicked(d.id)}
                aria-pressed={d.id === demo.id}
                className={cn(
                  'flex w-full items-center justify-between gap-3 rounded-2xl border p-4 text-left transition-colors',
                  d.id === demo.id ? 'border-ink bg-raised' : 'border-line hover:border-ink/40',
                )}
              >
                <span className="font-medium">{d.title}</span>
                <span className="font-mono text-[11px] whitespace-nowrap text-ink-faint">
                  {d.humanUrl ? (d.realFootage ? 'real footage' : 'AI clip') : 'no clip'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
