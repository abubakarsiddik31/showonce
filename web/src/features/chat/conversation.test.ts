import { describe, expect, it } from 'vitest'

import {
  confirmation,
  conversationReducer,
  emptyConversation,
  greeting,
  planKey,
} from './conversation'

describe('conversation', () => {
  it('opens with the robot saying what it understood, in its own words', () => {
    const message = greeting('I saw you scrub both plates. Did I get it right?')
    expect(message).toMatchObject({ from: 'robot', asks: true })
    expect(message.text).toBe('I saw you scrub both plates. Did I get it right?')
  })

  it('asks the person to describe the task when it understood nothing', () => {
    const message = greeting('   ')
    expect(message.text).toMatch(/Tell me what you did/)
    expect(message.asks).toBe(false)
  })

  it('says it will not copy the hands once the person approves', () => {
    expect(confirmation.text).toMatch(/my own way/)
    expect(confirmation.asks).toBe(false)
  })

  it('collects messages with unique ids and remembers confirmation', () => {
    let state = conversationReducer(emptyConversation, { type: 'say', message: greeting('Hi?') })
    state = conversationReducer(state, {
      type: 'say',
      message: { from: 'person', text: 'also the blue plate' },
    })
    state = conversationReducer(state, { type: 'confirmed' })
    expect(state.messages.map((m) => m.from)).toEqual(['robot', 'person'])
    expect(new Set(state.messages.map((m) => m.id)).size).toBe(2)
    expect(state.confirmed).toBe(true)
    expect(conversationReducer(state, { type: 'reset' })).toEqual(emptyConversation)
  })

  it('tells a changed plan from an unchanged one', () => {
    const wipe = { object: 'sponge', action: 'wipe', target: 'white plate' }
    expect(planKey([wipe])).toBe(planKey([{ ...wipe }]))
    expect(planKey([wipe])).not.toBe(planKey([{ ...wipe, target: 'blue plate' }]))
    expect(planKey([wipe])).not.toBe(planKey([{ ...wipe, relation: 'left_of' }]))
  })
})
