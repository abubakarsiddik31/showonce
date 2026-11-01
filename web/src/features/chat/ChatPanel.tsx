import { Check, PaperPlaneRight, PencilSimple } from '@phosphor-icons/react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useId, useRef, useState } from 'react'

import { Button } from '../../components/Button'
import { cn, objectTone } from '../../lib/format'
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
        {robot ? 'ShowOnce' : 'You'}
      </span>
      <div
        className={cn(
          'max-w-[92%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed',
          robot
            ? 'rounded-tl-md border border-line bg-raised text-ink'
            : 'rounded-tr-md bg-accent/25 text-ink',
        )}
      >
        <p>{message.text}</p>
        {message.steps && message.steps.length > 0 && (
          <ol className="mt-2.5 flex flex-col gap-2 border-t border-line pt-2.5">
            {message.steps.map((step, i) => (
              <li key={`${i}-${step.text}`} className="flex gap-2 text-xs">
                <span className="w-3 shrink-0 pt-px font-mono text-ink-faint">{i + 1}</span>
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="flex items-center gap-1.5 font-mono text-ink">
                    <span
                      className="size-1.5 shrink-0 rounded-full"
                      style={{ background: objectTone(step.object) }}
                      aria-hidden
                    />
                    {step.text}
                  </span>
                  {message.showHow && step.how && <span className="text-ink-dim">{step.how}</span>}
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </motion.li>
  )
}

/** Talk the plan through: the robot says what it understood and the person puts it right. */
export function ChatPanel({ messages, confirmed, thinking, onSend, onConfirm, onNotQuite }: Props) {
  const [draft, setDraft] = useState('')
  const inputId = useId()
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const last = messages[messages.length - 1]
  const awaitingConfirm =
    !confirmed && !thinking && last?.from === 'robot' && Boolean(last.steps?.length)

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })
  }, [messages.length, thinking])

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-sunken/60 p-3">
      <ul
        aria-live="polite"
        aria-label="Conversation"
        className="flex max-h-[26rem] flex-col gap-3 overflow-y-auto px-1 py-1"
      >
        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <Bubble key={m.id} message={m} />
          ))}
        </AnimatePresence>
        {thinking && (
          <li className="flex flex-col items-start gap-1" aria-label="Thinking">
            <span className="px-1 font-mono text-[10px] tracking-wide text-ink-faint uppercase">
              ShowOnce
            </span>
            <div className="skeleton h-9 w-40 rounded-2xl rounded-tl-md" />
          </li>
        )}
        <div ref={endRef} />
      </ul>

      {awaitingConfirm && (
        <div className="flex flex-wrap gap-2 px-1">
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
            confirmed ? 'Change something, or ask a question' : 'Correct me, in your own words'
          }
          autoComplete="off"
          className="h-9 min-w-0 flex-1 rounded-lg border border-line bg-raised px-3 text-sm text-ink placeholder:text-ink-faint hover:border-line-strong"
        />
        <Button
          variant="ghost"
          type="submit"
          aria-label="Send"
          disabled={!draft.trim() || thinking}
          icon={<PaperPlaneRight size={16} />}
        />
      </form>
    </div>
  )
}
