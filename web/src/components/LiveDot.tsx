import { memo } from 'react'
import { motion } from 'motion/react'

/** A breathing status dot. Isolated and memoised so the loop never re-renders its parent. */
export const LiveDot = memo(function LiveDot({ tone = 'accent' }: { tone?: 'accent' | 'warn' }) {
  const color = tone === 'accent' ? 'bg-accent' : 'bg-amber-400'
  return (
    <span className="relative flex size-2" aria-hidden>
      <motion.span
        className={`absolute inset-0 rounded-full ${color}`}
        animate={{ scale: [1, 2.2], opacity: [0.5, 0] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'easeOut' }}
      />
      <span className={`relative size-2 rounded-full ${color}`} />
    </span>
  )
})
