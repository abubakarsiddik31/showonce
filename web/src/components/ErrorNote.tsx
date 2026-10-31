import { WarningCircle } from '@phosphor-icons/react'

export function ErrorNote({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="flex items-start gap-2 border-l-2 border-danger bg-danger/5 py-2 pr-2 pl-3 text-sm text-ink-dim"
    >
      <WarningCircle size={18} className="mt-px shrink-0 text-danger" aria-hidden />
      <span className="break-words">{message}</span>
    </p>
  )
}
