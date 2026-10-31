import { describe, expect, it } from 'vitest'

import { describeStep, formatTime, objectTone, plural, targetsFor } from './format'

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

describe('wipe and open steps', () => {
  it('read naturally', () => {
    expect(describeStep({ object: 'sponge', action: 'wipe', target: 'plate' })).toBe(
      'wipe plate with sponge',
    )
    expect(describeStep({ object: 'chips', action: 'open', target: 'chips' })).toBe('open chips')
  })

  it('aim each action at what it can act on', () => {
    const objects = ['sponge', 'plate', 'chips']
    expect(targetsFor('place_in', 'sponge', objects, ['tray'])).toEqual(['tray'])
    expect(targetsFor('wipe', 'sponge', objects, ['tray'])).toEqual(['plate', 'chips', 'tray'])
    expect(targetsFor('open', 'chips', objects, ['tray'])).toEqual(['chips'])
  })
})

describe('objectTone', () => {
  it('uses the colour word in the name, with a neutral fallback', () => {
    expect(objectTone('green block')).toBe('#4ade80')
    expect(objectTone('spanner')).toBe('#a1a1aa')
  })
})

describe('plural', () => {
  it('only adds the s when it is not exactly one', () => {
    expect(plural(1, 'step')).toBe('1 step')
    expect(plural(0, 'step')).toBe('0 steps')
    expect(plural(3, 'step')).toBe('3 steps')
  })
})
