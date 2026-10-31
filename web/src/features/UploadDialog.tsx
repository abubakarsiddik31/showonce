import { UploadSimple } from '@phosphor-icons/react'
import { useEffect, useId, useRef, useState } from 'react'

import { Button } from '../components/Button'
import { parseLines } from '../lib/parse'

export interface UploadSpec {
  file: File
  objects: Record<string, string>
  containers: Record<string, string>
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
  const [objects, setObjects] = useState('')
  const [containers, setContainers] = useState('')
  const parsed = parseLines(objects)
  const valid = file !== null && Object.keys(parsed).length > 0

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
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-2xl border border-line-strong bg-raised p-0 text-ink backdrop:bg-black/60 backdrop:backdrop-blur-sm"
    >
      <form
        className="flex flex-col gap-5 p-6"
        onSubmit={(e) => {
          e.preventDefault()
          if (file && valid) onSubmit({ file, objects: parsed, containers: parseLines(containers) })
        }}
      >
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Teach it your own clip</h2>
          <p className="mt-1 text-sm leading-relaxed text-ink-dim">
            Use an overhead clip of one tabletop task. Name what to track so SAM knows what to look
            for.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor={`${id}-file`} className="text-sm font-medium">
            Video
          </label>
          <input
            id={`${id}-file`}
            type="file"
            accept="video/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className={fieldClass}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor={`${id}-objects`} className="text-sm font-medium">
            Objects to move
          </label>
          <textarea
            id={`${id}-objects`}
            rows={3}
            value={objects}
            onChange={(e) => setObjects(e.target.value)}
            placeholder={'red mug\nblue mug: blue ceramic mug'}
            className={fieldClass}
          />
          <p className="text-xs text-ink-faint">
            One per line. Optional text after a colon is what SAM searches for.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor={`${id}-containers`} className="text-sm font-medium">
            Containers
          </label>
          <textarea
            id={`${id}-containers`}
            rows={2}
            value={containers}
            onChange={(e) => setContainers(e.target.value)}
            placeholder="tray: gray tray"
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
            disabled={!valid}
            icon={<UploadSimple size={18} />}
          >
            Learn from clip
          </Button>
        </div>
      </form>
    </dialog>
  )
}
