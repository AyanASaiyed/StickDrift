import type { Direction } from '../api'

/**
 * Fixed assessment chart, Friday Night Funkin' style: arrows rise from the
 * bottom of the screen and the player moves the matching stick when an arrow
 * reaches the target row. The chart is identical every session so results
 * stay comparable. Changing anything here requires a new PROTOCOL_VERSION.
 */
export const PROTOCOL_VERSION = 'assess-v1'

export const TRAVEL_MS = 2600 // arrow appears -> reaches the target row
export const SPACING_MS = 1700 // between consecutive targets
export const LEAD_IN_MS = 3000 // banner before the first arrow appears
export const BANNER_MS = 2500 // "Right stick only" etc. between blocks
export const EARLY_MS = 450 // a move this long before the target still counts
export const LATE_MS = 650 // ...and this long after

export type Hand = 'left' | 'right'
export type Block = 'practice' | 'left' | 'right' | 'both'

export interface Note {
  hand: Hand
  dir: Direction
}

export interface ChartTrial {
  trial_id: number
  block: Block
  notes: Note[]
  spawn_ms: number
  target_ms: number
}

export interface Banner {
  from_ms: number
  to_ms: number
  text: string
}

export interface Chart {
  trials: ChartTrial[]
  banners: Banner[]
  end_ms: number
}

const DIRS: Direction[] = ['up', 'down', 'left', 'right']
const OPPOSITE: Record<Direction, Direction> = { up: 'down', down: 'up', left: 'right', right: 'left' }

/** Small deterministic PRNG so the "shuffled" order is the same every session. */
function mulberry32(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function shuffled<T>(items: T[], seed: number): T[] {
  const rand = mulberry32(seed)
  const out = [...items]
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

function build(blocks: { block: Block; banner: string; notes: Note[][] }[]): Chart {
  const trials: ChartTrial[] = []
  const banners: Banner[] = []
  let t = 0
  for (const { block, banner, notes } of blocks) {
    const bannerEnd = t + (trials.length === 0 ? LEAD_IN_MS : BANNER_MS)
    banners.push({ from_ms: t, to_ms: bannerEnd, text: banner })
    let target = bannerEnd + TRAVEL_MS
    for (const n of notes) {
      trials.push({ trial_id: trials.length, block, notes: n, spawn_ms: target - TRAVEL_MS, target_ms: target })
      target += SPACING_MS
    }
    t = target - SPACING_MS + LATE_MS
  }
  return { trials, banners, end_ms: t + 1000 }
}

const rep = <T,>(items: T[], n: number) => Array.from({ length: n }, () => items).flat()

export function practiceChart(): Chart {
  const L = (dir: Direction): Note[] => [{ hand: 'left', dir }]
  const R = (dir: Direction): Note[] => [{ hand: 'right', dir }]
  return build([
    {
      block: 'practice',
      banner: 'Practice: not scored',
      notes: [L('up'), R('down'), L('right'), R('left'), L('down'), R('up')],
    },
  ])
}

export function assessmentChart(): Chart {
  // Left and right blocks: each direction 3 times.
  const left = shuffled(rep(DIRS, 3), 11).map((dir): Note[] => [{ hand: 'left', dir }])
  const right = shuffled(rep(DIRS, 3), 23).map((dir): Note[] => [{ hand: 'right', dir }])
  // Both block: 8 same-direction pairs (each direction twice) and 4 opposite
  // pairs, so each hand still gets each direction exactly 3 times.
  const pairs: [Direction, Direction][] = [
    ...rep(DIRS, 2).map((d): [Direction, Direction] => [d, d]),
    ...DIRS.map((d): [Direction, Direction] => [d, OPPOSITE[d]]),
  ]
  const both = shuffled(pairs, 37).map(([l, r]): Note[] => [
    { hand: 'left', dir: l },
    { hand: 'right', dir: r },
  ])
  return build([
    { block: 'left', banner: 'Left stick only', notes: left },
    { block: 'right', banner: 'Right stick only', notes: right },
    { block: 'both', banner: 'Both sticks together', notes: both },
  ])
}
