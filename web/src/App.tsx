import { useQueryClient } from '@tanstack/react-query'
import { MotionConfig, motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'

import { ApiError } from './api/client'
import {
  useHealth,
  useJob,
  useSamples,
  useStartLearn,
  useStartRun,
  useStartUpload,
} from './api/hooks'
import type { Sample, Step } from './api/schemas'
import { ErrorNote } from './components/ErrorNote'
import { Skeleton } from './components/Skeleton'
import { ChatPanel } from './features/chat/ChatPanel'
import { useConversation } from './features/chat/useConversation'
import { ProgramPanel } from './features/program/ProgramPanel'
import { RunPanel } from './features/run/RunPanel'
import { TeachPanel } from './features/teach/TeachPanel'
import { TaskPicker } from './features/TaskPicker'
import { TopBar } from './features/TopBar'
import { UploadDialog, type UploadSpec } from './features/UploadDialog'
import { initialState, isEdited, workbenchReducer } from './features/workbench'

const message = (error: unknown): string | null =>
  error instanceof ApiError || error instanceof Error ? error.message : null

export default function App() {
  const queryClient = useQueryClient()
  const health = useHealth()
  const samples = useSamples()
  const [state, dispatch] = useReducer(workbenchReducer, initialState)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [custom, setCustom] = useState<Sample | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [learnJobId, setLearnJobId] = useState<string | null>(null)
  const [runJobId, setRunJobId] = useState<string | null>(null)
  const [progress, setProgress] = useState<{ done: number; active: number } | null>(null)
  const lastUpload = useRef<UploadSpec | null>(null)

  const startLearn = useStartLearn()
  const startUpload = useStartUpload()
  const startRun = useStartRun()
  const learnJob = useJob(learnJobId)
  const runJob = useJob(runJobId)

  const list = samples.data
  const learn = learnJob.data?.learn ?? null
  const picked = custom ?? list?.find((s) => s.id === selectedId) ?? list?.[0] ?? null
  // A clip you upload has no object list until the robot has looked at the table.
  const sample =
    picked && custom && learn
      ? { ...picked, objects: learn.objectNames, containers: learn.containerNames }
      : picked

  const revise = useCallback((steps: Step[]) => dispatch({ type: 'revise', steps }), [])
  const plan = useMemo(() => state.steps.map(({ id: _id, ...rest }) => rest), [state.steps])
  const conversation = useConversation(learn?.sampleId ?? null, plan, revise)
  const { start: startConversation, reset: resetConversation } = conversation

  // Load the learned steps into the editor once per finished learn job.
  const loaded = useRef<string | null>(null)
  useEffect(() => {
    if (learn && learnJobId && loaded.current !== learnJobId) {
      loaded.current = learnJobId
      dispatch({ type: 'learned', steps: learn.steps })
      startConversation(learn.steps)
    }
  }, [learn, learnJobId, startConversation])

  const clearTask = useCallback(() => {
    setLearnJobId(null)
    setRunJobId(null)
    loaded.current = null
    dispatch({ type: 'reset' })
    resetConversation()
  }, [resetConversation])

  const select = (id: string) => {
    setCustom(null)
    setSelectedId(id)
    clearTask()
  }

  const sendUpload = (spec: UploadSpec) => {
    const form = new FormData()
    form.set('video', spec.file)
    startUpload.mutate(form, { onSuccess: setLearnJobId })
  }

  const submitUpload = (spec: UploadSpec) => {
    lastUpload.current = spec
    setUploadOpen(false)
    clearTask()
    setCustom({
      id: 'upload',
      name: spec.file.name.replace(/\.[^.]+$/, ''),
      videoUrl: URL.createObjectURL(spec.file),
      objects: [],
      containers: [],
      durationS: 0,
    })
    sendUpload(spec)
  }

  const learnNow = () => {
    if (!sample) return
    setRunJobId(null)
    loaded.current = null
    if (custom && lastUpload.current) sendUpload(lastUpload.current)
    else startLearn.mutate(sample.id, { onSuccess: setLearnJobId })
  }

  const runNow = () => {
    if (!learn) return
    startRun.mutate(
      {
        sampleId: learn.sampleId,
        steps: plan,
        seed: state.seed,
        oracle: state.oracle,
        slip: state.slip && !state.oracle,
      },
      {
        onSuccess: (id) => {
          setRunJobId(id)
          void queryClient.invalidateQueries({ queryKey: ['job', id] })
        },
      },
    )
  }

  const edited = useMemo(() => isEdited(state), [state])
  const learning = startLearn.isPending || startUpload.isPending
  const learnStartError = message(startLearn.error ?? startUpload.error)

  const reveal = (i: number) => ({
    initial: { opacity: 0, y: 14 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.6, delay: 0.08 * i, ease: [0.16, 1, 0.3, 1] as const },
  })

  return (
    <MotionConfig reducedMotion="user">
      <div className="mx-auto flex min-h-[100dvh] max-w-[1680px] flex-col px-4 pb-16 sm:px-8">
        <TopBar
          onUpload={() => setUploadOpen(true)}
          health={health.data}
          healthError={health.isError}
        />

        <motion.div {...reveal(0)} className="grid gap-6 pt-6 pb-10 lg:grid-cols-[1.9fr_1fr]">
          <h1 className="font-display text-[clamp(2.5rem,5.8vw,5.25rem)] leading-[0.92] font-semibold tracking-[-0.03em] text-balance">
            Show it once.
            <br />
            <span className="text-ink-faint lg:whitespace-nowrap">The robot does the rest.</span>
          </h1>
          <p className="max-w-[46ch] self-end text-lg leading-relaxed text-ink-dim">
            Film a tabletop task a single time. The arm turns it into plain steps, does them on a
            table it has never seen, then looks at the result and fixes its own mistakes.
          </p>
        </motion.div>

        {samples.isError && (
          <div className="pb-8">
            <ErrorNote message="Could not reach the ShowOnce API. Start it with `make backend`." />
          </div>
        )}

        {samples.isPending ? (
          <main className="grid flex-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
            <Skeleton className="h-96 w-full rounded-3xl" />
            <Skeleton className="h-96 w-full rounded-3xl" />
            <Skeleton className="h-96 w-full rounded-3xl" />
          </main>
        ) : sample ? (
          <>
            <motion.div {...reveal(1)} className="pb-5">
              <TaskPicker
                samples={list ?? []}
                selectedId={custom ? null : (sample?.id ?? null)}
                onSelect={select}
              />
            </motion.div>
            <main className="grid flex-1 items-start gap-6 lg:grid-cols-2 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)_minmax(0,1.1fr)]">
              <motion.div {...reveal(2)} className="min-w-0">
                <TeachPanel
                  sample={sample}
                  job={learnJob.data}
                  starting={learning}
                  startError={learnStartError}
                  onLearn={learnNow}
                />
              </motion.div>
              <motion.div {...reveal(3)} className="min-w-0">
                <ProgramPanel
                  sample={sample}
                  learn={learn}
                  learning={learning || learnJob.data?.status === 'running'}
                  steps={state.steps}
                  answer={state.answer}
                  edited={edited}
                  progress={progress}
                  dispatch={dispatch}
                  conversation={
                    <ChatPanel
                      messages={conversation.messages}
                      confirmed={conversation.confirmed}
                      thinking={conversation.thinking}
                      onSend={conversation.send}
                      onConfirm={conversation.confirm}
                      onNotQuite={conversation.notQuite}
                    />
                  }
                />
              </motion.div>
              <motion.div {...reveal(4)} className="min-w-0 lg:col-span-2 xl:col-span-1">
                <RunPanel
                  steps={state.steps}
                  canRun={Boolean(learn) && state.steps.length > 0}
                  seed={state.seed}
                  oracle={state.oracle}
                  slip={state.slip}
                  job={runJob.data}
                  starting={startRun.isPending}
                  startError={message(startRun.error)}
                  onSeed={(seed) => dispatch({ type: 'seed', seed })}
                  onOracle={(oracle) => dispatch({ type: 'oracle', oracle })}
                  onSlip={(slip) => dispatch({ type: 'slip', slip })}
                  onRun={runNow}
                  onProgress={setProgress}
                />
              </motion.div>
            </main>
            <ProofStrip />
          </>
        ) : (
          !samples.isError && (
            <p className="py-16 text-sm text-ink-dim">
              No sample clips found. Add an mp4 and a scene json to{' '}
              <code className="font-mono">samples/</code> or use &ldquo;Your clip&rdquo;.
            </p>
          )
        )}

        <UploadDialog
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onSubmit={submitUpload}
        />
      </div>
    </MotionConfig>
  )
}

/** What has been measured so far, and what it was measured on. */
function ProofStrip() {
  const facts = [
    ['8 of 8', 'clips read into the right plan'],
    ['24 of 24', 'replays succeeded on shuffled tables'],
    ['about 1 mm', 'SAM position error in the simulator'],
    ['10', 'actions, from put-in to pour, stir and cut'],
  ]
  return (
    <motion.section
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true }}
      aria-label="What has been measured"
      className="mt-14 border-t border-line-strong pt-8"
    >
      <dl className="grid grid-cols-2 gap-x-6 gap-y-8 lg:grid-cols-4">
        {facts.map(([value, label]) => (
          <div key={label}>
            <dd className="font-display text-4xl leading-none font-semibold tracking-tight">
              {value}
            </dd>
            <dt className="mt-2 max-w-[24ch] text-sm text-ink-dim">{label}</dt>
          </div>
        ))}
      </dl>
      <p className="mt-6 max-w-[70ch] text-xs leading-relaxed text-ink-faint">
        Measured on synthetic and AI-generated clips in a MuJoCo simulator, checked against
        simulator ground truth. Real phone footage and a real arm are not tested yet.
      </p>
    </motion.section>
  )
}
