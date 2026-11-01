import { Question as QuestionIcon } from '@phosphor-icons/react'
import { AnimatePresence, motion } from 'motion/react'

import type { Question } from '../../api/schemas'
import { LiveDot } from '../../components/LiveDot'
import { cn, objectTone } from '../../lib/format'

interface Props {
  question: Question
  chosen: string | null
  onChoose: (optionId: string) => void
}

/** The Ask step: shown only when the two readings of the demo disagree. */
export function AskCard({ question, chosen, onChoose }: Props) {
  const answered = chosen !== null
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 120, damping: 20 }}
      className="flex flex-col gap-4 rounded-2xl border border-line-strong bg-raised p-5 shadow-[0_20px_40px_-24px_rgba(17,21,26,0.35)]"
    >
      <div className="flex items-center gap-2 text-xs font-medium text-ink">
        {answered ? <QuestionIcon size={16} /> : <LiveDot />}
        {answered ? 'Answered' : 'Needs your call'}
      </div>
      <p className="text-sm leading-relaxed text-ink">{question.prompt}</p>
      <div role="radiogroup" aria-label={question.prompt} className="grid gap-3">
        {question.options.map((option) => {
          const selected = chosen === option.id
          return (
            <button
              key={option.id}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChoose(option.id)}
              className={cn(
                'rounded-xl border p-3 text-left transition-[transform,border-color,background-color] duration-200',
                'active:scale-[0.99]',
                selected
                  ? 'border-accent bg-accent/10'
                  : 'border-line hover:border-line-strong hover:bg-ink/[0.03]',
              )}
            >
              <span className="text-sm font-medium">{option.label}</span>
              <ol className="mt-2 flex flex-col gap-1">
                {option.steps.map((step, i) => (
                  <li
                    key={`${i}-${step.text}`}
                    className="flex items-center gap-2 text-xs text-ink-dim"
                  >
                    <span className="w-4 font-mono text-ink-faint">{i + 1}</span>
                    <span
                      className="size-1.5 shrink-0 rounded-full"
                      style={{ background: objectTone(step.object) }}
                    />
                    <span className="font-mono">{step.text}</span>
                  </li>
                ))}
              </ol>
            </button>
          )
        })}
      </div>
      <AnimatePresence>
        {answered && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="text-xs text-ink-faint"
          >
            Saved with the program. The robot will not ask again.
          </motion.p>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
