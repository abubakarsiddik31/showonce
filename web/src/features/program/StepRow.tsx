import { DotsSixVertical, X } from '@phosphor-icons/react'
import { Reorder, useDragControls } from 'motion/react'

import type { Action, Relation } from '../../api/schemas'
import { describeRelation, objectTone, RELATIONS, targetsFor } from '../../lib/format'
import type { EditableStep } from '../workbench'

interface Props {
  step: EditableStep
  index: number
  objects: string[]
  containers: string[]
  onEdit: (patch: Partial<Pick<EditableStep, 'object' | 'action' | 'target' | 'relation'>>) => void
  onRemove: () => void
}

const selectClass =
  'h-8 min-w-0 rounded-md border border-line bg-sunken px-2 text-sm text-ink transition-colors ' +
  'hover:border-line-strong'

export function StepRow({ step, index, objects, containers, onEdit, onRemove }: Props) {
  const controls = useDragControls()
  const targets = targetsFor(step.action, step.object, objects, containers)

  function changeAction(action: Action) {
    const pool = targetsFor(action, step.object, objects, containers)
    onEdit({ action, target: pool.includes(step.target) ? step.target : (pool[0] ?? step.target) })
  }

  function changeObject(object: string) {
    // opening acts on the object itself, so its target follows it
    onEdit(step.action === 'open' ? { object, target: object } : { object })
  }

  return (
    <Reorder.Item
      value={step}
      dragListener={false}
      dragControls={controls}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      whileDrag={{ scale: 1.02, boxShadow: '0 18px 40px -16px rgba(0,0,0,0.7)' }}
      className="relative flex flex-col gap-1.5 rounded-xl border border-line bg-raised py-2 pr-2 pl-1"
    >
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label={`Drag step ${index + 1} to reorder`}
          onPointerDown={(e) => controls.start(e)}
          className="grid size-7 shrink-0 cursor-grab touch-none place-items-center rounded-md text-ink-faint hover:text-ink active:cursor-grabbing"
        >
          <DotsSixVertical size={18} />
        </button>
        <span className="w-4 shrink-0 text-center font-mono text-xs text-ink-faint">
          {index + 1}
        </span>
        <span
          className="size-2 shrink-0 rounded-full"
          style={{ background: objectTone(step.object) }}
          aria-hidden
        />
        <select
          aria-label={`Step ${index + 1} object`}
          className={`${selectClass} flex-1`}
          value={step.object}
          onChange={(e) => changeObject(e.target.value)}
        >
          {objects.map((o) => (
            <option key={o}>{o}</option>
          ))}
        </select>
        <button
          type="button"
          aria-label={`Remove step ${index + 1}`}
          onClick={onRemove}
          className="grid size-7 shrink-0 place-items-center rounded-md text-ink-faint transition-colors hover:bg-white/10 hover:text-danger active:scale-95"
        >
          <X size={16} />
        </button>
      </div>
      <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] items-center gap-1.5 pl-9">
        <select
          aria-label={`Step ${index + 1} action`}
          className={selectClass}
          value={step.action}
          onChange={(e) => changeAction(e.target.value as Action)}
        >
          <option value="place_in">into</option>
          <option value="stack_on">onto</option>
          <option value="wipe">wipes</option>
          <option value="open">opens</option>
        </select>
        {step.action === 'open' ? (
          <span className="px-1 text-sm text-ink-faint">tears it open</span>
        ) : (
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
      </div>
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
    </Reorder.Item>
  )
}
