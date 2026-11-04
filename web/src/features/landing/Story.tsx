const POINTS: Array<[string, string]> = [
  [
    'Every home is different',
    'The dishes go in another rack, the toys in another bin. A robot cannot ship with every household job already programmed.',
  ],
  [
    'People teach by showing',
    'A parent shows a child once. Nobody hands over a dataset of a thousand demonstrations or writes code.',
  ],
  [
    'So we teach the task',
    'ShowOnce learns what moved where and why, not the motion of a hand. That is what carries over to a new table.',
  ],
]

/** Why this exists: the household idea, in three beats. */
export function Story() {
  return (
    <section aria-labelledby="why-title" className="border-t border-line-strong py-14">
      <h2 id="why-title" className="font-mono text-xs tracking-wide text-ink-faint uppercase">
        Why
      </h2>
      <p className="mt-4 max-w-[24ch] font-display text-4xl leading-[1.02] font-semibold tracking-tight">
        A robot for a home has to learn like a person does.
      </p>
      <ul className="mt-10 grid gap-8 md:grid-cols-3">
        {POINTS.map(([title, body]) => (
          <li key={title} className="flex flex-col gap-2">
            <h3 className="font-display text-xl font-semibold tracking-tight">{title}</h3>
            <p className="max-w-[38ch] text-sm leading-relaxed text-ink-dim">{body}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
