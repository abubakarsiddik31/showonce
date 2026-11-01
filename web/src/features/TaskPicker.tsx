import type { Sample } from '../api/schemas'
import { cn, plural } from '../lib/format'

interface Props {
  samples: Sample[]
  selectedId: string | null
  onSelect: (id: string) => void
}

/** The demo clips as cards: the first frame, what it is, and how much is on the table. */
export function TaskPicker({ samples, selectedId, onSelect }: Props) {
  return (
    <nav aria-label="Demo clips" className="-mx-4 overflow-x-auto px-4 pb-2 sm:-mx-8 sm:px-8">
      <ul className="flex gap-3">
        {samples.map((s) => {
          const selected = selectedId === s.id
          return (
            <li key={s.id} className="shrink-0">
              <button
                type="button"
                onClick={() => onSelect(s.id)}
                aria-current={selected}
                className={cn(
                  'group flex w-44 flex-col gap-2 rounded-2xl border p-2 text-left transition-[transform,border-color,background-color] duration-200',
                  'active:scale-[0.98]',
                  selected
                    ? 'border-ink bg-raised'
                    : 'border-line bg-raised/60 hover:border-line-strong hover:bg-raised',
                )}
              >
                <span className="viewport block aspect-video rounded-lg">
                  <video
                    src={`${s.videoUrl}#t=0.1`}
                    muted
                    playsInline
                    preload="metadata"
                    tabIndex={-1}
                    aria-hidden
                    className="absolute inset-0 size-full object-cover"
                  />
                </span>
                <span className="px-1 pb-0.5">
                  <span className="block truncate text-sm font-medium capitalize">{s.name}</span>
                  <span className="block font-mono text-[11px] text-ink-faint">
                    {plural(s.objects.length, 'object')}
                    {s.durationS > 0 ? ` · ${Math.round(s.durationS)} s` : ''}
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
