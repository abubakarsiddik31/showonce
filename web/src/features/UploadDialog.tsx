import { UploadSimple } from '@phosphor-icons/react'
import { useEffect, useId, useRef, useState } from 'react'

import { Button } from '../components/Button'

export interface UploadSpec {
  file: File
}

interface Props {
  open: boolean
  onClose: () => void
  onSubmit: (spec: UploadSpec) => void
}

const fieldClass =
  'w-full rounded-lg border border-line bg-sunken px-3 py-2 text-sm text-ink placeholder:text-ink-faint hover:border-line-strong'

export function UploadDialog({ open, onClose, onSubmit }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  const [file, setFile] = useState<File | null>(null)

  // The native dialog gives focus trapping and Escape for free.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className="m-auto w-[min(30rem,calc(100vw-2rem))] rounded-2xl border border-line-strong bg-raised p-0 text-ink backdrop:bg-black/60 backdrop:backdrop-blur-sm"
    >
      <form
        className="flex flex-col gap-5 p-6"
        onSubmit={(e) => {
          e.preventDefault()
          if (file) onSubmit({ file })
        }}
      >
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Teach it your own clip</h2>
          <p className="mt-1 text-sm leading-relaxed text-ink-dim">
            Film one task from above, with the camera still, and upload it. You do not need to name
            anything: the robot looks at the table itself, tells you what it understood, and you
            correct it in words.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor={`${id}-file`} className="text-sm font-medium">
            Video (mp4)
          </label>
          <input
            id={`${id}-file`}
            type="file"
            accept="video/mp4,video/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className={fieldClass}
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="quiet" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            disabled={file === null}
            icon={<UploadSimple size={18} />}
          >
            Watch my clip
          </Button>
        </div>
      </form>
    </dialog>
  )
}
