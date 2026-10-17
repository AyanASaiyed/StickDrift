import type { Direction } from '../api'
import { TRAVEL_MS, type Chart, type Hand } from './chart'
import { stickDirection } from './detector'
import type { NoteState } from './judge'

// Friday Night Funkin' lane order and colors.
export const LANES: Direction[] = ['left', 'down', 'up', 'right']
const COLORS: Record<Direction, string> = {
  left: '#c24b99',
  down: '#00a8cc',
  up: '#12a150',
  right: '#e5484d',
}
const ROTATION: Record<Direction, number> = { up: 0, right: Math.PI / 2, down: Math.PI, left: -Math.PI / 2 }

const STAGE = '#14161a'
const INK = '#f2f0eb'
const MUTED = '#9aa1a9'
const RECEPTOR = '#5b626d'
const FONT = "'Atkinson Hyperlegible', system-ui, sans-serif"

// Unit arrow pointing up, centered on 0,0.
const ARROW = new Path2D('M0 -0.46 L0.44 0 L0.17 0 L0.17 0.44 L-0.17 0.44 L-0.17 0 L-0.44 0 Z')

export interface Flash {
  hand: Hand
  dir: Direction
  at: number // game ms
  text: string
}

export interface FrameState {
  now: number // game ms
  chart: Chart
  notes: NoteState[]
  sticks: { lx: number; ly: number; rx: number; ry: number } // calibrated
  flashes: Flash[]
  practice: boolean
}

function drawArrow(ctx: CanvasRenderingContext2D, x: number, y: number, size: number, dir: Direction,
                   fill: string | null, stroke: string, lineWidth: number) {
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(ROTATION[dir])
  ctx.scale(size, size)
  ctx.lineJoin = 'round'
  if (fill) {
    ctx.fillStyle = fill
    ctx.fill(ARROW)
  }
  ctx.lineWidth = lineWidth / size
  ctx.strokeStyle = stroke
  ctx.stroke(ARROW)
  ctx.restore()
}

export function layout(w: number, h: number) {
  const lane = Math.min(120, (w * 0.84) / 9)
  const size = lane * 0.84
  const groupX: Record<Hand, number> = { left: w * 0.27, right: w * 0.73 }
  const laneX = (hand: Hand, dir: Direction) => groupX[hand] + (LANES.indexOf(dir) - 1.5) * lane
  const receptorY = Math.max(h * 0.24, 130)
  return { lane, size, groupX, laneX, receptorY, spawnY: h + size }
}

export function drawFrame(ctx: CanvasRenderingContext2D, w: number, h: number, s: FrameState) {
  const { size, groupX, laneX, receptorY, spawnY } = layout(w, h)
  ctx.fillStyle = STAGE
  ctx.fillRect(0, 0, w, h)

  // Group labels with a live stick dot.
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  for (const hand of ['left', 'right'] as Hand[]) {
    const [x, y] = hand === 'left' ? [s.sticks.lx, s.sticks.ly] : [s.sticks.rx, s.sticks.ry]
    ctx.font = `700 ${Math.round(size * 0.24)}px ${FONT}`
    ctx.fillStyle = MUTED
    const labelY = receptorY - size * 1.05
    ctx.fillText(hand === 'left' ? 'LEFT STICK' : 'RIGHT STICK', groupX[hand], labelY)
    const r = size * 0.16
    const dotX = groupX[hand] + size * 1.25
    ctx.strokeStyle = RECEPTOR
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(dotX, labelY, r, 0, Math.PI * 2)
    ctx.stroke()
    ctx.fillStyle = INK
    ctx.beginPath()
    ctx.arc(dotX + Math.max(-1, Math.min(1, x)) * r, labelY + Math.max(-1, Math.min(1, y)) * r, r * 0.35, 0, Math.PI * 2)
    ctx.fill()
  }

  // Receptors: outlined arrows; the stick's current direction lights up.
  const held: Record<Hand, Direction | null> = {
    left: stickDirection(s.sticks.lx, s.sticks.ly),
    right: stickDirection(s.sticks.rx, s.sticks.ry),
  }
  for (const hand of ['left', 'right'] as Hand[]) {
    for (const dir of LANES) {
      const flash = s.flashes.find((f) => f.hand === hand && f.dir === dir && s.now - f.at < 220)
      const lit = flash || held[hand] === dir
      drawArrow(ctx, laneX(hand, dir), receptorY, size, dir, lit ? COLORS[dir] : '#1e2127',
        lit ? INK : RECEPTOR, 4)
    }
  }

  // Notes rise from the bottom and reach the receptors at target time.
  for (const n of s.notes) {
    const { spawn_ms, target_ms } = n.trial
    if (s.now < spawn_ms || n.outcome === 'hit') continue
    const progress = (target_ms - s.now) / TRAVEL_MS
    const y = receptorY + progress * (spawnY - receptorY)
    if (y < -size) continue
    const x = laneX(n.note.hand, n.note.dir)
    if (n.outcome === 'pending') {
      drawArrow(ctx, x, y, size, n.note.dir, COLORS[n.note.dir], INK, 3)
    } else {
      // Missed or wrong: fade out quietly, no penalty message.
      ctx.globalAlpha = Math.max(0, 0.35 - (s.now - target_ms) / 3000)
      drawArrow(ctx, x, y, size, n.note.dir, MUTED, MUTED, 2)
      ctx.globalAlpha = 1
    }
  }

  // Encouragement above each group for hits only.
  for (const f of s.flashes) {
    const age = s.now - f.at
    if (age > 700 || !f.text) continue
    ctx.globalAlpha = 1 - age / 700
    ctx.fillStyle = INK
    ctx.font = `700 ${Math.round(size * 0.42)}px ${FONT}`
    ctx.fillText(f.text, groupX[f.hand], receptorY + size * 1.15 - age * 0.04)
    ctx.globalAlpha = 1
  }

  // Block banner.
  const banner = s.chart.banners.find((b) => s.now >= b.from_ms && s.now < b.to_ms)
  if (banner) {
    ctx.font = `700 ${Math.round(Math.min(w * 0.06, 44))}px ${FONT}`
    const tw = ctx.measureText(banner.text).width
    ctx.fillStyle = 'rgba(20,22,26,0.85)'
    ctx.fillRect(w / 2 - tw / 2 - 28, h * 0.58 - 40, tw + 56, 80)
    ctx.fillStyle = INK
    ctx.fillText(banner.text, w / 2, h * 0.58)
  }

  // Progress.
  const p = Math.max(0, Math.min(1, s.now / s.chart.end_ms))
  ctx.fillStyle = '#262a31'
  ctx.fillRect(0, h - 6, w, 6)
  ctx.fillStyle = s.practice ? MUTED : '#6fb3e0'
  ctx.fillRect(0, h - 6, w * p, 6)
}
