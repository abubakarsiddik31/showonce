import { Eye } from '@phosphor-icons/react'
import { useCallback, useState } from 'react'

import type { Job, Sample } from '../../api/schemas'
import { Button } from '../../components/Button'
import { ErrorNote } from '../../components/ErrorNote'
import { LiveDot } from '../../components/LiveDot'
import { Panel, StatusPill } from '../../components/Panel'
import { Skeleton } from '../../components/Skeleton'
import { Timeline } from './Timeline'
import { VideoStage } from './VideoStage'

interface Props {
  sample: Sample
  job: Job | undefined
  starting: boolean
  startError: string | null
  onLearn: () => void
}

export function TeachPanel({ sample, job, starting, startError, onLearn }: Props) {
  const [time, setTime] = useState(0)
  const [seekTo, setSeekTo] = useState<number | null>(null)
  const learn = job?.learn ?? null
  const busy = starting || job?.status === 'queued' || job?.status === 'running'
  const handleTime = useCallback((s: number) => setTime(s), [])
  const seek = useCallback((s: number) => {
    setTime(s)
    setSeekTo(s)
  }, [])

  const status = busy ? (
    <StatusPill tone="live">Reading</StatusPill>
  ) : learn ? (
    <StatusPill tone="done">Learned</StatusPill>
  ) : (
    <StatusPill tone="idle">Ready</StatusPill>
  )

  return (
    <Panel
      id="panel-demo"
      title="Show it once"
      hint="One clip is all it gets. It looks at the table, follows every object with SAM 3.1, and Muse Spark watches the same video."
      status={status}
    >
      <VideoStage
        src={sample.videoUrl}
        learn={learn}
        time={time}
        onTime={handleTime}
        seekTo={seekTo}
      />

      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant={learn ? 'ghost' : 'primary'}
            size="lg"
            icon={<Eye size={20} />}
            disabled={busy}
            onClick={onLearn}
          >
            {learn ? 'Watch again' : 'Let the robot watch'}
          </Button>
          {busy && (
            <p className="flex items-center gap-2 text-sm text-ink-dim" aria-live="polite">
              <LiveDot />
              {job?.stage ?? 'Starting'}
            </p>
          )}
        </div>

        {busy && (
          <div className="flex flex-col gap-2" aria-hidden>
            <Skeleton className="h-3 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        )}

        {(startError ?? job?.error) && <ErrorNote message={(startError ?? job?.error) as string} />}

        {learn && !busy && (
          <details className="border-t border-line pt-3 text-sm">
            <summary className="w-fit cursor-pointer rounded-md py-1 text-xs text-ink-faint select-none hover:text-ink">
              What it tracked
            </summary>
            <div className="mt-3 flex flex-col gap-4">
              <Timeline learn={learn} time={time} onSeek={seek} />
              <dl className="grid grid-cols-3 gap-x-6">
                <Fact
                  label="Objects"
                  value={String(new Set(learn.rests.map((r) => r.object)).size)}
                />
                <Fact label="Moves seen" value={String(learn.moves.length)} />
                <Fact
                  label="Read by"
                  value={learn.source === 'geometry' ? 'Motion' : 'Muse Spark'}
                />
              </dl>
            </div>
          </details>
        )}
      </div>
    </Panel>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className="mt-1 font-display text-xl font-semibold">{value}</dd>
    </div>
  )
}
