import { ArrowRight } from '@phosphor-icons/react'
import { MotionConfig } from 'motion/react'

import { useDemos, useSamples } from '../../api/hooks'
import { Button } from '../../components/Button'
import { Logo } from '../../components/Logo'
import { studioHref } from '../../lib/route'
import { Capabilities } from './Capabilities'
import { ClipGallery } from './ClipGallery'
import { DemoShowcase } from './DemoShowcase'
import { Hero } from './Hero'
import { HowItWorks } from './HowItWorks'
import { Proof } from './Proof'

const jump = (id: string) =>
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

const LINKS: Array<[string, string]> = [
  ['watch', 'Watch it'],
  ['how', 'How it works'],
  ['can', 'What it can do'],
  ['clips', 'Clips'],
]

/** The message, on its own page: what it is, how it works, and a way in. */
export function Landing({ go }: { go: (href: string) => void }) {
  const samples = useSamples()
  const demos = useDemos()
  const start = () => go(studioHref())

  return (
    <MotionConfig reducedMotion="user">
      <div className="mx-auto flex min-h-[100dvh] max-w-[1400px] flex-col px-4 sm:px-8">
        <header className="sticky top-0 z-20 -mx-4 border-b border-line bg-canvas/85 px-4 backdrop-blur sm:-mx-8 sm:px-8">
          <div className="flex h-16 items-center gap-6">
            <a href="#/" className="flex items-center gap-2.5" aria-label="ShowOnce home">
              <Logo />
              <span className="font-display text-xl font-semibold tracking-tight">ShowOnce</span>
            </a>
            <nav aria-label="Sections" className="ml-6 hidden gap-6 text-sm text-ink-dim md:flex">
              {LINKS.map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => jump(id)}
                  className="transition-colors hover:text-ink"
                >
                  {label}
                </button>
              ))}
            </nav>
            <Button
              variant="primary"
              className="ml-auto"
              icon={<ArrowRight size={16} weight="bold" />}
              onClick={start}
            >
              Open the studio
            </Button>
          </div>
        </header>

        <main className="flex-1">
          <Hero onStart={start} onHow={() => jump('how')} />
          <DemoShowcase demos={demos.data} />
          <HowItWorks />
          <Capabilities />
          <ClipGallery samples={samples.data} loading={samples.isPending} go={go} />
          <Proof />

          <section
            aria-labelledby="cta-title"
            className="viewport mb-16 !rounded-3xl p-8 text-white sm:p-12"
          >
            <div className="relative z-[2] flex flex-wrap items-end justify-between gap-6">
              <div>
                <h2
                  id="cta-title"
                  className="max-w-[18ch] font-display text-4xl leading-[1.02] font-semibold tracking-tight sm:text-5xl"
                >
                  Teach it something once.
                </h2>
                <p className="mt-3 max-w-[44ch] text-white/65">
                  Pick a clip or bring your own. It will tell you what it understood before it
                  moves.
                </p>
              </div>
              <Button
                variant="primary"
                size="lg"
                icon={<ArrowRight size={20} weight="bold" />}
                onClick={start}
              >
                Open the studio
              </Button>
            </div>
          </section>
        </main>

        <footer className="border-t border-line py-6 text-xs text-ink-faint">
          Built for the Meta Global AI Developer Hackathon 2026. Runs in simulation, with SAM 3.1
          and Muse Spark.
        </footer>
      </div>
    </MotionConfig>
  )
}
