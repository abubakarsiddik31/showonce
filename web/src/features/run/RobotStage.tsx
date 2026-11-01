import {
  ArrowsClockwise,
  CheckCircle,
  DiceFive,
  Eye,
  Lock,
  Play,
  WarningOctagon,
  XCircle,
} from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'

import type { Fixes, Job } from '../../api/schemas'
import { Button } from '../../components/Button'
import { ErrorNote } from '../../components/ErrorNote'
import { LiveDot } from '../../components/LiveDot'
import { Skeleton } from '../../components/Skeleton'
import { cn, describeStep, howItWillDo, objectTone, plural } from '../../lib/format'
import type { EditableStep } from '../workbench'

interface Props {
  steps: EditableStep[]
  /** The demo has been watched. */
  learned: boolean
  /** The person has said the robot understood. Nothing moves before this. */
  approved: boolean
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
  /** Reports the step being played, for the plan to light up beside it. */
  progress: { done: number; active: number } | null
}

const SPEEDS = [1, 2, 4] as const

const WAITING = {
  demo: 'Waiting for a demo to watch.',
  approval: 'Waiting for you to say I understood.',
  ready: 'Ready. I will work on a table I have never seen.',
} as const

/**
 * The robot is the point of the app, so it gets the big stage: the cell at rest, then the arm at
 * work with a running caption of what it is doing and how, then what it got right.
 */
export function RobotStage(props: Props) {
  const { steps, learned, approved, seed, oracle, slip, job, starting, startError, progress } =
    props
  const { onSeed, onOracle, onSlip, onRun, onProgress } = props
  const video = useRef<HTMLVideoElement>(null)
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(2)
  const last = useRef<string>('')
  const run = job?.run ?? null
  const busy = starting || job?.status === 'queued' || job?.status === 'running'
  const verified = run?.checks.filter((c) => c.ok).length ?? 0
  const idleMessage = !learned ? WAITING.demo : approved ? WAITING.ready : WAITING.approval
  const active = run && progress ? steps[progress.active] : undefined

  useEffect(() => {
    if (!run) {
      last.current = ''
      onProgress(null)
    }
  }, [run, onProgress])

  // The arm works at real speed, which is slow to watch, so play it faster by default.
  useEffect(() => {
    if (video.current) video.current.playbackRate = speed
  }, [speed, run?.videoUrl])

  const follow = (time: number) => {
    if (!run) return
    const done = run.stepTimesS.filter((end) => time >= end).length
    const key = `${done}`
    if (key === last.current) return
    last.current = key
    onProgress({ done, active: Math.min(done, run.checks.length - 1) })
  }

  const state = busy
    ? { label: 'Working', dot: 'bg-accent' }
    : run
      ? {
          label: run.success ? 'Done' : 'Finished with misses',
          dot: run.success ? 'bg-ok' : 'bg-danger',
        }
      : { label: approved ? 'Ready' : 'Locked', dot: approved ? 'bg-ok' : 'bg-white/30' }

  return (
    <section aria-labelledby="stage-robot" className="flex min-w-0 flex-col gap-5">
      <div className="flex flex-col gap-4 rounded-3xl bg-viewport p-4 text-white sm:p-5">
        <header className="flex items-center justify-between gap-3">
          <div>
            <h2 id="stage-robot" className="font-display text-2xl font-semibold tracking-tight">
              The robot
            </h2>
            <p className="text-xs text-white/55">
              A simulated Franka arm on a table it has never seen
            </p>
          </div>
          <span className="flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 font-mono text-[11px]">
            <span className={cn('size-1.5 rounded-full', state.dot)} aria-hidden />
            {state.label}
          </span>
        </header>

        <div className="viewport !rounded-2xl ring-1 ring-white/10">
          <div className="relative aspect-video">
            {run ? (
              <video
                ref={video}
                key={run.videoUrl}
                src={run.videoUrl}
                controls
                autoPlay
                muted
                playsInline
                className="absolute inset-0 z-[2] size-full object-contain"
                onLoadedMetadata={(e) => {
                  e.currentTarget.playbackRate = speed
                }}
                onTimeUpdate={(e) => follow(e.currentTarget.currentTime)}
                onSeeked={(e) => follow(e.currentTarget.currentTime)}
              />
            ) : (
              <>
                <img
                  src="/robot-cell.jpg"
                  alt="The robot arm at rest beside a table"
                  className={cn(
                    'absolute inset-0 size-full object-cover transition-opacity duration-500',
                    busy ? 'opacity-40' : 'opacity-80',
                  )}
                />
                {busy && <Skeleton className="absolute inset-0 rounded-none opacity-20" />}
                <div className="absolute inset-x-0 bottom-0 z-[2] flex items-center gap-2.5 bg-gradient-to-t from-black/80 to-transparent px-5 pt-12 pb-4 text-sm text-white/90">
                  {busy ? (
                    <>
                      <LiveDot /> <span aria-live="polite">{job?.stage ?? 'Starting'}</span>
                    </>
                  ) : (
                    <>
                      {!approved && <Lock size={16} aria-hidden />}
                      <span>{idleMessage}</span>
                    </>
                  )}
                </div>
              </>
            )}
            {run && active && (
              <div className="pointer-events-none absolute inset-x-0 top-0 z-[3] flex items-start gap-3 bg-gradient-to-b from-black/75 to-transparent px-5 pt-4 pb-10">
                <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-md bg-accent font-mono text-xs font-semibold text-ink">
                  {(progress?.active ?? 0) + 1}
                </span>
                <p className="text-sm leading-snug text-white">
                  <span className="font-medium">{describeStep(active)}</span>
                  <span className="block text-white/70">{howItWillDo(active)}</span>
                </p>
              </div>
            )}
          </div>
        </div>

        {approved && steps.length > 0 && (
          <ol className="flex flex-wrap gap-2" aria-label="The robot's steps">
            {steps.map((step, i) => {
              const now = run && progress ? i === progress.active : false
              const done = run && progress ? i < progress.done : false
              return (
                <li
                  key={step.id}
                  className={cn(
                    'flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition-colors',
                    now
                      ? 'border-accent bg-accent/20 text-white'
                      : done
                        ? 'border-white/15 text-white/45'
                        : 'border-white/15 text-white/70',
                  )}
                >
                  <span
                    className="size-1.5 shrink-0 rounded-full"
                    style={{ background: objectTone(step.object) }}
                    aria-hidden
                  />
                  <span className="font-mono text-white/50">{i + 1}</span>
                  {describeStep(step)}
                  {done && <CheckCircle size={14} weight="fill" className="text-ok" aria-hidden />}
                </li>
              )
            })}
          </ol>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <Button
            variant="primary"
            size="lg"
            icon={run ? <ArrowsClockwise size={20} /> : <Play size={20} weight="fill" />}
            disabled={!approved || steps.length === 0 || busy}
            onClick={() => {
              if (run) onSeed(Math.floor(Math.random() * 1000))
              onRun()
            }}
          >
            {run ? 'Shuffle and run again' : 'Start the robot'}
          </Button>
          <p className="flex items-center gap-1.5 text-xs text-white/55">
            <DiceFive size={16} aria-hidden /> Table <span className="font-mono">{seed}</span>
            {approved && steps.length > 0 && <span>· {plural(steps.length, 'step')}</span>}
          </p>
          {run && (
            <button
              type="button"
              onClick={() => setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length] ?? 1)}
              aria-label={`Playback speed ${speed} times. Press to change.`}
              className="rounded-full border border-white/20 px-3 py-1.5 font-mono text-xs text-white/80 transition-colors hover:bg-white/10"
            >
              {speed}×
            </button>
          )}
          {!approved && learned && (
            <p className="text-xs text-white/55">Say it is right first, then I will move.</p>
          )}
        </div>

        <details className="group text-sm text-white/70">
          <summary className="w-fit cursor-pointer rounded-md py-1 text-xs text-white/50 select-none hover:text-white">
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
                <span className="block text-xs text-white/50">
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
                <span className="block text-xs text-white/50">
                  Use true positions from the simulator instead of SAM.
                </span>
              </span>
            </label>
          </div>
        </details>

        {(startError ?? job?.error) && <ErrorNote message={(startError ?? job?.error) as string} />}
      </div>

      {run && (
        <div className="flex flex-col gap-5 rounded-3xl border border-line bg-raised p-5 sm:p-6">
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
    </section>
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
