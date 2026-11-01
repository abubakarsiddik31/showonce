import { CheckCircle } from '@phosphor-icons/react'
import type { ReactNode } from 'react'

import { cn } from '../../lib/format'

function Row({
  n,
  title,
  children,
  visual,
}: {
  n: string
  title: string
  children: ReactNode
  visual: ReactNode
}) {
  return (
    <li className="grid gap-6 border-t border-line-strong py-10 lg:grid-cols-[6rem_1fr_1.15fr] lg:gap-10 lg:py-14">
      <span className="font-display text-5xl leading-none font-semibold text-ink-faint">{n}</span>
      <div className="flex max-w-[44ch] flex-col gap-3">
        <h3 className="font-display text-3xl leading-tight font-semibold tracking-tight">
          {title}
        </h3>
        <p className="text-base leading-relaxed text-ink-dim">{children}</p>
      </div>
      <div aria-hidden>{visual}</div>
    </li>
  )
}

function Bubble({ robot, children }: { robot?: boolean; children: ReactNode }) {
  return (
    <p
      className={cn(
        'max-w-[88%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
        robot
          ? 'self-start rounded-tl-md border border-line bg-raised'
          : 'self-end rounded-tr-md bg-ink text-canvas',
      )}
    >
      {children}
    </p>
  )
}

/** Three steps, each with a small picture of what it looks like in the studio. */
export function HowItWorks() {
  return (
    <section id="how" aria-labelledby="how-title" className="scroll-mt-24 py-10">
      <h2 id="how-title" className="font-mono text-xs tracking-wide text-ink-faint uppercase">
        How it works
      </h2>
      <ol className="mt-6">
        <Row
          n="01"
          title="Show it once"
          visual={
            <div className="flex items-center gap-3 rounded-2xl border border-dashed border-line-strong p-5">
              <div className="viewport aspect-video w-32 shrink-0 rounded-lg" />
              <p className="text-sm text-ink-dim">
                <span className="block font-medium text-ink">my_clip.mp4</span>
                No labels, no object names. It looks at the table and finds everything itself.
              </p>
            </div>
          }
        >
          Pick one of the demo clips or upload your own overhead video of a tabletop task. There is
          nothing to name or draw: the robot finds the objects and follows them through the clip.
        </Row>
        <Row
          n="02"
          title="Talk it through"
          visual={
            <div className="flex flex-col gap-2.5 rounded-2xl bg-sunken p-5">
              <Bubble robot>
                I saw you scrub the white plate clean with the yellow sponge, then do the same to
                the blue one. Did I get it right?
              </Bubble>
              <Bubble>Only the white one needs cleaning.</Bubble>
              <Bubble robot>Got it, just the white plate. Is that right?</Bubble>
            </div>
          }
        >
          Before it moves, it says what it understood, in plain words, and waits. You correct it by
          typing. It only gets going when you tell it that it has it right.
        </Row>
        <Row
          n="03"
          title="Watch it work"
          visual={
            <div className="viewport !rounded-2xl p-4 text-white">
              <p className="text-sm">
                <span className="font-medium">wipe the white plate with the yellow sponge</span>
                <span className="block text-white/65">
                  I&apos;ll scrub it with the sponge, my own way, until it is clean.
                </span>
              </p>
              <p className="mt-3 flex items-center gap-2 font-mono text-xs text-white/70">
                <CheckCircle size={16} weight="fill" className="text-ok" /> 14 of 14 stains wiped
              </p>
            </div>
          }
        >
          The robot does it on a table it has never seen, with its own motions: it does not copy
          your hands. Then it looks at the finished table and, if it missed something, tries once
          more.
        </Row>
      </ol>
    </section>
  )
}
