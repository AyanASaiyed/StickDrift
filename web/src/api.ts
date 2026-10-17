const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Hand = 'left' | 'right' | 'unknown'

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
