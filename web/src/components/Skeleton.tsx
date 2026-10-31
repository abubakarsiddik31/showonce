import { cn } from '../lib/format'

export const Skeleton = ({ className }: { className?: string }) => (
  <div aria-hidden className={cn('skeleton rounded-md', className)} />
)
