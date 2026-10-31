import { describe, expect, it } from 'vitest'

import type { Step } from '../../api/schemas'
import {
  confirmation,
  conversationReducer,
  emptyConversation,
  greeting,
  planKey,
} from './conversation'

const wipe: Step = {
  object: 'yellow sponge',
  action: 'wipe',
  target: 'white plate',
  text: 'wipe white plate with yellow sponge',
  how: "I'll scrub it my own way.",
}

describe('conversation', () => {
  it('greets with the plan it understood and asks if it is right', () => {
    const message = greeting([wipe])
    expect(message.from).toBe('robot')
    expect(message.steps).toEqual([wipe])
    expect(message.text).toMatch(/right\?$/)
  })

  it('asks for a description when it understood nothing', () => {
    const message = greeting([])
    expect(message.steps).toBeUndefined()
    expect(message.text).toMatch(/Tell me what you did/)
  })

  it('shows how it will do each step once confirmed, and says it will not copy the hands', () => {
    const message = confirmation([wipe])
    expect(message.showHow).toBe(true)
    expect(message.text).toMatch(/my own way/)
  })

  it('collects messages with unique ids and remembers confirmation', () => {
    let state = conversationReducer(emptyConversation, { type: 'say', message: greeting([wipe]) })
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
    expect(planKey([wipe])).toBe(planKey([{ ...wipe, text: 'different words', how: '' }]))
    expect(planKey([wipe])).not.toBe(planKey([{ ...wipe, target: 'blue plate' }]))
  })
})
