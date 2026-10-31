import type { Relation, Step } from '../api/schemas'

export const RELATIONS: Relation[] = ['next_to', 'left_of', 'right_of', 'in_front_of', 'behind']

export function describeRelation(relation?: Relation | null): string {
  return (relation ?? 'next_to').replaceAll('_', ' ')
}

/** 83.2 -> "01:23.2" */
export function formatTime(seconds: number): string {
  const safe = Math.max(0, seconds)
  const minutes = Math.floor(safe / 60)
  const rest = safe - minutes * 60
  return `${String(minutes).padStart(2, '0')}:${rest.toFixed(1).padStart(4, '0')}`
}

export function describeStep(
  step: Pick<Step, 'object' | 'action' | 'target' | 'relation'>,
): string {
  switch (step.action) {
    case 'place_in':
      return `put ${step.object} in ${step.target}`
    case 'stack_on':
      return `stack ${step.object} on ${step.target}`
    case 'place_near':
      return `put ${step.object} ${describeRelation(step.relation)} ${step.target}`
    case 'push':
      return step.relation
        ? `push ${step.object} ${describeRelation(step.relation)} ${step.target}`
        : `push ${step.object} into ${step.target}`
    case 'pour':
      return `pour ${step.object} into ${step.target}`
    case 'stir':
      return `stir ${step.target} with ${step.object}`
    case 'cut':
      return `cut ${step.target} with ${step.object}`
    case 'press':
      return `press ${step.object}`
    case 'wipe':
      return `wipe ${step.target} with ${step.object}`
    case 'open':
      return `open ${step.object}`
  }
}

/** What an action can be aimed at: a container, an object, a surface, or the object itself. */
export function targetsFor(
  action: Step['action'],
  object: string,
  objects: string[],
  containers: string[],
): string[] {
  const others = objects.filter((o) => o !== object)
  switch (action) {
    case 'place_in':
      return containers
    case 'stack_on':
      return others
    case 'place_near':
      return others
    case 'push':
      return [...others, ...containers]
    case 'pour':
    case 'stir':
      return containers
    case 'cut':
      return others
    case 'press':
      return [object]
    case 'wipe':
      return [...others, ...containers]
    case 'open':
      return [object]
  }
}

const TONES: Record<string, string> = {
  red: '#f87171',
  orange: '#fb923c',
  yellow: '#facc15',
  green: '#4ade80',
  blue: '#60a5fa',
  purple: '#c084fc',
  pink: '#f472b6',
  white: '#e4e4e7',
}

/** The colour an object's own name suggests, so chips match what is on the table. */
export function objectTone(name: string): string {
  const lower = name.toLowerCase()
  for (const [word, tone] of Object.entries(TONES)) if (lower.includes(word)) return tone
  return '#a1a1aa'
}

export const cn = (...parts: Array<string | false | null | undefined>): string =>
  parts.filter(Boolean).join(' ')

/** plural(1, 'step') -> "1 step", plural(2, 'step') -> "2 steps" */
export const plural = (count: number, noun: string): string =>
  `${count} ${noun}${count === 1 ? '' : 's'}`
