import { describe, expect, it } from 'vitest'

import { describeStep, formatTime, objectTone } from './format'

describe('formatTime', () => {
  it('pads minutes and keeps one decimal', () => {
    expect(formatTime(83.24)).toBe('01:23.2')
    expect(formatTime(0)).toBe('00:00.0')
  })
  it('clamps negatives', () => {
    expect(formatTime(-4)).toBe('00:00.0')
  })
})

describe('describeStep', () => {
  it('reads naturally for both actions', () => {
    expect(describeStep({ object: 'red mug', action: 'place_in', target: 'tray' })).toBe(
      'put red mug in tray',
    )
    expect(describeStep({ object: 'red cup', action: 'stack_on', target: 'blue cup' })).toBe(
      'stack red cup on blue cup',
    )
  })
})

describe('objectTone', () => {
  it('uses the colour word in the name, with a neutral fallback', () => {
    expect(objectTone('green block')).toBe('#4ade80')
    expect(objectTone('spanner')).toBe('#a1a1aa')
  })
})
