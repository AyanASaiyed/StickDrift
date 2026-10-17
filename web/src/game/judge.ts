import type { Direction, ResponseRecord, TrialRecord } from '../api'
import { EARLY_MS, LATE_MS, type Chart, type ChartTrial, type Hand, type Note } from './chart'

export type NoteOutcome = 'pending' | 'hit' | 'wrong_direction' | 'missed' | 'invalid'

export interface NoteState {
  trial: ChartTrial
  note: Note
  outcome: NoteOutcome
  windowOpen: boolean
  offCenterAtOpen: boolean
  detected: Direction | null
  move_ms: number | null
  offset_ms: number | null
}

export interface Judgement {
  hand: Hand
  dir: Direction
  outcome: 'hit' | 'wrong_direction'
  offset_ms: number
}

/** Matches stick movements to arrows. All times are game-clock ms. */
export class Judge {
  readonly notes: NoteState[]
  strayMoves = 0

  constructor(chart: Chart) {
    this.notes = chart.trials.flatMap((trial) =>
      trial.notes.map(
        (note): NoteState => ({
          trial,
          note,
          outcome: 'pending',
          windowOpen: false,
          offCenterAtOpen: false,
          detected: null,
          move_ms: null,
          offset_ms: null,
        }),
      ),
    )
  }

  /** Open response windows that start at or before `now`; remember if the stick was off-center. */
  openWindows(now: number, armed: Record<Hand, boolean>) {
    for (const n of this.notes) {
      if (!n.windowOpen && now >= n.trial.target_ms - EARLY_MS) {
        n.windowOpen = true
        n.offCenterAtOpen = !armed[n.note.hand]
      }
    }
  }

  /** The first movement inside an arrow's window decides it: right direction = hit. */
  onMove(hand: Hand, dir: Direction, t: number): Judgement | null {
    const n = this.notes.find(
      (s) =>
        s.outcome === 'pending' &&
        s.note.hand === hand &&
        t >= s.trial.target_ms - EARLY_MS &&
        t <= s.trial.target_ms + LATE_MS,
    )
    if (!n) {
      this.strayMoves++
      return null
    }
    n.detected = dir
    n.move_ms = t
    n.offset_ms = t - n.trial.target_ms
    n.outcome = dir === n.note.dir ? 'hit' : 'wrong_direction'
    return { hand, dir, outcome: n.outcome, offset_ms: n.offset_ms }
  }

  /** Close windows that ended before `now`. Unanswered arrows are missed, or invalid if the stick started off-center. */
  closeWindows(now: number) {
    for (const n of this.notes) {
      if (n.outcome === 'pending' && now > n.trial.target_ms + LATE_MS) {
        n.outcome = n.offCenterAtOpen ? 'invalid' : 'missed'
      }
    }
  }

  get done(): boolean {
    return this.notes.every((n) => n.outcome !== 'pending')
  }

  trialRecords(): TrialRecord[] {
    const trials = new Map<number, ChartTrial>()
    for (const n of this.notes) trials.set(n.trial.trial_id, n.trial)
    return [...trials.values()].map((t) => ({
      trial_id: t.trial_id,
      block: t.block === 'practice' ? 'left' : t.block,
      direction_l: t.notes.find((n) => n.hand === 'left')?.dir ?? null,
      direction_r: t.notes.find((n) => n.hand === 'right')?.dir ?? null,
      spawn_ms: t.spawn_ms,
      target_ms: t.target_ms,
    }))
  }

  /** Only notes whose window has closed or that were answered (an abandoned run stores what was played). */
  responseRecords(): ResponseRecord[] {
    return this.notes
      .filter((n) => n.outcome !== 'pending')
      .map((n) => ({
        trial_id: n.trial.trial_id,
        hand: n.note.hand,
        outcome: n.outcome as ResponseRecord['outcome'],
        detected_dir: n.detected,
        move_ms: n.move_ms,
        offset_ms: n.offset_ms,
      }))
  }
}
