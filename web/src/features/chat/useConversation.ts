import { useCallback, useReducer } from 'react'

import { useChat } from '../../api/hooks'
import type { Step } from '../../api/schemas'
import {
  askWhatIsDifferent,
  confirmation,
  conversationReducer,
  emptyConversation,
  greeting,
  planKey,
  type ChatMessage,
} from './conversation'

const wire = (messages: ChatMessage[]) => messages.map((m) => ({ role: m.from, text: m.text }))

/**
 * The talk-it-through loop. The robot says, in words, what it understood and then waits; the
 * person answers or corrects it as often as they like; the plan only counts once they confirm.
 */
export function useConversation(
  sampleId: string | null,
  steps: Step[],
  onRevise: (steps: Step[]) => void,
) {
  const [state, dispatch] = useReducer(conversationReducer, emptyConversation)
  const chat = useChat()

  const start = useCallback((understanding: string) => {
    dispatch({ type: 'reset' })
    dispatch({ type: 'say', message: greeting(understanding) })
  }, [])

  const reset = useCallback(() => dispatch({ type: 'reset' }), [])

  const confirm = useCallback(() => {
    dispatch({ type: 'say', message: { from: 'person', text: "Yes, that's right." } })
    dispatch({ type: 'say', message: confirmation })
    dispatch({ type: 'confirmed' })
  }, [])

  const notQuite = useCallback(() => {
    dispatch({ type: 'say', message: { from: 'person', text: 'Not quite.' } })
    dispatch({ type: 'say', message: askWhatIsDifferent })
  }, [])

  const send = useCallback(
    (text: string) => {
      if (!sampleId || !text.trim()) return
      const said: ChatMessage = { id: 'pending', from: 'person', text: text.trim() }
      dispatch({ type: 'say', message: { from: 'person', text: said.text } })
      chat.mutate(
        { sampleId, messages: wire([...state.messages, said]), steps },
        {
          onSuccess: (reply) => {
            if (planKey(reply.steps) !== planKey(steps)) onRevise(reply.steps)
            dispatch({ type: 'say', message: { from: 'robot', text: reply.reply, asks: true } })
            if (reply.confirmed) {
              dispatch({ type: 'say', message: confirmation })
              dispatch({ type: 'confirmed' })
            }
          },
          onError: () =>
            dispatch({
              type: 'say',
              message: {
                from: 'robot',
                text: 'I could not reach my language model just now. You can still edit the steps.',
                asks: false,
              },
            }),
        },
      )
    },
    [chat, onRevise, sampleId, state.messages, steps],
  )

  return { ...state, thinking: chat.isPending, start, reset, send, confirm, notQuite }
}
