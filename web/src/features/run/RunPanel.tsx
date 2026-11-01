import {
  ArrowsClockwise,
  CheckCircle,
  DiceFive,
  Eye,
  Play,
  WarningOctagon,
  XCircle,
} from '@phosphor-icons/react'
import { useEffect, useRef } from 'react'

import type { Fixes, Job } from '../../api/schemas'
import { Button } from '../../components/Button'
import { ErrorNote } from '../../components/ErrorNote'
import { LiveDot } from '../../components/LiveDot'
import { Panel, StatusPill } from '../../components/Panel'
import { Skeleton } from '../../components/Skeleton'
import { cn, plural } from '../../lib/format'
import type { EditableStep } from '../workbench'

interface Props {
  steps: EditableStep[]
  canRun: boolean
  seed: number
  oracle: boolean
  slip: boolean
  job: Job | undefined
  starting: boolean
  startError: string | null
  onSeed: (seed: number) => void
  onOracle: (value: boolean) => void
  onSlip: (value: boolean) => void
  onRun: () => void
  /** Reports how far the arm's video has got, or null when there is no run to follow. */
  onProgress: (progress: { done: number; active: number } | null) => void
}

export function RunPanel(props: Props) {
  const { steps, canRun, seed, oracle, slip, job, starting, startError } = props
  const { onSeed, onOracle, onSlip, onRun, onProgress } = props
  const video = useRef<HTMLVideoElement>(null)
  const last = useRef<string>('')
  const run = job?.run ?? null
  const busy = starting || job?.status === 'queued' || job?.status === 'running'
  const verified = run?.checks.filter((c) => c.ok).length ?? 0

  useEffect(() => {
    if (!run) {
      last.current = ''
      onProgress(null)
    }
  }, [run, onProgress])

  const follow = (time: number) => {
    if (!run) return
    const done = run.stepTimesS.filter((end) => time >= end).length
    const key = `${done}`
    if (key === last.current) return
    last.current = key
    onProgress({ done, active: Math.min(done, run.checks.length - 1) })
  }

  const status = busy ? (
    <StatusPill tone="live">Running</StatusPill>
  ) : run ? (
    <StatusPill tone={run.success ? 'done' : 'bad'}>
      {verified}/{run.checks.length} verified
    </StatusPill>
  ) : (
    <StatusPill tone="idle">{canRun ? 'Ready' : 'Locked'}</StatusPill>
  )

  return (
    <Panel
      id="panel-run"
      title="On a new table"
      hint="The objects are shuffled. The arm finds each one with SAM, does the task, then looks at the result."
      status={status}
      waiting={!canRun && !run}
    >
      <div className="viewport">
        <div className="relative aspect-video">
          {run ? (
            <video
              ref={video}
              key={run.videoUrl}
              src={run.videoUrl}
              controls
              muted
              playsInline
              className="absolute inset-0 z-[2] size-full object-contain"
              onTimeUpdate={(e) => follow(e.currentTarget.currentTime)}
              onSeeked={(e) => follow(e.currentTarget.currentTime)}
            />
          ) : busy ? (
            <div className="absolute inset-0 flex flex-col justify-end gap-3 p-4">
              <Skeleton className="absolute inset-0 rounded-none opacity-20" />
              <p
                className="relative flex items-center gap-2 text-sm text-white/80"
                aria-live="polite"
              >
                <LiveDot /> {job?.stage ?? 'Starting'}
              </p>
            </div>
          ) : (
            <div className="absolute inset-0 grid place-items-center">
              <svg
                aria-hidden
                className="absolute inset-0 size-full opacity-25"
                preserveAspectRatio="none"
              >
                <defs>
                  <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">
                    <circle cx="1" cy="1" r="1" fill="#fff" />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" />
              </svg>
              <p className="relative text-sm text-white/60">The arm&rsquo;s view appears here</p>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-3">
        <Button
          variant="primary"
          size="lg"
          icon={run ? <ArrowsClockwise size={20} /> : <Play size={20} weight="fill" />}
          disabled={!canRun || busy}
          onClick={() => {
            if (run) onSeed(Math.floor(Math.random() * 1000))
            onRun()
          }}
        >
          {run
            ? 'Shuffle and run again'
            : `Run${steps.length > 0 ? ` ${plural(steps.length, 'step')}` : ''}`}
        </Button>
        <p className="flex items-center gap-1.5 text-xs text-ink-faint">
          <DiceFive size={16} aria-hidden /> Table <span className="font-mono">{seed}</span>
        </p>
      </div>

      <details className="group text-sm text-ink-dim">
        <summary className="w-fit cursor-pointer rounded-md py-1 text-xs text-ink-faint select-none hover:text-ink">
          Options
        </summary>
        <div className="mt-2 flex flex-col gap-2.5">
          <label className="flex cursor-pointer items-start gap-2.5">
            <input
              type="checkbox"
              checked={slip}
              disabled={oracle}
              onChange={(e) => onSlip(e.target.checked)}
              className="mt-0.5 size-4 accent-[#ff5a1f]"
            />
            <span>
              Make it slip
              <span className="block text-xs text-ink-faint">
                Drops one object after the run, so you can watch SAM catch it and fix it.
              </span>
            </span>
          </label>
          <label className="flex cursor-pointer items-start gap-2.5">
            <input
              type="checkbox"
              checked={oracle}
              onChange={(e) => onOracle(e.target.checked)}
              className="mt-0.5 size-4 accent-[#ff5a1f]"
            />
            <span>
              Skip vision
              <span className="block text-xs text-ink-faint">
                Use true positions from the simulator instead of SAM.
              </span>
            </span>
          </label>
        </div>
      </details>

      {(startError ?? job?.error) && <ErrorNote message={(startError ?? job?.error) as string} />}

      {run && (
        <div className="flex flex-col gap-5">
          <Verdict success={run.success} verified={verified} total={run.checks.length} />
          {run.fixes && <SelfCheck fixes={run.fixes} />}
          <ol className="flex flex-col divide-y divide-line border-y border-line">
            {run.checks.map((check, i) => (
              <li key={`${i}-${check.step}`}>
                <button
                  type="button"
                  onClick={() => {
                    const start = i === 0 ? 0 : (run.stepTimesS[i - 1] ?? 0)
                    if (video.current) video.current.currentTime = start
                  }}
                  className="flex w-full items-center gap-3 py-2.5 text-left transition-colors hover:bg-ink/[0.04]"
                >
                  <span className="w-4 text-center font-mono text-xs text-ink-faint">{i + 1}</span>
                  <span className="flex-1 text-sm">{check.step}</span>
                  <span className="font-mono text-xs text-ink-faint">{check.detail}</span>
                  {check.ok ? (
                    <CheckCircle size={18} weight="fill" className="text-ok" />
                  ) : (
                    <XCircle size={18} weight="fill" className="text-danger" />
                  )}
                </button>
              </li>
            ))}
          </ol>
          {Object.keys(run.perceptionErrorMm).length > 0 && (
            <p className="font-mono text-xs text-ink-faint">
              SAM found the objects to{' '}
              {(
                Object.values(run.perceptionErrorMm).reduce((a, b) => a + b, 0) /
                Object.values(run.perceptionErrorMm).length
              ).toFixed(1)}{' '}
              mm on average
            </p>
          )}
        </div>
      )}
    </Panel>
  )
}

function Verdict({
  success,
  verified,
  total,
}: {
  success: boolean
  verified: number
  total: number
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-3 rounded-2xl px-4 py-3',
        success ? 'bg-ok/12 text-ok' : 'bg-danger/10 text-danger',
      )}
    >
      {success ? (
        <CheckCircle size={28} weight="fill" aria-hidden />
      ) : (
        <XCircle size={28} weight="fill" aria-hidden />
      )}
      <p>
        <span className="font-display text-2xl leading-none font-semibold">
          {verified} of {total}
        </span>
        <span className="ml-2 text-sm font-medium">
          {success ? 'steps done on a table it never saw' : 'steps verified. The rest failed.'}
        </span>
      </p>
    </div>
  )
}

/** SAM's look at the finished table: what it saw, and whether the arm had to try again. */
function SelfCheck({ fixes }: { fixes: Fixes }) {
  const missed = fixes.before.filter((c) => !c.ok)
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-canvas/60 p-4">
      <p className="flex items-center gap-2 text-sm font-medium">
        <Eye size={18} aria-hidden /> SAM checked the finished table
      </p>
      {fixes.missed ? (
        <div
          className={cn(
            'flex items-start gap-3 rounded-xl p-3 text-sm',
            fixes.fixed ? 'bg-accent/15' : 'bg-danger/10',
          )}
        >
          <WarningOctagon
            size={20}
            weight="fill"
            className={fixes.fixed ? 'text-accent' : 'text-danger'}
            aria-hidden
          />
          <p>
            <span className="font-medium">
              It saw {plural(missed.length, 'miss')}: {missed.map((c) => c.step).join('; ')}.
            </span>{' '}
            {fixes.fixed
              ? 'The arm tried once more and now it checks out.'
              : 'The arm tried once more and it still does not check out.'}
          </p>
        </div>
      ) : (
        <p className="text-sm text-ink-dim">Everything it could see is where the plan said.</p>
      )}
      <ul className="flex flex-wrap gap-1.5">
        {fixes.after.map((c, i) => (
          <li
            key={`${i}-${c.step}`}
            className="flex items-center gap-1.5 rounded-full border border-line bg-raised px-2.5 py-1 font-mono text-[11px] text-ink-dim"
          >
            <span
              className={cn('size-1.5 rounded-full', c.ok ? 'bg-ok' : 'bg-danger')}
              aria-hidden
            />
            {c.detail.startsWith('SAM') ? 'seen by SAM' : 'from the simulator'}
          </li>
        ))}
      </ul>
    </div>
  )
}
