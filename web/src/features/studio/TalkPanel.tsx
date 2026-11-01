import { ChatsCircle } from '@phosphor-icons/react'
import type { ReactNode } from 'react'

import type { LearnResult } from '../../api/schemas'
import { Panel, StatusPill } from '../../components/Panel'
import { plural } from '../../lib/format'
import { AskCard } from '../program/AskCard'

interface Props {
  learn: LearnResult | null
  learning: boolean
  confirmed: boolean
  answer: string | null
  onAnswer: (optionId: string) => void
  /** The conversation itself. */
  chat: ReactNode
  /** The agreed plan, shown once the person has approved. */
  plan: ReactNode
  stepCount: number
}

const GHOST = ['I saw you…', 'It looked like you wanted…']

/**
 * Step two: the robot says what it understood and the person talks it through. The plan only
 * appears once they have said it is right, so the words come first and the steps second.
 */
export function TalkPanel({
  learn,
  learning,
  confirmed,
  answer,
  onAnswer,
  chat,
  plan,
  stepCount,
}: Props) {
  const question = learn?.questions[0]
  const status = learning ? (
    <StatusPill tone="live">Watching</StatusPill>
  ) : confirmed ? (
    <StatusPill tone="done">Agreed · {plural(stepCount, 'step')}</StatusPill>
  ) : learn ? (
    <StatusPill tone="live">Your turn</StatusPill>
  ) : (
    <StatusPill tone="idle">Waiting</StatusPill>
  )

  return (
    <Panel
      id="panel-talk"
      title="Talk it through"
      hint="The robot tells you what it understood, in words, and waits. Correct it as often as you like. It does nothing until you say it is right."
      status={status}
      waiting={!learn && !learning}
    >
      {learn ? (
        <div className="flex flex-col gap-5">
          {question && <AskCard question={question} chosen={answer} onChoose={onAnswer} />}
          {chat}
          {confirmed && plan}
        </div>
      ) : (
        <ul
          className="flex flex-col gap-2"
          aria-label="The robot will speak here once it has watched"
        >
          {GHOST.map((text) => (
            <li
              key={text}
              className="flex items-center gap-3 rounded-2xl rounded-tl-md border border-dashed border-line-strong px-4 py-3 text-sm text-ink-faint"
            >
              <ChatsCircle size={18} aria-hidden />
              {text}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
