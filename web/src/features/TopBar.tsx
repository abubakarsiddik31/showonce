import { UploadSimple } from '@phosphor-icons/react'
import { motion } from 'motion/react'

import type { Sample } from '../api/schemas'
import { Button } from '../components/Button'
import { cn } from '../lib/format'

interface Props {
  samples: Sample[]
  selectedId: string | null
  onSelect: (id: string) => void
  onUpload: () => void
  health: { ok: boolean; metaKey: boolean } | undefined
  healthError: boolean
}

export function TopBar({ samples, selectedId, onSelect, onUpload, health, healthError }: Props) {
  const status = healthError
    ? { text: 'API offline', tone: 'bg-danger' }
    : health && !health.metaKey
      ? { text: 'Meta key missing', tone: 'bg-amber-400' }
      : { text: 'Connected', tone: 'bg-accent' }

  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-line py-4">
      <div className="flex items-center gap-2.5">
        <svg viewBox="0 0 32 32" className="size-7" aria-hidden>
          <rect width="32" height="32" rx="8" fill="#18181b" />
          <circle cx="11" cy="21" r="4" fill="#34d399" />
          <path
            d="M15 21h6a3 3 0 0 0 3-3v-6"
            fill="none"
            stroke="#e4e4e7"
            strokeWidth="2.4"
            strokeLinecap="round"
          />
        </svg>
        <span className="text-base font-semibold tracking-tight">ShowOnce</span>
      </div>

      <nav
        aria-label="Demo clips"
        className="order-last flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto"
      >
        {samples.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => onSelect(s.id)}
            aria-current={selectedId === s.id}
            className={cn(
              'relative shrink-0 rounded-lg px-3 py-1.5 text-sm capitalize transition-colors',
              selectedId === s.id ? 'text-ink' : 'text-ink-dim hover:text-ink',
            )}
          >
            {selectedId === s.id && (
              <motion.span
                layoutId="tab-pill"
                className="absolute inset-0 rounded-lg bg-white/8"
                transition={{ type: 'spring', stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative">{s.name}</span>
          </button>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-4">
        <span className="flex items-center gap-2 text-xs text-ink-dim" role="status">
          <span className={cn('size-1.5 rounded-full', status.tone)} aria-hidden />
          {status.text}
        </span>
        <Button variant="ghost" icon={<UploadSimple size={18} />} onClick={onUpload}>
          Your clip
        </Button>
      </div>
    </header>
  )
}
