import { UploadSimple } from '@phosphor-icons/react'
import type { ReactNode } from 'react'

import { Button } from '../components/Button'
import { Logo } from '../components/Logo'
import { cn } from '../lib/format'

interface Props {
  onUpload: () => void
  health: { ok: boolean; metaKey: boolean } | undefined
  healthError: boolean
  /** The three-stage progress, shown in the middle on wide screens. */
  progress?: ReactNode
  /** The clip picker. */
  clips?: ReactNode
}

export function TopBar({ onUpload, health, healthError, progress, clips }: Props) {
  const status = healthError
    ? { text: 'API offline', tone: 'bg-danger' }
    : health && !health.metaKey
      ? { text: 'Meta key missing', tone: 'bg-accent' }
      : { text: 'Connected', tone: 'bg-ok' }

  return (
    <header className="sticky top-0 z-20 -mx-4 border-b border-line bg-canvas/85 px-4 backdrop-blur sm:-mx-8 sm:px-8">
      <div className="flex h-16 items-center gap-4">
        <a href="#/" className="flex items-center gap-2.5 rounded-lg" aria-label="ShowOnce home">
          <Logo />
          <span className="hidden font-display text-xl font-semibold tracking-tight sm:inline">
            ShowOnce
          </span>
        </a>
        <div className="hidden flex-1 justify-center lg:flex">{progress}</div>
        <div className="ml-auto flex items-center gap-3">
          {clips}
          <Button variant="ghost" icon={<UploadSimple size={18} />} onClick={onUpload}>
            <span className="hidden sm:inline">Your clip</span>
          </Button>
          <span className="hidden items-center gap-2 text-xs text-ink-dim md:flex" role="status">
            <span className={cn('size-1.5 rounded-full', status.tone)} aria-hidden />
            {status.text}
          </span>
        </div>
      </div>
      {progress && <div className="flex justify-center pb-3 lg:hidden">{progress}</div>}
    </header>
  )
}
