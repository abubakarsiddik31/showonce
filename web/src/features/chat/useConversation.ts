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
 * The talk-it-through loop: the robot says what it understood, the person corrects it in words,
 * and the plan is revised until they confirm.
 */
export function useConversation(
  sampleId: string | null,
  steps: Step[],
  onRevise: (steps: Step[]) => void,
) {
  const [state, dispatch] = useReducer(conversationReducer, emptyConversation)
  const chat = useChat()

  const start = useCallback((learned: Step[]) => {
    dispatch({ type: 'reset' })
    dispatch({ type: 'say', message: greeting(learned) })
  }, [])

  const reset = useCallback(() => dispatch({ type: 'reset' }), [])

  const confirm = useCallback(() => {
    dispatch({ type: 'say', message: { from: 'person', text: "Yes, that's right." } })
    dispatch({ type: 'say', message: confirmation(steps) })
    dispatch({ type: 'confirmed' })
  }, [steps])

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
            const changed = planKey(reply.steps) !== planKey(steps)
            if (changed) onRevise(reply.steps)
            dispatch({
              type: 'say',
              message: {
                from: 'robot',
                text: reply.reply,
                steps: changed ? reply.steps : undefined,
              },
            })
            if (reply.confirmed) {
              dispatch({ type: 'say', message: confirmation(changed ? reply.steps : steps) })
              dispatch({ type: 'confirmed' })
            }
          },
          onError: () =>
            dispatch({
              type: 'say',
              message: {
                from: 'robot',
                text: 'I could not reach my language model just now. You can still edit the steps below.',
              },
            }),
        },
      )
    },
    [chat, onRevise, sampleId, state.messages, steps],
  )

  return { ...state, thinking: chat.isPending, start, reset, send, confirm, notQuite }
}
