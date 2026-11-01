import { ArrowCounterClockwise, Plus } from '@phosphor-icons/react'
import { AnimatePresence, Reorder } from 'motion/react'

import type { Sample } from '../../api/schemas'
import { Button } from '../../components/Button'
import { defaultStep, type EditableStep, type WorkbenchAction } from '../workbench'
import { StepRow, type StepState } from './StepRow'

interface Props {
  sample: Sample
  steps: EditableStep[]
  edited: boolean
  /** How far the robot's video has got, so the plan lights up in step with it. */
  progress: { done: number; active: number } | null
  dispatch: (action: WorkbenchAction) => void
}

/** The agreed plan as plain sentences: reorder, change or add steps in place. */
export function PlanEditor({ sample, steps, edited, progress, dispatch }: Props) {
  const stateOf = (i: number): StepState =>
    !progress ? 'idle' : i < progress.done ? 'done' : i === progress.active ? 'active' : 'waiting'

  return (
    <div className="flex flex-col gap-3">
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
      <div className="flex items-center gap-2">
        <Button
          variant="quiet"
          icon={<Plus size={16} />}
          onClick={() =>
            dispatch({ type: 'add', step: defaultStep(sample.objects, sample.containers) })
          }
        >
          Add step
        </Button>
        {edited && (
          <Button
            variant="quiet"
            icon={<ArrowCounterClockwise size={16} />}
            onClick={() => dispatch({ type: 'restore' })}
          >
            Back to what I learned
          </Button>
        )}
      </div>
    </div>
  )
}
