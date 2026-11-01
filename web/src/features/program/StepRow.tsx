import { Check, DotsSixVertical, PencilSimple, X } from '@phosphor-icons/react'
import { Reorder, useDragControls } from 'motion/react'
import { useState } from 'react'

import type { Action, Relation } from '../../api/schemas'
import {
  cn,
  describeRelation,
  describeStep,
  objectTone,
  RELATIONS,
  targetsFor,
} from '../../lib/format'
import type { EditableStep } from '../workbench'

export type StepState = 'idle' | 'waiting' | 'active' | 'done'

interface Props {
  step: EditableStep
  index: number
  objects: string[]
  containers: string[]
  /** Where the robot is in this step while its video plays. */
  state?: StepState
  onEdit: (patch: Partial<Pick<EditableStep, 'object' | 'action' | 'target' | 'relation'>>) => void
  onRemove: () => void
}

const ACTIONS: Array<[Action, string]> = [
  ['place_in', 'goes in'],
  ['stack_on', 'goes on'],
  ['place_near', 'goes beside'],
  ['push', 'is pushed to'],
  ['pour', 'pours into'],
  ['stir', 'stirs'],
  ['cut', 'cuts'],
  ['press', 'is pressed'],
  ['wipe', 'wipes'],
  ['open', 'is opened'],
]

/** Actions that act on the object itself, so there is no target to pick. */
const SELF_ACTIONS: ReadonlySet<Action> = new Set(['open', 'press'])

const selectClass =
  'h-8 min-w-0 rounded-md border border-line bg-raised px-2 text-sm text-ink transition-colors ' +
  'hover:border-line-strong'

export function StepRow({
  step,
  index,
  objects,
  containers,
  state = 'idle',
  onEdit,
  onRemove,
}: Props) {
  const controls = useDragControls()
  const [editing, setEditing] = useState(false)
  const targets = targetsFor(step.action, step.object, objects, containers)
  const self = SELF_ACTIONS.has(step.action)

  function changeAction(action: Action) {
    const pool = targetsFor(action, step.object, objects, containers)
    onEdit({
      action,
      target: SELF_ACTIONS.has(action)
        ? step.object
        : pool.includes(step.target)
          ? step.target
          : (pool[0] ?? step.target),
    })
  }

  function changeObject(object: string) {
    onEdit(self ? { object, target: object } : { object })
  }

  return (
    <Reorder.Item
      value={step}
      dragListener={false}
      dragControls={controls}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      whileDrag={{ scale: 1.02, boxShadow: '0 18px 40px -16px rgba(17,21,26,0.35)' }}
      className={cn(
        'group relative flex flex-col gap-2 rounded-xl border bg-canvas/60 py-2.5 pr-2 pl-1 transition-colors duration-300',
        state === 'active' ? 'border-accent bg-accent/10' : 'border-line',
        state === 'waiting' && 'opacity-60',
      )}
    >
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          aria-label={`Drag step ${index + 1} to reorder`}
          onPointerDown={(e) => controls.start(e)}
          className="grid size-7 shrink-0 cursor-grab touch-none place-items-center rounded-md text-ink-faint hover:text-ink active:cursor-grabbing"
        >
          <DotsSixVertical size={18} />
        </button>
        <span
          className={cn(
            'grid size-6 shrink-0 place-items-center rounded-md font-mono text-xs font-medium',
            state === 'done' ? 'bg-ok text-white' : 'bg-ink text-canvas',
          )}
        >
          {state === 'done' ? <Check size={13} weight="bold" aria-label="Done" /> : index + 1}
        </span>
        <span
          className="ml-1 size-2.5 shrink-0 rounded-full"
          style={{ background: objectTone(step.object) }}
          aria-hidden
        />
        <p className="min-w-0 flex-1 text-sm leading-snug font-medium break-words">
          {describeStep(step)}
        </p>
        <button
          type="button"
          aria-label={editing ? `Finish editing step ${index + 1}` : `Edit step ${index + 1}`}
          aria-pressed={editing}
          onClick={() => setEditing((v) => !v)}
          className={cn(
            'grid size-7 shrink-0 place-items-center rounded-md transition-colors active:scale-95',
            editing ? 'bg-ink text-canvas' : 'text-ink-faint hover:bg-ink/8 hover:text-ink',
          )}
        >
          {editing ? <Check size={15} weight="bold" /> : <PencilSimple size={15} />}
        </button>
        <button
          type="button"
          aria-label={`Remove step ${index + 1}`}
          onClick={onRemove}
          className="grid size-7 shrink-0 place-items-center rounded-md text-ink-faint transition-colors hover:bg-danger/10 hover:text-danger active:scale-95"
        >
          <X size={15} />
        </button>
      </div>
      {editing && (
        <div className="flex flex-col gap-1.5 pl-9">
          <div className="grid grid-cols-[minmax(0,1fr)_8rem] gap-1.5">
            <select
              aria-label={`Step ${index + 1} object`}
              className={selectClass}
              value={step.object}
              onChange={(e) => changeObject(e.target.value)}
            >
              {objects.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
            <select
              aria-label={`Step ${index + 1} action`}
              className={selectClass}
              value={step.action}
              onChange={(e) => changeAction(e.target.value as Action)}
            >
              {ACTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          {!self && (
            <select
              aria-label={`Step ${index + 1} target`}
              className={selectClass}
              value={step.target}
              onChange={(e) => onEdit({ target: e.target.value })}
            >
              {targets.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          )}
          {(step.action === 'place_near' || step.action === 'push') && (
            <select
              aria-label={`Relation for step ${index + 1}`}
              className={selectClass}
              value={step.relation ?? 'next_to'}
              onChange={(e) => onEdit({ relation: e.target.value as Relation })}
            >
              {RELATIONS.map((r) => (
                <option key={r} value={r}>
                  {describeRelation(r)}
                </option>
              ))}
            </select>
          )}
        </div>
      )}
    </Reorder.Item>
  )
}
