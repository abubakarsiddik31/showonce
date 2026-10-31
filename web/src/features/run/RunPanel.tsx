import { CheckCircle, DiceFive, Play, XCircle } from '@phosphor-icons/react'
import { useRef, useState } from 'react'

import type { Job } from '../../api/schemas'
import { Button } from '../../components/Button'
import { ErrorNote } from '../../components/ErrorNote'
import { LiveDot } from '../../components/LiveDot'
import { Section } from '../../components/Section'
import { Skeleton } from '../../components/Skeleton'
import { cn, formatTime } from '../../lib/format'
import type { EditableStep } from '../workbench'

interface Props {
  steps: EditableStep[]
  canRun: boolean
  seed: number
  oracle: boolean
  job: Job | undefined
  starting: boolean
  startError: string | null
  onSeed: (seed: number) => void
  onOracle: (value: boolean) => void
  onRun: () => void
}

export function RunPanel(props: Props) {
  const { steps, canRun, seed, oracle, job, starting, startError, onSeed, onOracle, onRun } = props
  const video = useRef<HTMLVideoElement>(null)
  const [time, setTime] = useState(0)
  const run = job?.run ?? null
  const busy = starting || job?.status === 'queued' || job?.status === 'running'
  const verified = run?.checks.filter((c) => c.ok).length ?? 0

  return (
    <Section
      index="03"
      title="Do"
      hint="The arm works on a shuffled table. It finds each object with SAM, then checks the result."
    >
      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <label className="flex flex-col gap-1.5 text-xs text-ink-faint">
          Layout seed
          <span className="flex items-center gap-1.5">
            <input
              type="number"
              min={0}
              value={seed}
              onChange={(e) => onSeed(Math.max(0, Number(e.target.value) || 0))}
              className="h-9 w-20 rounded-lg border border-line bg-sunken px-2.5 font-mono text-sm text-ink hover:border-line-strong"
            />
            <Button
              variant="ghost"
              aria-label="Shuffle layout"
              className="w-9 px-0"
              icon={<DiceFive size={18} />}
              onClick={() => onSeed(Math.floor(Math.random() * 1000))}
            />
          </span>
        </label>
        <label className="flex h-9 cursor-pointer items-center gap-2 text-sm text-ink-dim">
          <input
            type="checkbox"
            checked={oracle}
            onChange={(e) => onOracle(e.target.checked)}
            className="size-4 accent-emerald-400"
          />
          Skip vision (true positions)
        </label>
        <Button
          variant="primary"
          className="ml-auto"
          icon={<Play size={18} weight="fill" />}
          disabled={!canRun || busy}
          onClick={onRun}
        >
          Run {steps.length > 0 ? `${steps.length} steps` : ''}
        </Button>
      </div>

      {(startError ?? job?.error) && <ErrorNote message={(startError ?? job?.error) as string} />}

      <div className="max-w-3xl overflow-hidden rounded-2xl border border-line bg-sunken">
        <div className="relative aspect-video">
          {run ? (
            <video
              ref={video}
              key={run.videoUrl}
              src={run.videoUrl}
              controls
              muted
              playsInline
              className="absolute inset-0 size-full object-contain"
              onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
            />
          ) : busy ? (
            <div className="absolute inset-0 flex flex-col justify-end gap-3 p-4">
              <Skeleton className="absolute inset-0 rounded-none" />
              <p
                className="relative flex items-center gap-2 text-sm text-ink-dim"
                aria-live="polite"
              >
                <LiveDot /> {job?.stage ?? 'Starting'}
              </p>
            </div>
          ) : (
            <div className="absolute inset-0 grid place-items-center text-sm text-ink-faint">
              The arm view appears here
            </div>
          )}
        </div>
      </div>

      {run && (
        <div className="flex flex-col gap-4">
          <p
            className={cn(
              'flex items-center gap-2 text-sm font-medium',
              run.success ? 'text-accent' : 'text-danger',
            )}
          >
            {run.success ? (
              <CheckCircle size={18} weight="fill" />
            ) : (
              <XCircle size={18} weight="fill" />
            )}
            {verified} of {run.checks.length} steps verified in the simulator
          </p>
          <ol className="flex flex-col divide-y divide-line border-y border-line">
            {run.checks.map((check, i) => {
              const end = run.stepTimesS[i] ?? Infinity
              const start = i === 0 ? 0 : (run.stepTimesS[i - 1] ?? 0)
              const state = time >= end ? 'done' : time >= start ? 'active' : 'waiting'
              return (
                <li key={`${i}-${check.step}`}>
                  <button
                    type="button"
                    onClick={() => {
                      if (video.current) video.current.currentTime = start
                    }}
                    className="flex w-full items-center gap-3 py-2.5 text-left transition-colors hover:bg-white/[0.03]"
                  >
                    <span className="w-4 text-center font-mono text-xs text-ink-faint">
                      {i + 1}
                    </span>
                    <span
                      className={cn(
                        'flex-1 text-sm transition-colors',
                        state === 'waiting' ? 'text-ink-faint' : 'text-ink',
                      )}
                    >
                      {check.step}
                    </span>
                    <span className="font-mono text-xs text-ink-faint">{check.detail}</span>
                    {state === 'done' ? (
                      check.ok ? (
                        <CheckCircle size={18} weight="fill" className="text-accent" />
                      ) : (
                        <XCircle size={18} weight="fill" className="text-danger" />
                      )
                    ) : (
                      <span className="font-mono text-xs text-ink-faint tabular-nums">
                        {state === 'active' ? formatTime(time) : ''}
                      </span>
                    )}
                  </button>
                </li>
              )
            })}
          </ol>
          {Object.keys(run.perceptionErrorMm).length > 0 && (
            <p className="font-mono text-xs text-ink-faint">
              SAM position error{' '}
              {(
                Object.values(run.perceptionErrorMm).reduce((a, b) => a + b, 0) /
                Object.values(run.perceptionErrorMm).length
              ).toFixed(1)}{' '}
              mm average
            </p>
          )}
        </div>
      )}
    </Section>
  )
}
