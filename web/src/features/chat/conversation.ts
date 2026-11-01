export type Speaker = 'person' | 'robot'

export interface ChatMessage {
  id: string
  from: Speaker
  text: string
  /** False for a message that only invites more talk, so no "is that right?" buttons follow it. */
  asks?: boolean
}

export interface Conversation {
  messages: ChatMessage[]
  confirmed: boolean
}

export type ConversationAction =
  { type: 'reset' } | { type: 'say'; message: Omit<ChatMessage, 'id'> } | { type: 'confirmed' }

export const emptyConversation: Conversation = { messages: [], confirmed: false }

let counter = 0

export function conversationReducer(state: Conversation, action: ConversationAction): Conversation {
  switch (action.type) {
    case 'reset':
      return emptyConversation
    case 'say':
      return {
        ...state,
        messages: [...state.messages, { ...action.message, id: `m-${++counter}` }],
      }
    case 'confirmed':
      return { ...state, confirmed: true }
  }
}

/** The robot speaks first, in its own words, and then waits to hear whether it got it right. */
export const greeting = (understanding: string): Omit<ChatMessage, 'id'> => ({
  from: 'robot',
  text:
    understanding.trim() ||
    'I watched your clip but could not make out a clear task. Tell me what you did, in your own words.',
  asks: understanding.trim().length > 0,
})

export const confirmation: Omit<ChatMessage, 'id'> = {
  from: 'robot',
  text: 'Good, I have it. I will not copy your hands: I will do each step my own way, wherever things sit on the table. Here is what I will do.',
  asks: false,
}

export const askWhatIsDifferent: Omit<ChatMessage, 'id'> = {
  from: 'robot',
  text: 'Tell me what is different. For example: \u201Calso clean the blue plate\u201D, or \u201Cdo the red one last\u201D.',
  asks: false,
}

/** The same plan, said the same way: used to tell whether a reply changed anything. */
export const planKey = (
  steps: Array<{ object: string; action: string; target: string; relation?: string | null }>,
): string => steps.map((s) => `${s.object}|${s.action}|${s.target}|${s.relation ?? ''}`).join(';')
