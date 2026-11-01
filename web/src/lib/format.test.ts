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
    expect(objectTone('green block')).toBe('#1e9e4f')
    expect(objectTone('spanner')).toBe('#6b7782')
  })
})

describe('describeStep for the new actions', () => {
  it('words place_near with and without a relation', () => {
    expect(
      describeStep({
        object: 'red block',
        action: 'place_near',
        target: 'blue block',
        relation: 'left_of',
      }),
    ).toBe('put red block left of blue block')
    expect(describeStep({ object: 'red block', action: 'place_near', target: 'blue block' })).toBe(
      'put red block next to blue block',
    )
  })

  it('words the other five', () => {
    expect(describeStep({ object: 'green book', action: 'push', target: 'bin' })).toBe(
      'push green book into bin',
    )
    expect(describeStep({ object: 'red cup', action: 'pour', target: 'bowl' })).toBe(
      'pour red cup into bowl',
    )
    expect(describeStep({ object: 'yellow spoon', action: 'stir', target: 'bowl' })).toBe(
      'stir bowl with yellow spoon',
    )
    expect(describeStep({ object: 'gray knife', action: 'cut', target: 'white bar' })).toBe(
      'cut white bar with gray knife',
    )
    expect(describeStep({ object: 'orange lamp', action: 'press', target: 'orange lamp' })).toBe(
      'press orange lamp',
    )
  })

  it('targets the new actions', () => {
    const objects = ['red block', 'blue block']
    const containers = ['bin']
    expect(targetsFor('place_near', 'red block', objects, containers)).toEqual(['blue block'])
    expect(targetsFor('push', 'red block', objects, containers)).toEqual(['blue block', 'bin'])
    expect(targetsFor('pour', 'red cup', objects, containers)).toEqual(['bin'])
    expect(targetsFor('stir', 'red cup', objects, containers)).toEqual(['bin'])
    expect(targetsFor('cut', 'red block', objects, containers)).toEqual(['blue block'])
    expect(targetsFor('press', 'red block', objects, containers)).toEqual(['red block'])
  })
})

describe('plural', () => {
  it('only adds the s when it is not exactly one', () => {
    expect(plural(1, 'step')).toBe('1 step')
    expect(plural(0, 'step')).toBe('0 steps')
    expect(plural(3, 'step')).toBe('3 steps')
  })
})
