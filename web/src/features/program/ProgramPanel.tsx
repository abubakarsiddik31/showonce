import { ArrowCounterClockwise, ListChecks, Plus } from '@phosphor-icons/react'
import { AnimatePresence, Reorder } from 'motion/react'

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
}

export function ProgramPanel({ sample, learn, steps, answer, edited, dispatch }: Props) {
  const question = learn?.questions[0]

  return (
    <Section
      index="02"
      title="Task program"
      hint="Steps name objects and containers, never positions, so they work on any layout. Edit them freely."
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
