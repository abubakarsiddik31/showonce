import { Eye } from '@phosphor-icons/react'
import { useCallback, useState } from 'react'

import type { Job, Sample } from '../../api/schemas'
import { Button } from '../../components/Button'
import { ErrorNote } from '../../components/ErrorNote'
import { LiveDot } from '../../components/LiveDot'
import { Section } from '../../components/Section'
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

  return (
    <Section
      index="01"
      title="Teach"
      hint="Show the task once. SAM 3.1 follows each object through the clip and Muse Spark reads the same video."
    >
      <VideoStage
        src={sample.videoUrl}
        learn={learn}
        time={time}
        onTime={handleTime}
        seekTo={seekTo}
      />

      {learn && <Timeline learn={learn} time={time} onSeek={seek} />}

      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <Button variant="primary" icon={<Eye size={18} />} disabled={busy} onClick={onLearn}>
            {learn ? 'Watch again' : 'Learn from this video'}
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
          <dl className="grid grid-cols-3 gap-x-6 border-t border-line pt-4">
            <Fact label="Objects" value={String(new Set(learn.rests.map((r) => r.object)).size)} />
            <Fact label="Moves seen" value={String(learn.moves.length)} />
            <Fact label="Read by" value={learn.source === 'geometry' ? 'Motion' : 'Muse Spark'} />
          </dl>
        )}
      </div>
    </Section>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className="mt-1 font-mono text-sm text-ink">{value}</dd>
    </div>
  )
}
