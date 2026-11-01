import { ArrowDown, ArrowRight } from '@phosphor-icons/react'
import { motion } from 'motion/react'

import { Button } from '../../components/Button'
import { LiveDot } from '../../components/LiveDot'

interface Props {
  onStart: () => void
  onHow: () => void
}

/** The promise, and the robot doing it. Left-aligned text beside the footage. */
export function Hero({ onStart, onHow }: Props) {
  return (
    <section className="grid items-center gap-10 py-12 lg:grid-cols-[1.05fr_1fr] lg:gap-14 lg:py-20">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        className="flex flex-col gap-7"
      >
        <p className="flex w-fit items-center gap-2 rounded-full border border-line-strong px-3 py-1.5 font-mono text-[11px] text-ink-dim">
          <LiveDot /> A robot that learns from one demo
        </p>
        <h1 className="font-display text-[clamp(2.75rem,6.4vw,5.75rem)] leading-[0.92] font-semibold tracking-[-0.035em] text-balance">
          Show it once.
          <br />
          <span className="text-ink-faint">The robot does the rest.</span>
        </h1>
        <p className="max-w-[48ch] text-lg leading-relaxed text-ink-dim">
          Film a task a single time. The robot tells you what it understood, in words, and waits for
          you to say it is right. Then it does the job on a table it has never seen, its own way,
          and checks its own work.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="primary"
            size="lg"
            icon={<ArrowRight size={20} weight="bold" />}
            onClick={onStart}
          >
            Start teaching
          </Button>
          <Button size="lg" icon={<ArrowDown size={18} />} onClick={onHow}>
            See how it works
          </Button>
        </div>
      </motion.div>

      <motion.figure
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
        className="flex flex-col gap-3"
      >
        <div className="viewport !rounded-3xl shadow-[0_40px_80px_-40px_rgba(17,21,26,0.55)]">
          <video
            src="/robot-demo.mp4"
            poster="/robot-cell.jpg"
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            aria-label="The robot arm scrubbing two stained plates in a simulation"
            className="aspect-video w-full object-cover"
          />
        </div>
        <figcaption className="flex items-center justify-between gap-4 px-1 text-xs text-ink-faint">
          <span>Live from the simulator: scrubbing stained plates, in circles.</span>
          <span className="hidden font-mono sm:inline">Franka arm · MuJoCo</span>
        </figcaption>
      </motion.figure>
    </section>
  )
}
