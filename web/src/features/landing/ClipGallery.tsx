import { UploadSimple } from '@phosphor-icons/react'

import type { Sample } from '../../api/schemas'
import { Skeleton } from '../../components/Skeleton'
import { groupSamples, plural } from '../../lib/format'
import { studioHref } from '../../lib/route'

interface Props {
  samples: Sample[] | undefined
  loading: boolean
  go: (href: string) => void
}

/** The demo clips, grouped by the kind of task. Each opens the studio on that clip. */
export function ClipGallery({ samples, loading, go }: Props) {
  return (
    <section id="clips" aria-labelledby="clips-title" className="scroll-mt-24 py-14">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="clips-title" className="font-mono text-xs tracking-wide text-ink-faint uppercase">
            Try a clip
          </h2>
          <p className="mt-4 max-w-[22ch] font-display text-4xl leading-[1.02] font-semibold tracking-tight">
            Pick a demo, or bring your own.
          </p>
        </div>
        <button
          type="button"
          onClick={() => go(studioHref({ upload: true }))}
          className="flex items-center gap-2 rounded-xl border border-line-strong px-4 py-2.5 text-sm font-medium transition-colors hover:bg-ink/5"
        >
          <UploadSimple size={18} /> Use my own clip
        </button>
      </div>

      {loading || !samples ? (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="aspect-[4/3] rounded-2xl" />
          ))}
        </div>
      ) : (
        groupSamples(samples).map(([group, items]) => (
          <div key={group} className="mt-10">
            <h3 className="mb-4 font-display text-xl font-semibold tracking-tight">{group}</h3>
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {items.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => go(studioHref({ clip: s.id }))}
                    className="group flex w-full flex-col gap-3 rounded-2xl border border-line bg-raised p-2.5 text-left transition-[transform,border-color] duration-200 hover:border-ink/40 active:scale-[0.99]"
                  >
                    <span className="viewport block aspect-video rounded-xl">
                      <video
                        src={`${s.videoUrl}#t=0.1`}
                        muted
                        playsInline
                        preload="metadata"
                        tabIndex={-1}
                        aria-hidden
                        className="absolute inset-0 size-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                      />
                    </span>
                    <span className="px-1 pb-1">
                      <span className="block font-medium">{s.title}</span>
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
        ))
      )}
    </section>
  )
}
