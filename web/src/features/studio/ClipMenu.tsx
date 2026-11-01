import { CaretDown } from '@phosphor-icons/react'
import { useEffect, useRef } from 'react'

import type { Sample } from '../../api/schemas'
import { cn, groupSamples, plural } from '../../lib/format'

interface Props {
  samples: Sample[]
  /** The clip being worked on, or null when it is one you uploaded. */
  selected: Sample | null
  label: string
  onSelect: (id: string) => void
}

/** Pick a demo clip, with the clips grouped by the kind of task they show. */
export function ClipMenu({ samples, selected, label, onSelect }: Props) {
  const ref = useRef<HTMLDetailsElement>(null)

  // A <details> has no click-away, so add it.
  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (ref.current?.open && !ref.current.contains(e.target as Node)) ref.current.open = false
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  return (
    <details ref={ref} className="relative">
      <summary className="flex h-9 cursor-pointer list-none items-center gap-2 rounded-lg border border-line-strong px-3 text-sm font-medium select-none hover:bg-ink/5 [&::-webkit-details-marker]:hidden">
        <span className="max-w-[9ch] truncate sm:max-w-[24ch]">{label}</span>
        <CaretDown size={14} aria-hidden />
      </summary>
      <div className="absolute right-0 z-30 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-2xl border border-line-strong bg-raised p-2 shadow-[0_24px_48px_-24px_rgba(17,21,26,0.5)]">
        {groupSamples(samples).map(([group, items]) => (
          <div key={group} className="py-1">
            <p className="px-2 pt-1 pb-1.5 font-mono text-[11px] tracking-wide text-ink-faint uppercase">
              {group}
            </p>
            <ul>
              {items.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(s.id)
                      if (ref.current) ref.current.open = false
                    }}
                    className={cn(
                      'flex w-full items-center gap-3 rounded-xl p-2 text-left transition-colors hover:bg-ink/5',
                      selected?.id === s.id && 'bg-ink/[0.06]',
                    )}
                  >
                    <span className="viewport block aspect-video w-16 shrink-0 rounded-md">
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
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">{s.title}</span>
                      <span className="block font-mono text-[11px] text-ink-faint">
                        {plural(s.objects.length, 'object')}
                        {s.durationS > 0 ? ` · ${Math.round(s.durationS)} s` : ''}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </details>
  )
}
