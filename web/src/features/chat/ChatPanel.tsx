import { Check, PaperPlaneRight, PencilSimple } from '@phosphor-icons/react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useId, useRef, useState } from 'react'

import { Button } from '../../components/Button'
import { cn } from '../../lib/format'
import type { ChatMessage } from './conversation'

interface Props {
  messages: ChatMessage[]
  confirmed: boolean
  thinking: boolean
  onSend: (text: string) => void
  onConfirm: () => void
  onNotQuite: () => void
}

function Bubble({ message }: { message: ChatMessage }) {
  const robot = message.from === 'robot'
  return (
    <motion.li
      layout="position"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 160, damping: 22 }}
      className={cn('flex flex-col gap-1', robot ? 'items-start' : 'items-end')}
    >
      <span className="px-1 font-mono text-[10px] tracking-wide text-ink-faint uppercase">
        {robot ? 'The robot' : 'You'}
      </span>
      <p
        className={cn(
          'max-w-[94%] rounded-2xl px-4 py-3 text-[15px] leading-relaxed',
          robot
            ? 'rounded-tl-md border border-line bg-raised text-ink'
            : 'rounded-tr-md bg-ink text-canvas',
        )}
      >
        {message.text}
      </p>
    </motion.li>
  )
}

/**
 * Talk it through. The robot speaks first, says what it understood, and then waits: nothing
 * moves until the person says it is right.
 */
export function ChatPanel({ messages, confirmed, thinking, onSend, onConfirm, onNotQuite }: Props) {
  const [draft, setDraft] = useState('')
  const inputId = useId()
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const last = messages[messages.length - 1]
  const awaitingConfirm = !confirmed && !thinking && last?.from === 'robot' && last.asks !== false

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })
  }, [messages.length, thinking])

  return (
    <div className="flex flex-col gap-3">
      <ul
        aria-live="polite"
        aria-label="Conversation"
        className="flex max-h-[24rem] min-h-24 flex-col gap-3 overflow-y-auto pr-1"
      >
        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <Bubble key={m.id} message={m} />
          ))}
        </AnimatePresence>
        {thinking && (
          <li className="flex flex-col items-start gap-1" aria-label="Thinking">
            <span className="px-1 font-mono text-[10px] tracking-wide text-ink-faint uppercase">
              The robot
            </span>
            <div className="skeleton h-11 w-44 rounded-2xl rounded-tl-md" />
          </li>
        )}
        <div ref={endRef} />
      </ul>

      {awaitingConfirm && (
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" icon={<Check size={16} weight="bold" />} onClick={onConfirm}>
            Yes, that&apos;s right
          </Button>
          <Button
            icon={<PencilSimple size={16} />}
            onClick={() => {
              onNotQuite()
              inputRef.current?.focus()
            }}
          >
            Not quite
          </Button>
        </div>
      )}

      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (!draft.trim() || thinking) return
          onSend(draft)
          setDraft('')
        }}
      >
        <label htmlFor={inputId} className="sr-only">
          Tell the robot what to change
        </label>
        <input
          id={inputId}
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={
            confirmed ? 'Change something, or ask a question' : 'Or tell me more, in your own words'
          }
          autoComplete="off"
          className="h-10 min-w-0 flex-1 rounded-lg border border-line-strong bg-raised px-3 text-sm text-ink placeholder:text-ink-faint hover:border-ink/40"
        />
        <Button
          variant="ghost"
          type="submit"
          aria-label="Send"
          disabled={!draft.trim() || thinking}
          icon={<PaperPlaneRight size={16} />}
          className="h-10"
        />
      </form>
    </div>
  )
}
