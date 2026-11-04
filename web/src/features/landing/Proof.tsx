/** What has been measured, and on what, stated plainly. */
const FACTS: Array<[string, string]> = [
  ['6 of 6', 'demo clips replayed on a shuffled table, every step verified'],
  ['3 real', 'stock-footage clips among them: fruit, sugar, carrot'],
  ['within 3 mm', 'SAM position error against simulator truth'],
  ['10', 'actions, from put-in to pour, stir and cut'],
]

export function Proof() {
  return (
    <section aria-labelledby="proof-title" className="border-t border-line-strong py-14">
      <h2 id="proof-title" className="font-mono text-xs tracking-wide text-ink-faint uppercase">
        What has been measured
      </h2>
      <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-10 lg:grid-cols-4">
        {FACTS.map(([value, label]) => (
          <div key={label}>
            <dd className="font-display text-5xl leading-none font-semibold tracking-tight">
              {value}
            </dd>
            <dt className="mt-3 max-w-[24ch] text-sm text-ink-dim">{label}</dt>
          </div>
        ))}
      </dl>
      <p className="mt-8 max-w-[70ch] text-sm leading-relaxed text-ink-faint">
        Measured on real stock footage and AI-generated clips in a MuJoCo simulator, checked against
        simulator ground truth. Real phone footage and a real arm are not tested yet, and nothing
        here claims otherwise.
      </p>
    </section>
  )
}
