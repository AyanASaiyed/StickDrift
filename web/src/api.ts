const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Hand = 'left' | 'right' | 'unknown'
export type Activity = 'target_reach' | 'target_tracking' | 'bilateral_control'

export interface Participant {
  participant_id: string
  alias: string
  dominant_hand: Hand
  created_at: string
  session_count: number
  last_played_at: string | null
}

export interface SessionRow {
  session_id: string
  mode: 'assessment' | 'free_play'
  protocol_version: string
  status: 'in_progress' | 'completed' | 'abandoned'
  quality: 'good' | 'flagged' | 'invalid' | null
  is_synthetic: boolean
  connection: string | null
  started_at: string
  completed_at: string | null
  left_median_latency_ms: number | null
  right_median_latency_ms: number | null
  left_correct: number | null
  left_valid: number | null
  right_correct: number | null
  right_valid: number | null
  both_correct: number | null
  both_valid: number | null
  enjoyment: number | null
  metrics: Record<string, unknown> | null
}

export interface StartSessionInput {
  mode?: 'assessment' | 'free_play'
  protocol_version?: string
  controller_id?: string | null
  connection?: 'usb' | 'bluetooth' | 'simulated' | 'unknown'
  placement?: 'hands' | 'table' | 'lap' | 'other'
  is_synthetic?: boolean
}

export interface StartedSession {
  session_id: string
  started_at: string
}

export interface JoystickSample {
  seq: number
  /** Monotonic milliseconds elapsed since this session began. */
  t_ms: number
  lx: number
  ly: number
  rx: number
  ry: number
  connected: boolean
  activity?: Activity | null
  trial_id?: number | null
  target_x?: number | null
  target_y?: number | null
  cursor_x?: number | null
  cursor_y?: number | null
}

export interface TrialResult {
  trial_id: number
  activity: Activity
  block: 'practice' | 'left' | 'right' | 'both'
  hand: 'left' | 'right' | 'both'
  direction_l?: 'up' | 'down' | 'left' | 'right' | null
  direction_r?: 'up' | 'down' | 'left' | 'right' | null
  cue_onset_ms: number
  deadline_ms: number
  details?: Record<string, unknown>
  outcome: 'correct' | 'wrong_direction' | 'omission' | 'false_start' | 'invalid'
  detected_l?: string | null
  detected_r?: string | null
  cross_l_ms?: number | null
  cross_r_ms?: number | null
  latency_ms?: number | null
  metrics?: Record<string, unknown>
  code_version?: string
}

export interface SessionEvent {
  event_id?: string
  t_ms: number
  event_type: string
  payload?: Record<string, unknown>
}

export interface FinishSessionInput {
  quality: 'good' | 'flagged' | 'invalid'
  enjoyment?: number | null
  metrics: Record<string, unknown>
  code_version?: string
}

export interface SessionDataStatus {
  session_id: string
  status: string
  sample_count: number
  trial_count: number
  response_count: number
  event_count: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new Error("Can't reach the Stick Drift server. Is the backend running?")
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : `Request failed (${res.status})`
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const listParticipants = () => request<Participant[]>('/participants')

export const createParticipant = (alias: string, dominant_hand: Hand) =>
  request<Participant>('/participants', {
    method: 'POST',
    body: JSON.stringify({ alias, dominant_hand }),
  })

export const listSessions = (participantId: string) =>
  request<SessionRow[]>(`/participants/${participantId}/sessions`)

export const startSession = (participantId: string, input: StartSessionInput = {}) =>
  request<StartedSession>(`/participants/${participantId}/sessions`, {
    method: 'POST',
    body: JSON.stringify(input),
  })

export const uploadSamples = (sessionId: string, samples: JoystickSample[]) =>
  request<{ received: number; session_id: string }>(`/sessions/${sessionId}/samples`, {
    method: 'POST',
    body: JSON.stringify({ samples }),
  })

export const saveTrial = (sessionId: string, trial: TrialResult) =>
  request<{ session_id: string; trial_id: number; saved: boolean }>(`/sessions/${sessionId}/trials`, {
    method: 'POST',
    body: JSON.stringify(trial),
  })

export const uploadEvents = (sessionId: string, events: SessionEvent[]) =>
  request<{ received: number; session_id: string }>(`/sessions/${sessionId}/events`, {
    method: 'POST',
    body: JSON.stringify({ events }),
  })

export const finishSession = (sessionId: string, input: FinishSessionInput) =>
  request<{ session_id: string; status: string; quality: string }>(`/sessions/${sessionId}/complete`, {
    method: 'POST',
    body: JSON.stringify(input),
  })

export const abandonSession = (sessionId: string) =>
  request<{ session_id: string; status: string }>(`/sessions/${sessionId}/abandon`, { method: 'POST' })

export const getSessionDataStatus = (sessionId: string) =>
  request<SessionDataStatus>(`/sessions/${sessionId}/data-status`)
