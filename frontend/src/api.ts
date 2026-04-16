import type { Voice } from './voices'

export async function fetchVoices(): Promise<Voice[]> {
  const res = await fetch('/api/voices')
  if (!res.ok) throw new Error(`Failed to load voices (${res.status})`)
  return (await res.json()) as Voice[]
}

export async function tts(text: string, voiceId: string): Promise<Blob> {
  const res = await fetch('/api/tts', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ text, voiceId }),
  })

  if (!res.ok) {
    let detail = ''
    try {
      const data = (await res.json()) as { detail?: unknown }
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      // ignore
    }
    throw new Error(detail ? `TTS failed: ${detail}` : `TTS failed (${res.status})`)
  }

  return await res.blob()
}

