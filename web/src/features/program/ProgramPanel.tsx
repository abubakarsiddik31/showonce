import { ArrowCounterClockwise, Plus } from '@phosphor-icons/react'
import { AnimatePresence, Reorder } from 'motion/react'
import type { ReactNode } from 'react'

import type { LearnResult, Sample } from '../../api/schemas'
import { Button } from '../../components/Button'
import { Panel, StatusPill } from '../../components/Panel'
import { plural } from '../../lib/format'
import { defaultStep, type EditableStep, type WorkbenchAction } from '../workbench'
import { AskCard } from './AskCard'
import { StepRow, type StepState } from './StepRow'

interface Props {
  sample: Sample
  learn: LearnResult | null
  learning: boolean
  steps: EditableStep[]
  answer: string | null
  edited: boolean
  /** How far the robot's video has got, so the plan lights up in step with it. */
  progress: { done: number; active: number } | null
  dispatch: (action: WorkbenchAction) => void
  /** The talk-it-through panel, shown once there is something to talk about. */
  conversation?: ReactNode
}

const GHOST_STEPS = ['put the first thing away', 'then the next', 'and the last one']

export function ProgramPanel({
  sample,
  learn,
  learning,
  steps,
  answer,
  edited,
  progress,
  dispatch,
  conversation,
}: Props) {
  const question = learn?.questions[0]
  const status = learning ? (
    <StatusPill tone="live">Reading</StatusPill>
  ) : steps.length > 0 ? (
    <StatusPill tone="done">{edited ? 'Edited' : plural(steps.length, 'step')}</StatusPill>
  ) : (
    <StatusPill tone="idle">Waiting</StatusPill>
  )

  const stateOf = (i: number): StepState =>
    !progress ? 'idle' : i < progress.done ? 'done' : i === progress.active ? 'active' : 'waiting'

  return (
    <Panel
      id="panel-program"
      title="What it understood"
      hint="Plain steps that name objects, never positions, so they hold on any table. Correct them in words, or edit them directly."
      status={status}
      waiting={steps.length === 0 && !learning}
      aside={
        edited ? (
          <Button
            variant="quiet"
            icon={<ArrowCounterClockwise size={16} />}
            onClick={() => dispatch({ type: 'restore' })}
          >
            Reset
          </Button>
        ) : undefined
      }
    >
      {steps.length === 0 ? (
        <ol className="flex flex-col gap-2" aria-label="Steps appear here once it has watched">
          {GHOST_STEPS.map((text, i) => (
            <li
              key={text}
              className="flex items-center gap-3 rounded-xl border border-dashed border-line-strong px-3 py-3 text-sm text-ink-faint"
            >
              <span className="grid size-6 place-items-center rounded-md border border-line-strong font-mono text-xs">
                {i + 1}
              </span>
              {text}
            </li>
          ))}
        </ol>
      ) : (
        <div className="flex flex-col gap-4">
          {question && (
            <AskCard
              question={question}
              chosen={answer}
              onChoose={(id) => {
                const option = question.options.find((o) => o.id === id)
                if (option) dispatch({ type: 'answer', optionId: id, steps: option.steps })
              }}
            />
          )}
          <Reorder.Group
            axis="y"
            values={steps}
            onReorder={(next) => dispatch({ type: 'reorder', steps: next })}
            className="flex flex-col gap-2"
            aria-label="Steps"
          >
            <AnimatePresence initial={false}>
              {steps.map((step, i) => (
                <StepRow
                  key={step.id}
                  step={step}
                  index={i}
                  state={stateOf(i)}
                  objects={sample.objects}
                  containers={sample.containers}
                  onEdit={(patch) => dispatch({ type: 'edit', id: step.id, patch })}
                  onRemove={() => dispatch({ type: 'remove', id: step.id })}
                />
              ))}
            </AnimatePresence>
          </Reorder.Group>
          <Button
            variant="quiet"
            className="self-start"
            icon={<Plus size={16} />}
            onClick={() =>
              dispatch({ type: 'add', step: defaultStep(sample.objects, sample.containers) })
            }
          >
            Add step
          </Button>
          {conversation}
          {learn && learn.discrepancies.length > 0 && !question && (
            <p className="text-xs leading-relaxed text-ink-faint">{learn.discrepancies[0]}</p>
          )}
        </div>
      )}
    </Panel>
  )
}
