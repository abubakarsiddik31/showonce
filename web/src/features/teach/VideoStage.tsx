import { Pause, Play } from '@phosphor-icons/react'
import { memo, useCallback, useEffect, useRef, useState } from 'react'

import type { LearnResult } from '../../api/schemas'
import { formatTime, objectTone } from '../../lib/format'

interface Props {
  src: string
  learn: LearnResult | null
  time: number
  onTime: (seconds: number) => void
  seekTo: number | null
}

/** The demo video with SAM's reading drawn on top: containers, object markers and moves. */
export function VideoStage({ src, learn, time, onTime, seekTo }: Props) {
  const video = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    if (seekTo !== null && video.current) video.current.currentTime = seekTo
  }, [seekTo])

  // Report the playhead about 20 times a second while playing; the browser's own
  // timeupdate event is too coarse to move the overlay smoothly.
  useEffect(() => {
    if (!playing) return
    let frame = 0
    let last = 0
    const tick = (now: number) => {
      if (now - last > 50 && video.current) {
        last = now
        onTime(video.current.currentTime)
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [playing, onTime])

  const toggle = useCallback(() => {
    const el = video.current
    if (!el) return
    if (el.paused) void el.play()
    else el.pause()
  }, [])

  return (
    <div className="viewport">
      <div className="relative aspect-video">
        <video
          ref={video}
          src={`${src}#t=0.1`}
          muted
          playsInline
          preload="metadata"
          className="absolute inset-0 size-full object-contain"
          onPlay={() => setPlaying(true)}
          onPause={() => {
            setPlaying(false)
            if (video.current) onTime(video.current.currentTime)
          }}
          onSeeked={() => video.current && onTime(video.current.currentTime)}
          onClick={toggle}
        />
        {learn && <Overlay learn={learn} time={time} />}
      </div>
      <div className="relative z-[2] flex items-center gap-3 border-t border-white/10 px-3 py-2">
        <button
          type="button"
          onClick={toggle}
          aria-label={playing ? 'Pause demo' : 'Play demo'}
          className="grid size-8 place-items-center rounded-lg text-white transition-colors hover:bg-white/10 active:scale-95"
        >
          {playing ? <Pause size={18} weight="fill" /> : <Play size={18} weight="fill" />}
        </button>
        <span className="font-mono text-xs text-white/70 tabular-nums">{formatTime(time)}</span>
      </div>
    </div>
  )
}

const Overlay = memo(function Overlay({ learn, time }: { learn: LearnResult; time: number }) {
  const { width, height } = learn
  const unit = width / 100
  const objects = [...new Set(learn.rests.map((r) => r.object))]

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="pointer-events-none absolute inset-0 size-full"
      aria-hidden
    >
      {learn.containers.map((c) => (
        <g key={c.name}>
          <rect
            x={c.x1}
            y={c.y1}
            width={c.x2 - c.x1}
            height={c.y2 - c.y1}
            rx={unit}
            fill="rgb(255 90 31 / 0.10)"
            stroke="#ff7440"
            strokeOpacity={0.8}
            strokeWidth={unit * 0.25}
            strokeDasharray={`${unit * 1.2} ${unit * 0.8}`}
          />
          <text
            x={c.x1 + unit}
            y={c.y1 - unit * 0.8}
            fill="#ff9b75"
            fontSize={unit * 1.7}
            fontFamily="Geist Mono Variable, monospace"
          >
            {c.name}
          </text>
        </g>
      ))}
      {objects.map((name) => (
        <Marker key={name} name={name} learn={learn} time={time} unit={unit} />
      ))}
    </svg>
  )
})

function Marker({
  name,
  learn,
  time,
  unit,
}: {
  name: string
  learn: LearnResult
  time: number
  unit: number
}) {
  const tone = objectTone(name)
  const move = learn.moves.find((m) => m.object === name && time >= m.startS && time <= m.endS)
  let at: [number, number] | null = null
  if (move) {
    const p = (time - move.startS) / Math.max(move.endS - move.startS, 1e-6)
    at = [move.fromX + (move.toX - move.fromX) * p, move.fromY + (move.toY - move.fromY) * p]
  } else {
    const rests = learn.rests.filter((r) => r.object === name && r.startS <= time)
    const rest = rests.at(-1) ?? learn.rests.find((r) => r.object === name)
    if (rest) at = [rest.x, rest.y]
  }
  if (!at) return null
  return (
    <g>
      {move && (
        <line
          x1={move.fromX}
          y1={move.fromY}
          x2={move.toX}
          y2={move.toY}
          stroke={tone}
          strokeOpacity={0.7}
          strokeWidth={unit * 0.25}
          strokeDasharray={`${unit * 0.8} ${unit * 0.8}`}
        />
      )}
      <circle
        cx={at[0]}
        cy={at[1]}
        r={unit * 1.4}
        fill="none"
        stroke={tone}
        strokeWidth={unit * 0.3}
      />
      <circle cx={at[0]} cy={at[1]} r={unit * 0.35} fill={tone} />
    </g>
  )
}
