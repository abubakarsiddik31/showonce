import { useMemo } from 'react'

import type { LearnResult } from '../../api/schemas'
import { cn, formatTime, objectTone } from '../../lib/format'

interface Props {
  learn: LearnResult
  time: number
  onSeek: (seconds: number) => void
}

/** One lane per object. A bar is a stretch where the object was carried somewhere new. */
export function Timeline({ learn, time, onSeek }: Props) {
  const lanes = useMemo(() => [...new Set(learn.rests.map((r) => r.object))], [learn.rests])
  const total = Math.max(learn.durationS, 0.1)
  const pct = (s: number) => `${Math.min(100, Math.max(0, (s / total) * 100))}%`

  function seek(event: React.MouseEvent<HTMLDivElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    onSeek(((event.clientX - box.left) / box.width) * total)
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        role="slider"
        tabIndex={0}
        aria-label="Demo timeline"
        aria-valuemin={0}
        aria-valuemax={Math.round(total)}
        aria-valuenow={Math.round(time)}
        aria-valuetext={formatTime(time)}
        onClick={seek}
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight') onSeek(Math.min(total, time + 1))
          if (e.key === 'ArrowLeft') onSeek(Math.max(0, time - 1))
        }}
        className="relative cursor-pointer rounded-lg py-1"
      >
        {lanes.map((name) => (
          <div key={name} className="flex flex-col gap-1 border-b border-line py-1.5 last:border-0">
            <span className="truncate font-mono text-[11px] text-ink-faint">{name}</span>
            <div className="relative h-3">
              {learn.moves
                .filter((m) => m.object === name)
                .map((m) => (
                  <span
                    key={`${m.startS}-${m.endS}`}
                    className="absolute inset-y-0 rounded-sm"
                    style={{
                      left: pct(m.startS),
                      width: `calc(${pct(m.endS)} - ${pct(m.startS)})`,
                      minWidth: 6,
                      background: objectTone(name),
                    }}
                  />
                ))}
            </div>
          </div>
        ))}
        <span
          className={cn('pointer-events-none absolute inset-y-0 w-px bg-ink')}
          style={{ left: pct(time) }}
        />
      </div>
      <div className="flex justify-between font-mono text-[11px] text-ink-faint">
        <span>{formatTime(0)}</span>
        <span>{formatTime(total)}</span>
      </div>
    </div>
  )
}
