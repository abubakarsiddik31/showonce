import type { Step } from '../../api/schemas'

export type Speaker = 'person' | 'robot'

export interface ChatMessage {
  id: string
  from: Speaker
  text: string
  /** The plan as it stood when this was said, shown under the text. */
  steps?: Step[]
  /** Also show, for each step, how the robot will do it. */
  showHow?: boolean
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

export const greeting = (steps: Step[]): Omit<ChatMessage, 'id'> =>
  steps.length > 0
    ? {
        from: 'robot',
        text: 'I watched your clip. This is what I understood you did. Is that right?',
        steps,
      }
    : {
        from: 'robot',
        text: 'I watched your clip but could not make out a clear task. Tell me what you did, in your own words.',
      }

export const confirmation = (steps: Step[]): Omit<ChatMessage, 'id'> => ({
  from: 'robot',
  text: 'Learned. I will not copy your hands: I will do each step my own way, wherever things are on the table.',
  steps,
  showHow: true,
})

export const askWhatIsDifferent: Omit<ChatMessage, 'id'> = {
  from: 'robot',
  text: 'Tell me what is different. For example: \u201Calso clean the blue plate\u201D, or \u201Cdo the red one last\u201D.',
}

/** The same plan, said the same way: used to tell whether a reply changed anything. */
export const planKey = (steps: Step[]): string =>
  steps.map((s) => `${s.object}|${s.action}|${s.target}`).join(';')
