// All requests go through the Vite proxy (/api -> FastAPI) so the HttpOnly
// session cookie is same-origin.
const API = '/api'

export type Hand = 'left' | 'right' | 'unknown'
export type Role = 'senior' | 'caregiver'

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
  garden_visits?: number
  garden_judged?: number
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

export type PatternKey = 'parkinson' | 'stroke' | 'essential_tremor'
export type PatternScores = Record<PatternKey, number | null>

export interface TcnLevel {
  level: string
  completed: boolean
  scores: PatternScores
  stretches?: { left: number; right: number }
  duration_s?: number
  error?: string
}

export interface TcnResult {
  scores: PatternScores
  levels: TcnLevel[]
  meaning: string
  is_synthetic: boolean
}

export interface HandLive {
  reaction_s: number | null
  reach_s: number | null
  peak_speed: number | null
  reach_size: number | null
  apples_reached: number | null
  apples_total: number | null
  speed_change_pct: number | null
  tracking_error: number | null
  on_target: number | null
  shake: number | null
  shake_hz: number | null
}

export interface ReachTrial {
  trial: number
  left?: { reaction_s: number | null; reach_s: number | null; peak_speed: number; reach_size: number | null; reached: boolean }
  right?: { reaction_s: number | null; reach_s: number | null; peak_speed: number; reach_size: number | null; reached: boolean }
}

export interface LiveMetrics {
  hands: { left: HandLive; right: HandLive }
  left_right_difference_pct: Partial<Record<keyof HandLive, number>>
  reach_trials: ReachTrial[]
  tracking: Record<string, Record<string, { tracking_error: number; on_target: number; shake: number | null }>>
}

export interface GardenSession {
  session_id: string
  started_at: string
  status: string
  is_synthetic: boolean
  levels_completed: number | null
  tcn: TcnResult | null
  live: LiveMetrics | null
}

export interface ResidentDetail {
  participant_id: string
  username: string | null
  display_name: string
  dominant_hand: Hand
  review: Review
  insights: Insights
  sessions: SessionSummary[]
  garden_sessions: GardenSession[]
}

export type LiveStatus =
  | 'starting'
  | 'waiting'
  | 'ready'
  | 'playing'
  | 'paused'
  | 'saving'
  | 'scoring'
  | 'finished'
  | 'failed'
  | 'stopped'
  | 'lost'
  | 'ended'

export interface LiveBrief {
  live_id: string
  participant_id: string
  name: string
  status: LiveStatus
  level: string | null
  levels: string[]
  levels_done: string[]
  synthetic: boolean
  started_at: string
  elapsed_s: number
  tcn_scores: PatternScores | null
  db_session_id: string | null
  error: string | null
}

/** [seq, level, t, trial, phase, lx, ly, rx, ry, tlx, tly, trx, try, reached_l, reached_r] */
export type LiveSample = [
  number, string, number, number | null, string,
  number, number, number, number,
  number | null, number | null, number | null, number | null,
  number, number,
]

export interface LiveSnapshot extends LiveBrief {
  trial: number | null
  phase: string | null
  seq: number
  samples: LiveSample[]
  metrics: LiveMetrics
  result: TcnResult | null
}

export interface GardenStatus {
  active: boolean
  status: LiveStatus | null
  level: string | null
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

export const api = {
  me: () => request<Me>('/auth/me'),
  loginSenior: (username: string, password: string) =>
    post<Me>('/auth/senior/login', { username, password }),
  signupSenior: (username: string, password: string, dominant_hand: Hand) =>
    post<Me>('/auth/senior/signup', { username, password, dominant_hand }),
  signupCaregiver: (username: string, password: string, display_name: string, invite_code: string) =>
    post<Me>('/auth/caregiver/signup', { username, password, display_name, invite_code }),
  loginCaregiver: (username: string, password: string) =>
    post<Me>('/auth/caregiver/login', { username, password }),
  logout: () => post<void>('/auth/logout'),

  myGarden: () => request<GardenStatus>('/me/garden'),
  launchGarden: (keyboard: boolean) => post<GardenStatus>('/me/garden/launch', { keyboard }),

  gardenRecordings: () => request<GardenRecording[]>('/garden/recordings'),
  gardenTimeline: (sessionId: string) =>
    request<GardenSecond[]>(`/sessions/${sessionId}/garden-timeline`),
  caregiverResidents: () => request<ResidentRow[]>('/caregiver/residents'),
  caregiverResident: (id: string) => request<ResidentDetail>(`/caregiver/residents/${id}`),
  caregiverLive: () => request<LiveBrief[]>('/caregiver/live'),
  caregiverLiveSnapshot: (id: string, since: number) =>
    request<LiveSnapshot>(`/caregiver/live/${id}?since=${since}`),
  askAssistant: (question: string, history: ChatTurn[], participantId?: string) =>
    post<AssistantAnswer>('/caregiver/assistant', { question, history, participant_id: participantId ?? null }),
}
