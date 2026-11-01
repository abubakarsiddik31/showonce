import { useQueryClient } from '@tanstack/react-query'
import { MotionConfig, motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'

import { ApiError } from '../../api/client'
import {
  useHealth,
  useJob,
  useSamples,
  useStartLearn,
  useStartRun,
  useStartUpload,
} from '../../api/hooks'
import type { Sample, Step } from '../../api/schemas'
import { ErrorNote } from '../../components/ErrorNote'
import { Skeleton } from '../../components/Skeleton'
import { studioHref } from '../../lib/route'
import { ChatPanel } from '../chat/ChatPanel'
import { useConversation } from '../chat/useConversation'
import { PlanEditor } from '../program/PlanEditor'
import { RobotStage } from '../run/RobotStage'
import { TeachPanel } from '../teach/TeachPanel'
import { TopBar } from '../TopBar'
import { UploadDialog, type UploadSpec } from '../UploadDialog'
import { initialState, isEdited, workbenchReducer } from '../workbench'
import { ClipMenu } from './ClipMenu'
import { Stepper, type Stage } from './Stepper'
import { TalkPanel } from './TalkPanel'

const message = (error: unknown): string | null =>
  error instanceof ApiError || error instanceof Error ? error.message : null

interface Props {
  /** The clip named in the URL, if any. */
  clip: string | null
  /** Open the upload dialog straight away. */
  upload: boolean
  go: (href: string) => void
}

/** The workspace: show a clip, talk it through, then watch the robot do it. */
export function Studio({ clip, upload, go }: Props) {
  const queryClient = useQueryClient()
  const health = useHealth()
  const samples = useSamples()
  const [state, dispatch] = useReducer(workbenchReducer, initialState)
  const [custom, setCustom] = useState<Sample | null>(null)
  const [uploadOpen, setUploadOpen] = useState(upload)
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
  const picked = custom ?? list?.find((s) => s.id === clip) ?? list?.[0] ?? null
  // A clip you upload has no object list until the robot has looked at the table.
  const sample =
    picked && custom && learn
      ? { ...picked, objects: learn.objectNames, containers: learn.containerNames }
      : picked

  const revise = useCallback((steps: Step[]) => dispatch({ type: 'revise', steps }), [])
  const plan = useMemo(() => state.steps.map(({ id: _id, ...rest }) => rest), [state.steps])
  const conversation = useConversation(learn?.sampleId ?? null, plan, revise)
  const { start: startConversation, reset: resetConversation } = conversation

  // Load the learned steps into the editor once per finished learn job, and let the robot speak.
  const loaded = useRef<string | null>(null)
  useEffect(() => {
    if (learn && learnJobId && loaded.current !== learnJobId) {
      loaded.current = learnJobId
      dispatch({ type: 'learned', steps: learn.steps })
      startConversation(learn.understanding)
    }
  }, [learn, learnJobId, startConversation])

  const clearTask = useCallback(() => {
    setLearnJobId(null)
    setRunJobId(null)
    setProgress(null)
    loaded.current = null
    dispatch({ type: 'reset' })
    resetConversation()
  }, [resetConversation])

  const select = (id: string) => {
    if (id === clip) {
      setCustom(null)
      clearTask()
    } else go(studioHref({ clip: id }))
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
      title: spec.file.name.replace(/\.[^.]+$/, ''),
      group: 'Your clips',
      videoUrl: URL.createObjectURL(spec.file),
      objects: [],
      containers: [],
      durationS: 0,
    })
    sendUpload(spec)
  }

  const learnNow = () => {
    if (!sample) return
    clearTask()
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
  const reading =
    learning || learnJob.data?.status === 'queued' || learnJob.data?.status === 'running'
  const learnStartError = message(startLearn.error ?? startUpload.error)
  const ran = Boolean(runJob.data?.run)

  const stages: Stage[] = [
    { label: 'Show it', state: learn ? 'done' : 'now' },
    { label: 'Talk it through', state: !learn ? 'todo' : conversation.confirmed ? 'done' : 'now' },
    { label: 'Watch it work', state: ran ? 'done' : conversation.confirmed ? 'now' : 'todo' },
  ]

  return (
    <MotionConfig reducedMotion="user">
      <div className="mx-auto flex min-h-[100dvh] max-w-[1680px] flex-col px-4 pb-16 sm:px-8">
        <TopBar
          onUpload={() => setUploadOpen(true)}
          health={health.data}
          healthError={health.isError}
          progress={<Stepper stages={stages} />}
          clips={
            list && (
              <ClipMenu
                samples={list}
                selected={custom ? null : picked}
                label={custom ? custom.title : (picked?.title ?? 'Pick a clip')}
                onSelect={select}
              />
            )
          }
        />

        {samples.isError && (
          <div className="pt-8">
            <ErrorNote message="Could not reach the ShowOnce API. Start it with `make backend`." />
          </div>
        )}

        {samples.isPending ? (
          <main className="grid flex-1 gap-6 py-6 lg:grid-cols-[5fr_7fr]">
            <Skeleton className="h-96 w-full rounded-3xl" />
            <Skeleton className="h-96 w-full rounded-3xl" />
          </main>
        ) : sample ? (
          <motion.main
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="grid flex-1 items-start gap-6 py-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]"
          >
            <div className="flex min-w-0 flex-col gap-6">
              <TeachPanel
                sample={sample}
                job={learnJob.data}
                starting={learning}
                startError={learnStartError}
                onLearn={learnNow}
              />
              <TalkPanel
                learn={learn}
                learning={reading}
                confirmed={conversation.confirmed}
                answer={state.answer}
                onAnswer={(id) => {
                  const option = learn?.questions[0]?.options.find((o) => o.id === id)
                  if (option) dispatch({ type: 'answer', optionId: id, steps: option.steps })
                }}
                stepCount={state.steps.length}
                chat={
                  <ChatPanel
                    messages={conversation.messages}
                    confirmed={conversation.confirmed}
                    thinking={conversation.thinking}
                    onSend={conversation.send}
                    onConfirm={conversation.confirm}
                    onNotQuite={conversation.notQuite}
                  />
                }
                plan={
                  <div className="flex flex-col gap-3 border-t border-line pt-5">
                    <h3 className="font-display text-lg font-semibold tracking-tight">
                      What I will do
                    </h3>
                    <PlanEditor
                      sample={sample}
                      steps={state.steps}
                      edited={edited}
                      progress={progress}
                      dispatch={dispatch}
                    />
                  </div>
                }
              />
            </div>
            <div className="min-w-0 lg:sticky lg:top-24">
              <RobotStage
                steps={state.steps}
                learned={Boolean(learn)}
                approved={conversation.confirmed}
                seed={state.seed}
                oracle={state.oracle}
                slip={state.slip}
                job={runJob.data}
                starting={startRun.isPending}
                startError={message(startRun.error)}
                progress={progress}
                onSeed={(seed) => dispatch({ type: 'seed', seed })}
                onOracle={(oracle) => dispatch({ type: 'oracle', oracle })}
                onSlip={(slip) => dispatch({ type: 'slip', slip })}
                onRun={runNow}
                onProgress={setProgress}
              />
            </div>
          </motion.main>
        ) : (
          !samples.isError && (
            <p className="py-16 text-sm text-ink-dim">
              No sample clips found. Add an mp4 and a scene json to{' '}
              <code className="font-mono">samples/</code> or use &ldquo;Your clip&rdquo;.
            </p>
          )
        )}

        <p className="mt-10 max-w-[70ch] text-xs leading-relaxed text-ink-faint">
          Everything here runs in a MuJoCo simulation, checked against simulator ground truth. Real
          phone footage and a real arm are not tested yet.
        </p>

        <UploadDialog
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onSubmit={submitUpload}
        />
      </div>
    </MotionConfig>
  )
}
