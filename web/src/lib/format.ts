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

/** In the robot's own words, how it will do a step. It does not copy the hand it watched. */
export function howItWillDo(step: Pick<Step, 'object' | 'action' | 'target' | 'relation'>): string {
  const { object, target } = step
  switch (step.action) {
    case 'place_in':
      return `I'll pick up the ${object} and set it down inside the ${target}.`
    case 'stack_on':
      return `I'll pick up the ${object} and set it on top of the ${target}.`
    case 'place_near': {
      const where =
        step.relation && step.relation !== 'next_to' ? describeRelation(step.relation) : 'beside'
      return `I'll pick up the ${object} and set it down ${where} the ${target}.`
    }
    case 'push': {
      const where = step.relation
        ? `${describeRelation(step.relation)} the ${target}`
        : `into the ${target}`
      return `I'll put my fingers behind the ${object} and push it ${where}, without lifting it.`
    }
    case 'pour':
      return `I'll hold the ${object} over the ${target} and pour, tipping it until it is empty.`
    case 'stir':
      return `I'll stir the ${target} round and round with the ${object} until it is mixed.`
    case 'cut':
      return `I'll draw the ${object} across the ${target}, cut it through, and lay the two halves flat.`
    case 'press':
      return `I'll press the ${object} straight down, once and firmly.`
    case 'wipe':
      return `I'll scrub the ${target} with the ${object}, my own way, until it is clean.`
    case 'open':
      return `I'll take hold of the seal on the ${object}, tear it off and lay it aside.`
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
  red: '#d93636',
  orange: '#e8710a',
  yellow: '#c99a06',
  green: '#1e9e4f',
  blue: '#2f6fdb',
  purple: '#8a4fd1',
  pink: '#d6428c',
  white: '#8b97a2',
}

/** The colour an object's own name suggests, so chips match what is on the table. */
export function objectTone(name: string): string {
  const lower = name.toLowerCase()
  for (const [word, tone] of Object.entries(TONES)) if (lower.includes(word)) return tone
  return '#6b7782'
}

export const cn = (...parts: Array<string | false | null | undefined>): string =>
  parts.filter(Boolean).join(' ')

/** plural(1, 'step') -> "1 step", plural(2, 'step') -> "2 steps" */
export const plural = (count: number, noun: string): string =>
  `${count} ${noun}${count === 1 ? '' : 's'}`

/** Clips grouped by the kind of task they show, groups and clips in a steady order. */
export function groupSamples<T extends { group: string; title: string }>(
  samples: T[],
): Array<[string, T[]]> {
  const groups = new Map<string, T[]>()
  for (const s of samples) groups.set(s.group, [...(groups.get(s.group) ?? []), s])
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([group, items]) => [group, [...items].sort((a, b) => a.title.localeCompare(b.title))])
}
