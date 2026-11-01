import {
  ArrowFatLineDown,
  ArrowRight,
  ArrowsHorizontal,
  Broom,
  Drop,
  HandPointing,
  Package,
  Scissors,
  Spiral,
  StackSimple,
} from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import type { ReactNode } from 'react'

const MOVES: Array<[string, Icon]> = [
  ['put in', ArrowFatLineDown],
  ['stack on', StackSimple],
  ['put beside', ArrowsHorizontal],
  ['push', ArrowRight],
]
const CLEAN: Array<[string, Icon]> = [
  ['wipe', Broom],
  ['open', Package],
  ['cut', Scissors],
  ['press', HandPointing],
]
const MIX: Array<[string, Icon]> = [
  ['pour', Drop],
  ['stir', Spiral],
]

function Chips({ title, items }: { title: string; items: Array<[string, Icon]> }) {
  return (
    <div>
      <p className="mb-2 font-mono text-[11px] text-ink-faint">{title}</p>
      <ul className="flex flex-wrap gap-2">
        {items.map(([name, Glyph]) => (
          <li
            key={name}
            className="flex items-center gap-2 rounded-full border border-line-strong bg-raised px-3 py-1.5 text-sm"
          >
            <Glyph size={16} aria-hidden /> {name}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Group({ index, title, children }: { index: string; title: string; children: ReactNode }) {
  return (
    <li className="grid gap-3 border-t border-line-strong py-8 md:grid-cols-[3rem_1fr]">
      <span className="font-mono text-xs text-ink-faint">{index}</span>
      <div className="flex max-w-[60ch] flex-col gap-4">
        <h3 className="font-display text-2xl font-semibold tracking-tight">{title}</h3>
        {children}
      </div>
    </li>
  )
}

const P = ({ children }: { children: ReactNode }) => (
  <p className="leading-relaxed text-ink-dim">{children}</p>
)

/** What it can do, grouped by what it is for, with the ten actions grouped too. */
export function Capabilities() {
  return (
    <section
      id="can"
      aria-labelledby="can-title"
      className="grid scroll-mt-24 gap-8 py-14 lg:grid-cols-[minmax(0,20rem)_1fr] lg:gap-16"
    >
      <div className="lg:sticky lg:top-24 lg:self-start">
        <h2 id="can-title" className="font-mono text-xs tracking-wide text-ink-faint uppercase">
          What it can do
        </h2>
        <p className="mt-4 font-display text-4xl leading-[1.02] font-semibold tracking-tight">
          Four things, each one checked.
        </p>
      </div>
      <ul>
        <Group index="A" title="It learns from one clip">
          <P>
            Upload any overhead video. SAM 3.1 follows every object through it and Muse Spark reads
            what happened, so what comes out is a task the robot can do, not a recording to copy.
          </P>
        </Group>
        <Group index="B" title="It checks that it understood">
          <P>
            It says what it saw in plain words and waits. You reply, it restates, and you go back
            and forth until it is right. Its answers are checked too: a plan can only use things
            that are really on the table.
          </P>
        </Group>
        <Group index="C" title="It does the job its own way">
          <P>
            Ten actions, so far. A wipe becomes its own circular scrub, an open becomes its own
            tear, a put becomes a pick and a place.
          </P>
          <div className="flex flex-col gap-4">
            <Chips title="Move things" items={MOVES} />
            <Chips title="Clean, open and prepare" items={CLEAN} />
            <Chips title="Pour and mix" items={MIX} />
          </div>
        </Group>
        <Group index="D" title="It checks its own work">
          <P>
            Simulator ground truth can be circular, so the robot also looks. After a run SAM
            inspects the finished table, and a step it sees as missed gets one more try. With no
            demo at all, tidy mode scatters a table and has the robot plan and tidy it.
          </P>
        </Group>
      </ul>
    </section>
  )
}
