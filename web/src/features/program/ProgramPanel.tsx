import { ArrowCounterClockwise, ListChecks, Plus } from '@phosphor-icons/react'
import { AnimatePresence, Reorder } from 'motion/react'
import type { ReactNode } from 'react'

import type { LearnResult, Sample } from '../../api/schemas'
import { Button } from '../../components/Button'
import { EmptyState } from '../../components/EmptyState'
import { Section } from '../../components/Section'
import { defaultStep, type EditableStep, type WorkbenchAction } from '../workbench'
import { AskCard } from './AskCard'
import { StepRow } from './StepRow'

interface Props {
  sample: Sample
  learn: LearnResult | null
  steps: EditableStep[]
  answer: string | null
  edited: boolean
  dispatch: (action: WorkbenchAction) => void
  /** The talk-it-through panel, shown once there is something to talk about. */
  conversation?: ReactNode
}

export function ProgramPanel({
  sample,
  learn,
  steps,
  answer,
  edited,
  dispatch,
  conversation,
}: Props) {
  const question = learn?.questions[0]

  return (
    <Section
      index="02"
      title="Task program"
      hint="The robot says what it understood. Correct it in words, or edit the steps directly: they name objects, never positions, so they work on any layout."
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
        <EmptyState icon={<ListChecks size={24} />} title="Nothing learned yet">
          Press &ldquo;Learn from this video&rdquo;. The steps SAM and Muse Spark agree on appear
          here, ready to edit.
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-4">
          {conversation}
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
          <p className="-mb-2 font-mono text-xs text-ink-faint">The plan</p>
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
          {learn && learn.discrepancies.length > 0 && !question && (
            <p className="text-xs leading-relaxed text-ink-faint">{learn.discrepancies[0]}</p>
          )}
        </div>
      )}
    </Section>
  )
}
