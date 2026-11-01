import { UploadSimple } from '@phosphor-icons/react'

import { Button } from '../components/Button'
import { cn } from '../lib/format'

interface Props {
  onUpload: () => void
  health: { ok: boolean; metaKey: boolean } | undefined
  healthError: boolean
}

export function TopBar({ onUpload, health, healthError }: Props) {
  const status = healthError
    ? { text: 'API offline', tone: 'bg-danger' }
    : health && !health.metaKey
      ? { text: 'Meta key missing', tone: 'bg-accent' }
      : { text: 'Connected', tone: 'bg-ok' }

  return (
    <header className="flex items-center gap-4 py-5">
      <div className="flex items-center gap-2.5">
        <svg viewBox="0 0 32 32" className="size-8" aria-hidden>
          <rect width="32" height="32" rx="8" fill="#11151a" />
          <circle cx="11" cy="21" r="4" fill="#ff5a1f" />
          <path
            d="M15 21h6a3 3 0 0 0 3-3v-6"
            fill="none"
            stroke="#e6eaed"
            strokeWidth="2.4"
            strokeLinecap="round"
          />
        </svg>
        <span className="font-display text-xl font-semibold tracking-tight">ShowOnce</span>
      </div>
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
