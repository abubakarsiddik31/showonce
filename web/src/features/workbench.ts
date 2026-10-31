import type { Action, Step } from '../api/schemas'
import { describeStep as describe } from '../lib/format'

export interface EditableStep extends Step {
  id: string
}

export interface WorkbenchState {
  steps: EditableStep[]
  learned: EditableStep[]
  answer: string | null
  seed: number
  oracle: boolean
}

export type WorkbenchAction =
  | { type: 'reset' }
  | { type: 'learned'; steps: Step[] }
  | { type: 'answer'; optionId: string; steps: Step[] }
  | { type: 'edit'; id: string; patch: Partial<Pick<Step, 'object' | 'action' | 'target'>> }
  | { type: 'remove'; id: string }
  | { type: 'add'; step: Step }
  | { type: 'reorder'; steps: EditableStep[] }
  | { type: 'restore' }
  | { type: 'seed'; seed: number }
  | { type: 'oracle'; oracle: boolean }

export const initialState: WorkbenchState = {
  steps: [],
  learned: [],
  answer: null,
  seed: 3,
  oracle: false,
}

let counter = 0
const withIds = (steps: Step[]): EditableStep[] =>
  steps.map((s) => ({ ...s, id: `step-${++counter}` }))

const refresh = (step: EditableStep): EditableStep => ({ ...step, text: describe(step) })

export function workbenchReducer(state: WorkbenchState, action: WorkbenchAction): WorkbenchState {
  switch (action.type) {
    case 'reset':
      return { ...initialState, seed: state.seed, oracle: state.oracle }
    case 'learned': {
      const steps = withIds(action.steps)
      return { ...state, steps, learned: steps, answer: null }
    }
    case 'answer':
      return { ...state, steps: withIds(action.steps), answer: action.optionId }
    case 'edit':
      return {
        ...state,
        steps: state.steps.map((s) =>
          s.id === action.id ? refresh({ ...s, ...action.patch }) : s,
        ),
      }
    case 'remove':
      return { ...state, steps: state.steps.filter((s) => s.id !== action.id) }
    case 'add':
      return { ...state, steps: [...state.steps, ...withIds([action.step])] }
    case 'reorder':
      return { ...state, steps: action.steps }
    case 'restore':
      return { ...state, steps: state.learned, answer: null }
    case 'seed':
      return { ...state, seed: action.seed }
    case 'oracle':
      return { ...state, oracle: action.oracle }
  }
}

export const isEdited = (state: WorkbenchState): boolean =>
  state.steps.length !== state.learned.length ||
  state.steps.some((s, i) => describe(s) !== describe(state.learned[i] ?? s))

export const defaultStep = (objects: string[], containers: string[]): Step => {
  const object = objects[0] ?? 'object'
  const target = containers[0] ?? 'container'
  const action: Action = 'place_in'
  return { object, action, target, text: describe({ object, action, target }) }
}
