import { describe, expect, it } from 'vitest'

import type { Step } from '../api/schemas'
import { initialState, isEdited, workbenchReducer } from './workbench'

const step = (object: string, target = 'box'): Step => ({
  object,
  target,
  action: 'place_in',
  text: `put ${object} in ${target}`,
})

const loaded = () =>
  workbenchReducer(initialState, { type: 'learned', steps: [step('red'), step('blue')] })

describe('workbenchReducer', () => {
  it('loads learned steps with stable ids and is not edited', () => {
    const state = loaded()
    expect(state.steps.map((s) => s.object)).toEqual(['red', 'blue'])
    expect(new Set(state.steps.map((s) => s.id)).size).toBe(2)
    expect(isEdited(state)).toBe(false)
  })

  it('edits a step and refreshes its text', () => {
    const state = loaded()
    const id = state.steps[0]!.id
    const next = workbenchReducer(state, { type: 'edit', id, patch: { target: 'tray' } })
    expect(next.steps[0]!.text).toBe('put red in tray')
    expect(isEdited(next)).toBe(true)
  })

  it('removes, reorders and restores', () => {
    const state = loaded()
    const removed = workbenchReducer(state, { type: 'remove', id: state.steps[0]!.id })
    expect(removed.steps).toHaveLength(1)
    const swapped = workbenchReducer(state, { type: 'reorder', steps: [...state.steps].reverse() })
    expect(swapped.steps.map((s) => s.object)).toEqual(['blue', 'red'])
    expect(isEdited(swapped)).toBe(true)
    expect(workbenchReducer(swapped, { type: 'restore' }).steps.map((s) => s.object)).toEqual([
      'red',
      'blue',
    ])
  })

  it('records an answer and swaps in that plan', () => {
    const next = workbenchReducer(loaded(), {
      type: 'answer',
      optionId: 'muse_spark',
      steps: [step('green')],
    })
    expect(next.answer).toBe('muse_spark')
    expect(next.steps.map((s) => s.object)).toEqual(['green'])
  })

  it('keeps seed and oracle when the task is reset', () => {
    const state = workbenchReducer(loaded(), { type: 'seed', seed: 42 })
    const reset = workbenchReducer(state, { type: 'reset' })
    expect(reset.seed).toBe(42)
    expect(reset.steps).toEqual([])
  })
})
