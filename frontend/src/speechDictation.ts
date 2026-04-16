/**
 * Browser Web Speech API (SpeechRecognition) for fast local dictation.
 * Not guaranteed offline; engine is browser/OS dependent.
 */

/** Minimal typing; DOM lib may omit SpeechRecognition on some TS configs */
type SpeechAlternative = { transcript: string }

type SpeechRecognitionResultLike = {
  length: number
  isFinal: boolean
  item?: (index: number) => SpeechAlternative | undefined
  [index: number]: SpeechAlternative | undefined
}

type SpeechRecognitionResultList = {
  length: number
  [index: number]: SpeechRecognitionResultLike
}

type SpeechRecognitionEventLike = {
  resultIndex: number
  results: SpeechRecognitionResultList
}

type SpeechRecognitionErrorLike = { error?: string; message?: string }

type SpeechRecognitionInstance = {
  continuous: boolean
  interimResults: boolean
  lang: string
  maxAlternatives?: number
  start: () => void
  stop: () => void
  abort: () => void
  onresult: ((ev: SpeechRecognitionEventLike) => void) | null
  onend: (() => void) | null
  onerror: ((ev: SpeechRecognitionErrorLike) => void) | null
}

type SpeechRecognitionCtor = new () => SpeechRecognitionInstance

function getRecognitionConstructor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export function isBrowserDictationAvailable(): boolean {
  return getRecognitionConstructor() !== null
}

function alternativeTranscript(row: SpeechRecognitionResultLike | undefined): string {
  if (!row || row.length < 1) return ''
  const viaItem = typeof row.item === 'function' ? row.item(0) : undefined
  const alt = viaItem ?? row[0]
  return typeof alt?.transcript === 'string' ? alt.transcript : ''
}

function fullTranscriptFromResults(results: SpeechRecognitionResultList): string {
  let display = ''
  for (let i = 0; i < results.length; i++) {
    display += alternativeTranscript(results[i])
  }
  return display.trim()
}

export type DictationSession = {
  finishAndGetTranscript: () => Promise<string>
  discard: () => void
}

export function startDictationSession(options?: {
  lang?: string
  /** Full transcript so far (final + interim), for live UI */
  onTranscript?: (text: string) => void
  /** Browser error code, e.g. `not-allowed`, `service-not-allowed`, `audio-capture` */
  onServiceError?: (code: string) => void
}): DictationSession | null {
  const Ctor = getRecognitionConstructor()
  if (!Ctor) return null

  const rec = new Ctor()
  let finalBuffer = ''
  let settled = false
  let settle!: (value: string) => void
  const done = new Promise<string>((resolve) => {
    settle = resolve
  })

  const finish = (value: string) => {
    if (settled) return
    settled = true
    settle(value.trim())
  }

  rec.continuous = true
  rec.interimResults = true
  try {
    rec.maxAlternatives = 1
  } catch {
    // ignore; not all engines expose this
  }
  rec.lang = options?.lang ?? (typeof navigator !== 'undefined' ? navigator.language : undefined) ?? 'en-US'

  rec.onresult = (event: SpeechRecognitionEventLike) => {
    const display = fullTranscriptFromResults(event.results)
    if (display) {
      finalBuffer = display
    }
    options?.onTranscript?.(display)
  }

  rec.onend = () => {
    if (!settled) finish(finalBuffer)
  }

  rec.onerror = (event: SpeechRecognitionErrorLike) => {
    const code = typeof event?.error === 'string' ? event.error : 'unknown'
    if (code !== 'aborted') {
      options?.onServiceError?.(code)
    }
    if (!settled) finish(finalBuffer)
  }

  try {
    rec.start()
  } catch {
    return null
  }

  return {
    finishAndGetTranscript() {
      try {
        rec.stop()
      } catch {
        finish(finalBuffer)
      }
      return Promise.race([
        done,
        new Promise<string>((resolve) => {
          setTimeout(() => resolve(finalBuffer.trim()), 3200)
        }),
      ])
    },
    discard() {
      try {
        rec.abort()
      } catch {
        // ignore
      }
      finish('')
    },
  }
}
