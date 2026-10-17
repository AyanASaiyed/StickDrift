// All requests go through the Vite proxy (/api -> FastAPI) so the HttpOnly
// session cookie is same-origin.
const API = '/api'

export type Hand = 'left' | 'right' | 'unknown'
export type Direction = 'up' | 'down' | 'left' | 'right'
export type Placement = 'hands' | 'table' | 'lap' | 'other'
export type Role = 'senior' | 'caregiver'

// ---- game record shapes (produced by the arrow game) ----

export interface TrialRecord {
  trial_id: number
  block: 'left' | 'right' | 'both'
  direction_l: Direction | null
  direction_r: Direction | null
  spawn_ms: number
  target_ms: number
}

export interface ResponseRecord {
  trial_id: number
  hand: 'left' | 'right'
  outcome: 'hit' | 'wrong_direction' | 'missed' | 'invalid'
  detected_dir: Direction | null
  move_ms: number | null
  offset_ms: number | null
}

/** [epoch_ms, game_ms, lx, ly, rx, ry, connected] */
export type SampleRecord = [number, number, number, number, number, number, boolean]

export interface SessionComplete {
  status: 'completed' | 'abandoned'
  trials: TrialRecord[]
  responses: ResponseRecord[]
  samples: SampleRecord[]
  stray_moves: number
  disconnects: number
}

// ---- account + data shapes ----

export interface Me {
  role: Role
  account_id: string
  username: string
  display_name: string
  dominant_hand: Hand | null
}

export interface SessionSummary {
  session_id: string
  started_at: string
  completed_at: string | null
  status: 'completed' | 'abandoned' | 'in_progress'
  quality: 'good' | 'flagged' | 'invalid' | null
  mode: string
  protocol_version: string
  is_synthetic: boolean
  left_median_latency_ms: number | null
  right_median_latency_ms: number | null
  left_correct: number | null
  left_valid: number | null
  right_correct: number | null
  right_valid: number | null
  both_correct: number | null
  both_valid: number | null
  enjoyment: number | null
}

export interface Review {
  flagged: boolean
  reasons: string[]
}

export type Risk = 'none' | 'watch' | 'check'
export type MeasureKey =
  | 'left_latency'
  | 'right_latency'
  | 'left_accuracy'
  | 'right_accuracy'
  | 'both_accuracy'
  | 'lr_gap'
  | 'enjoyment'

export interface Finding {
  key: MeasureKey
  label: string
  hand: 'left' | 'right' | 'both' | null
  kind: 'latency' | 'accuracy' | 'gap' | 'enjoyment'
  baseline: number
  latest: number
  change: number
  baseline_text: string
  latest_text: string
  change_text: string
  direction: 'worse' | 'better' | 'steady'
  flagged: boolean
  persistent: boolean
  flagged_session_ids: string[]
  text: string
}

export interface Concern {
  id: string
  title: string
  level: 'watch' | 'check'
  summary: string
  evidence: string[]
  possible_contributors: string[]
  recommended_checks: string[]
  references: string[]
  measurements: MeasureKey[]
}

export interface Insights {
  status: 'ok' | 'insufficient'
  risk: Risk
  summary: string
  disclaimer: string
  synthetic: boolean
  usable_sessions: number
  baseline_sessions: number
  recent_session_ids: string[]
  findings: Finding[]
  concerns: Concern[]
}

export interface ResidentRow {
  participant_id: string
  username: string | null
  display_name: string
  dominant_hand: Hand
  session_count: number
  last_played_at: string | null
  review: Review
  risk: Risk
  concerns: Pick<Concern, 'id' | 'title' | 'level'>[]
  trend_left_ms: (number | null)[]
  trend_right_ms: (number | null)[]
}

export interface ResidentDetail {
  participant_id: string
  username: string | null
  display_name: string
  dominant_hand: Hand
  review: Review
  insights: Insights
  sessions: SessionSummary[]
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
}

export interface AssistantAnswer {
  answer: string
  source: 'gemini' | 'rules'
  grounded: boolean
  unverified_numbers: string[]
  note: string | null
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export interface GardenRecording {
  session_id: string
  source_group: string | null
  sample_count: number
  level_count: number
  started_at: string
  status: string
  is_synthetic: boolean
}

export interface GardenSecond {
  bucket: string
  activity: 'target_reach' | 'target_tracking' | 'bilateral_control' | null
  sample_count: number
  left_magnitude: number | null
  right_magnitude: number | null
  disconnected_count: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, "Can't reach the Stick Drift server. Is the backend running?")
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail =
      typeof body?.detail === 'string'
        ? body.detail
        : res.status >= 500
          ? 'The server had a problem. Try again in a moment.'
          : 'Please check what you entered and try again.'
    throw new ApiError(res.status, detail)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export interface GameSave {
  protocol_version: string
  input_reader: 'gamepad_api' | 'keyboard'
  connection: 'usb' | 'bluetooth' | 'simulated' | 'unknown'
  placement: Placement
  status: 'completed' | 'abandoned'
  quality: 'good' | 'flagged' | 'invalid'
  left_hits: number
  left_notes: number
  right_hits: number
  right_notes: number
  both_hits: number
  both_trials: number
  left_median_offset_ms: number | null
  right_median_offset_ms: number | null
  stray_moves: number
  enjoyment?: number | null
}

const median = (xs: number[]): number | null =>
  xs.length === 0 ? null : [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)]

/** Summarize the arrow game into the counts the backend stores. */
export function summarizeGame(result: SessionComplete): Omit<GameSave, 'protocol_version' | 'input_reader' | 'connection' | 'placement' | 'quality'> {
  const blockOf = new Map(result.trials.map((t) => [t.trial_id, t.block]))
  const inBlock = (hand: 'left' | 'right') =>
    result.responses.filter((r) => r.hand === hand && blockOf.get(r.trial_id) === hand)
  const left = inBlock('left')
  const right = inBlock('right')
  const bothTrials = result.trials.filter((t) => t.block === 'both')
  const bothHits = bothTrials.filter((t) => {
    const rs = result.responses.filter((r) => r.trial_id === t.trial_id)
    return rs.length > 0 && rs.every((r) => r.outcome === 'hit')
  }).length
  const offsets = (rs: ResponseRecord[]) =>
    median(rs.filter((r) => r.outcome === 'hit' && r.offset_ms !== null).map((r) => r.offset_ms as number))
  return {
    status: result.status,
    left_hits: left.filter((r) => r.outcome === 'hit').length,
    left_notes: left.length,
    right_hits: right.filter((r) => r.outcome === 'hit').length,
    right_notes: right.length,
    both_hits: bothHits,
    both_trials: bothTrials.length,
    left_median_offset_ms: offsets(left),
    right_median_offset_ms: offsets(right),
    stray_moves: result.stray_moves,
  }
}

export const api = {
  me: () => request<Me>('/auth/me'),
  loginSenior: (username: string, password: string) =>
    post<Me>('/auth/senior/login', { username, password }),
  signupSenior: (username: string, password: string, dominant_hand: Hand) =>
    post<Me>('/auth/senior/signup', { username, password, dominant_hand }),
  loginCaregiver: (username: string, password: string) =>
    post<Me>('/auth/caregiver/login', { username, password }),
  logout: () => post<void>('/auth/logout'),

  mySessions: () => request<SessionSummary[]>('/me/sessions'),
  saveGame: (body: GameSave) => post<{ session_id: string; status: string }>('/me/games', body),
  rateGame: (sessionId: string, enjoyment: number) =>
    request<void>(`/me/games/${sessionId}/rating`, {
      method: 'PATCH',
      body: JSON.stringify({ enjoyment }),
    }),

  gardenRecordings: () => request<GardenRecording[]>('/garden/recordings'),
  gardenTimeline: (sessionId: string) =>
    request<GardenSecond[]>(`/sessions/${sessionId}/garden-timeline`),
  caregiverResidents: () => request<ResidentRow[]>('/caregiver/residents'),
  caregiverResident: (id: string) => request<ResidentDetail>(`/caregiver/residents/${id}`),
  askAssistant: (question: string, history: ChatTurn[], participantId?: string) =>
    post<AssistantAnswer>('/caregiver/assistant', { question, history, participant_id: participantId ?? null }),
}
