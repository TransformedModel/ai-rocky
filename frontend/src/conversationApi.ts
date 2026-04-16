export type ConversationTurnResult = {
  sessionId: string
  turn: number
  userText: string
  rockyText: string
  rockyAudioUrl: string
}

export type ConversationTranscribeResult = {
  sessionId: string
  turn: number
  userText: string
}

export async function startConversation(): Promise<{ sessionId: string }> {
  const res = await fetch('/api/conversation/start', { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to start conversation (${res.status})`)
  return (await res.json()) as { sessionId: string }
}

export async function transcribeTurn(params: {
  sessionId: string
  turn: number
  audioBlob: Blob
  audioFilename?: string
}): Promise<ConversationTranscribeResult> {
  const form = new FormData()
  form.set('sessionId', params.sessionId)
  form.set('turn', String(params.turn))
  form.set('audio', params.audioBlob, params.audioFilename ?? 'user.webm')

  const res = await fetch('/api/conversation/transcribe-turn', { method: 'POST', body: form })
  if (!res.ok) {
    let detail = ''
    try {
      const data = (await res.json()) as { detail?: unknown }
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      // ignore
    }
    throw new Error(detail ? `Transcribe failed: ${detail}` : `Transcribe failed (${res.status})`)
  }
  return (await res.json()) as ConversationTranscribeResult
}

export async function replyTurn(params: {
  sessionId: string
  turn: number
  typedText?: string
}): Promise<ConversationTurnResult> {
  const form = new FormData()
  form.set('sessionId', params.sessionId)
  form.set('turn', String(params.turn))
  if (params.typedText) form.set('typedText', params.typedText)

  const res = await fetch('/api/conversation/reply-turn', { method: 'POST', body: form })
  if (!res.ok) {
    let detail = ''
    try {
      const data = (await res.json()) as { detail?: unknown }
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      // ignore
    }
    throw new Error(detail ? `Reply failed: ${detail}` : `Reply failed (${res.status})`)
  }
  return (await res.json()) as ConversationTurnResult
}
