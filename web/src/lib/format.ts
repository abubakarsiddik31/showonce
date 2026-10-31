import type { Step } from '../api/schemas'

/** 83.2 -> "01:23.2" */
export function formatTime(seconds: number): string {
  const safe = Math.max(0, seconds)
  const minutes = Math.floor(safe / 60)
  const rest = safe - minutes * 60
  return `${String(minutes).padStart(2, '0')}:${rest.toFixed(1).padStart(4, '0')}`
}

export function describeStep(step: Pick<Step, 'object' | 'action' | 'target'>): string {
  return step.action === 'place_in'
    ? `put ${step.object} in ${step.target}`
    : `stack ${step.object} on ${step.target}`
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
