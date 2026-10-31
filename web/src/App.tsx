import { useQueryClient } from '@tanstack/react-query'
import { MotionConfig } from 'motion/react'
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
import type { Sample } from './api/schemas'
import { ErrorNote } from './components/ErrorNote'
import { Skeleton } from './components/Skeleton'
import { ProgramPanel } from './features/program/ProgramPanel'
import { RunPanel } from './features/run/RunPanel'
import { TeachPanel } from './features/teach/TeachPanel'
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
  const lastUpload = useRef<UploadSpec | null>(null)

  const startLearn = useStartLearn()
  const startUpload = useStartUpload()
  const startRun = useStartRun()
  const learnJob = useJob(learnJobId)
  const runJob = useJob(runJobId)

  const list = samples.data
  const sample = custom ?? list?.find((s) => s.id === selectedId) ?? list?.[0] ?? null
  const learn = learnJob.data?.learn ?? null

  // Load the learned steps into the editor once per finished learn job.
  const loaded = useRef<string | null>(null)
  useEffect(() => {
    if (learn && learnJobId && loaded.current !== learnJobId) {
      loaded.current = learnJobId
      dispatch({ type: 'learned', steps: learn.steps })
    }
  }, [learn, learnJobId])

  const clearTask = useCallback(() => {
    setLearnJobId(null)
    setRunJobId(null)
    loaded.current = null
    dispatch({ type: 'reset' })
  }, [])

  const select = (id: string) => {
    setCustom(null)
    setSelectedId(id)
    clearTask()
  }

  const sendUpload = (spec: UploadSpec) => {
    const form = new FormData()
    form.set('video', spec.file)
    form.set('objects', JSON.stringify(spec.objects))
    form.set('containers', JSON.stringify(spec.containers))
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
      objects: Object.keys(spec.objects),
      containers: Object.keys(spec.containers),
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
    const steps = state.steps.map(({ id: _id, ...rest }) => rest)
    startRun.mutate(
      { sampleId: learn.sampleId, steps, seed: state.seed, oracle: state.oracle },
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

  return (
    <MotionConfig reducedMotion="user">
      <div className="mx-auto flex min-h-[100dvh] max-w-[1600px] flex-col px-4 sm:px-8">
        <TopBar
          samples={list ?? []}
          selectedId={custom ? null : (sample?.id ?? null)}
          onSelect={select}
          onUpload={() => setUploadOpen(true)}
          health={health.data}
          healthError={health.isError}
        />

        {samples.isError && (
          <div className="pt-8">
            <ErrorNote message="Could not reach the ShowOnce API. Start it with `uv run showonce ui`." />
          </div>
        )}

        {samples.isPending ? (
          <main className="grid flex-1 gap-10 py-10 md:grid-cols-2 xl:grid-cols-[9fr_7fr_8fr]">
            <Skeleton className="aspect-video w-full rounded-2xl" />
            <Skeleton className="h-64 w-full rounded-2xl" />
            <Skeleton className="aspect-video w-full rounded-2xl" />
          </main>
        ) : sample ? (
          <main className="grid flex-1 gap-x-10 gap-y-14 py-10 md:grid-cols-2 xl:grid-cols-[9fr_7fr_8fr]">
            <TeachPanel
              sample={sample}
              job={learnJob.data}
              starting={learning}
              startError={learnStartError}
              onLearn={learnNow}
            />
            <div className="md:border-l md:border-line md:pl-10">
              <ProgramPanel
                sample={sample}
                learn={learn}
                steps={state.steps}
                answer={state.answer}
                edited={edited}
                dispatch={dispatch}
              />
            </div>
            <div className="md:col-span-2 md:border-t md:border-line md:pt-10 xl:col-span-1 xl:border-t-0 xl:border-l xl:pt-0 xl:pl-10">
              <RunPanel
                steps={state.steps}
                canRun={Boolean(learn) && state.steps.length > 0}
                seed={state.seed}
                oracle={state.oracle}
                job={runJob.data}
                starting={startRun.isPending}
                startError={message(startRun.error)}
                onSeed={(seed) => dispatch({ type: 'seed', seed })}
                onOracle={(oracle) => dispatch({ type: 'oracle', oracle })}
                onRun={runNow}
              />
            </div>
          </main>
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
