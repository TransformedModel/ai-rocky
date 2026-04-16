import { useEffect, useMemo, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import './App.css'
import { replyTurn, startConversation, transcribeTurn } from './conversationApi'
import {
  isBrowserDictationAvailable,
  startDictationSession,
  type DictationSession,
} from './speechDictation'

type ChatMsg = {
  role: 'user' | 'rocky'
  text: string
  turn: number
  audioUrl?: string
}

const AVATAR_ROCKY = '/avatars/rocky.png'
const AVATAR_USER = '/avatars/user.png'

// 200ms of silence, 24kHz mono PCM16 WAV
const SILENT_WAV_DATA_URI =
  'data:audio/wav;base64,UklGRmQAAABXQVZFZm10IBAAAAABAAEAwF0AAIC7AAACABAAZGF0YUAAAAA='

function IconMic({ recording }: { recording: boolean }) {
  return (
    <svg className="iconSvg" viewBox="0 0 24 24" aria-hidden="true" width="22" height="22">
      <path
        fill="currentColor"
        d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V19H9v2h6v-2h-2v-1.08A7 7 0 0 0 19 11h-2z"
      />
      {recording ? <circle className="micRecDot" cx="18" cy="6" r="3" /> : null}
    </svg>
  )
}

function IconSend() {
  return (
    <svg className="iconSvg" viewBox="0 0 24 24" aria-hidden="true" width="18" height="18">
      <path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
    </svg>
  )
}

function IconTrash() {
  return (
    <svg className="iconSvg" viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
      <path
        fill="currentColor"
        d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"
      />
    </svg>
  )
}

function IconPlay() {
  return (
    <svg className="iconSvg iconPlay" viewBox="0 0 24 24" aria-hidden="true" width="18" height="18">
      <path fill="currentColor" d="M8 5v14l11-7z" />
    </svg>
  )
}

function AvatarRocky() {
  const [broke, setBroke] = useState(false)
  if (broke) {
    return (
      <div className="avatar avatarRocky" aria-hidden="true">
        R
      </div>
    )
  }
  return (
    <img
      className="avatarImg avatarRocky"
      src={AVATAR_ROCKY}
      alt=""
      onError={() => setBroke(true)}
    />
  )
}

function AvatarUser() {
  const [broke, setBroke] = useState(false)
  if (broke) {
    return (
      <div className="avatar avatarUser" aria-hidden="true">
        You
      </div>
    )
  }
  return (
    <img
      className="avatarImg avatarUser"
      src={AVATAR_USER}
      alt=""
      onError={() => setBroke(true)}
    />
  )
}

function TypingBubbleRocky() {
  return (
    <div className="bubbleRow bubbleRowRocky" aria-live="polite" aria-label="Rocky is typing">
      <AvatarRocky />
      <div className="bubble bubbleRocky typingBubble">
        <span className="typingDots">
          <span className="typingDot" />
          <span className="typingDot" />
          <span className="typingDot" />
        </span>
      </div>
    </div>
  )
}

function TypingBubbleUser({ label }: { label: string }) {
  return (
    <div className="bubbleRow bubbleRowUser" aria-live="polite" aria-label={label}>
      <div className="bubble bubbleUser typingBubbleUser">
        <span className="typingDots typingDotsUser">
          <span className="typingDot typingDotUser" />
          <span className="typingDot typingDotUser" />
          <span className="typingDot typingDotUser" />
        </span>
      </div>
      <AvatarUser />
    </div>
  )
}

function App() {
  const [sessionId, setSessionId] = useState<string>('')
  const sessionIdRef = useRef<string>('')
  const [turn, setTurn] = useState<number>(1)
  const [typedText, setTypedText] = useState<string>('')
  const [dictationLiveText, setDictationLiveText] = useState('')
  const dictationLiveTextRef = useRef('')
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [status, setStatus] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)
  const [awaitingUserTranscribe, setAwaitingUserTranscribe] = useState(false)
  const [awaitingDictationWrapup, setAwaitingDictationWrapup] = useState(false)
  const [awaitingRocky, setAwaitingRocky] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const [isRecording, setIsRecording] = useState(false)
  const [isArmingMic, setIsArmingMic] = useState(false)
  const recordStartedAtRef = useRef<number>(0)
  const autoPlayedTurnsRef = useRef<Set<number>>(new Set())
  const listEndRef = useRef<HTMLDivElement | null>(null)
  const dictationRef = useRef<DictationSession | null>(null)
  const isStartingMicRef = useRef(false)
  const pendingRecordingBlobRef = useRef<Blob | null>(null)
  const pendingRecordingUrlRef = useRef<string | null>(null)

  function revokePendingRecordingPreview() {
    if (pendingRecordingUrlRef.current) {
      URL.revokeObjectURL(pendingRecordingUrlRef.current)
      pendingRecordingUrlRef.current = null
    }
    pendingRecordingBlobRef.current = null
  }

  function clearPendingRecordingRefsOnly() {
    pendingRecordingBlobRef.current = null
    pendingRecordingUrlRef.current = null
  }

  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  const canRecord = useMemo(() => !isLoading || isRecording, [isLoading, isRecording])
  const micDisabled = isLoading && !isRecording && !isArmingMic
  const inputDisabled = isLoading

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, awaitingRocky, awaitingUserTranscribe, awaitingDictationWrapup])

  async function ensureSessionId(): Promise<string> {
    if (sessionIdRef.current) return sessionIdRef.current
    const out = await startConversation()
    sessionIdRef.current = out.sessionId
    setSessionId(out.sessionId)
    setTurn(1)
    autoPlayedTurnsRef.current = new Set()
    return out.sessionId
  }

  async function playOnce(url: string) {
    const audio = audioRef.current
    if (!audio) return
    audio.pause()
    audio.src = url
    try {
      await audio.play()
    } catch {
      setStatus('Tap the play button on Rocky’s message to hear audio.')
    }
  }

  async function primeAudioPlayback() {
    const audio = audioRef.current
    if (!audio) return
    try {
      const prevSrc = audio.src
      audio.muted = true
      audio.src = SILENT_WAV_DATA_URI
      const p = audio.play()
      await Promise.race([p, new Promise<void>((r) => setTimeout(r, 150))])
      audio.pause()
      audio.currentTime = 0
      audio.src = prevSrc
    } catch {
      // ignore
    } finally {
      audio.muted = false
    }
  }

  function discardRecording() {
    if (!isRecording) return
    const mr = mediaRecorderRef.current
    dictationRef.current?.discard()
    dictationRef.current = null
    chunksRef.current = []
    setTypedText('')
    dictationLiveTextRef.current = ''
    setDictationLiveText('')
    setIsRecording(false)
    setStatus('')
    if (mr && mr.state !== 'inactive') {
      mr.ondataavailable = () => {
        // ignore final chunks while discarding
      }
      mr.onstop = () => {
        try {
          mr.stream.getTracks().forEach((t) => t.stop())
        } catch {
          // ignore
        }
        chunksRef.current = []
      }
      try {
        mr.stop()
      } catch {
        // ignore
      }
    } else if (mr?.stream) {
      try {
        mr.stream.getTracks().forEach((t) => t.stop())
      } catch {
        // ignore
      }
    }
    mediaRecorderRef.current = null
  }

  async function stopRecording(opts?: { omitReviewHint?: boolean }): Promise<{ ok: boolean; mergedText: string }> {
    const fail = { ok: false as const, mergedText: '' }
    const mr = mediaRecorderRef.current
    if (!mr || !isRecording) return fail

    setIsRecording(false)
    setStatus('')

    try {
      const audioPromise = new Promise<Blob>((resolve) => {
        mr.onstop = () => {
          try {
            mr.stream.getTracks().forEach((t) => t.stop())
          } catch {
            // ignore
          }
          const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
          resolve(blob)
        }
      })

      mr.stop()
      const audioBlob = await audioPromise
      const ms = Date.now() - recordStartedAtRef.current
      if (audioBlob.size < 8_000 || ms < 600) {
        dictationRef.current?.discard()
        dictationRef.current = null
        dictationLiveTextRef.current = ''
        setDictationLiveText('')
        setStatus('Recording was too short. Record at least a second and speak clearly.')
        return fail
      }

      const dictation = dictationRef.current
      dictationRef.current = null
      let dictatedText = ''
      if (dictation) setAwaitingDictationWrapup(true)
      try {
        dictatedText = dictation ? await dictation.finishAndGetTranscript() : ''
      } finally {
        setAwaitingDictationWrapup(false)
      }

      const trimmed = dictatedText.trim()
      const fromLive = dictationLiveTextRef.current.trim()
      const merged = trimmed || fromLive
      setTypedText(merged)
      dictationLiveTextRef.current = ''
      setDictationLiveText('')

      revokePendingRecordingPreview()
      pendingRecordingBlobRef.current = audioBlob
      pendingRecordingUrlRef.current = URL.createObjectURL(audioBlob)
      if (opts?.omitReviewHint) {
        setStatus('')
      } else {
        setStatus('Review the text, then tap send when you’re ready.')
      }
      return { ok: true, mergedText: merged }
    } catch (e: any) {
      setAwaitingDictationWrapup(false)
      setStatus(String(e?.message ?? e))
      return fail
    }
  }

  async function sendTyped() {
    if (isLoading) return
    if (isArmingMic) {
      setStatus('Wait for the mic to finish starting.')
      return
    }

    let textForSend = typedText.trim()
    if (isRecording) {
      const stopped = await stopRecording({ omitReviewHint: true })
      if (!stopped.ok) return
      textForSend = stopped.mergedText.trim()
    }

    const text = textForSend
    const pendingBlob = pendingRecordingBlobRef.current
    if (!text && !pendingBlob) {
      setStatus('Write something first, or record a message to send.')
      return
    }

    const pendingUrl = pendingRecordingUrlRef.current
    const userAudioUrl: string | undefined = pendingUrl ?? undefined

    const sendTurn = turn
    let optimisticUserAdded = false

    setIsLoading(true)
    setAwaitingRocky(true)
    setStatus('Rocky is thinking…')

    try {
      const sid = await ensureSessionId()
      await primeAudioPlayback()

      if (text) {
        setMessages((m) => [...m, { role: 'user', text, turn: sendTurn, audioUrl: userAudioUrl }])
        optimisticUserAdded = true
        setTypedText('')
        clearPendingRecordingRefsOnly()

        const res = await replyTurn({ sessionId: sid, turn: sendTurn, typedText: text })
        setMessages((m) => [
          ...m.map((row, i) =>
            i === m.length - 1 && row.role === 'user' && row.turn === sendTurn
              ? ({ role: 'user', text: res.userText, turn: res.turn, audioUrl: userAudioUrl } satisfies ChatMsg)
              : row,
          ),
          {
            role: 'rocky' as const,
            text: res.rockyText,
            turn: res.turn,
            audioUrl: res.rockyAudioUrl,
          },
        ])

        if (!autoPlayedTurnsRef.current.has(res.turn)) {
          autoPlayedTurnsRef.current.add(res.turn)
          try {
            await playOnce(res.rockyAudioUrl)
            setStatus('')
          } catch {
            setStatus('Tap play on Rocky’s message if you don’t hear audio.')
          }
        }

        setTurn((t) => t + 1)
        return
      }

      setAwaitingUserTranscribe(true)
      setAwaitingRocky(false)
      setStatus('Transcribing on server…')

      const tr = await transcribeTurn({
        sessionId: sid,
        turn: sendTurn,
        audioBlob: pendingBlob!,
        audioFilename: `user_turn_${String(sendTurn).padStart(4, '0')}.webm`,
      })

      setAwaitingUserTranscribe(false)
      setAwaitingRocky(true)
      setStatus('Rocky is thinking…')

      const res = await replyTurn({ sessionId: sid, turn: sendTurn })

      clearPendingRecordingRefsOnly()
      setTypedText('')
      setMessages((m) => [
        ...m,
        { role: 'user', text: tr.userText, turn: tr.turn, audioUrl: userAudioUrl },
        { role: 'rocky', text: res.rockyText, turn: res.turn, audioUrl: res.rockyAudioUrl },
      ])

      if (!autoPlayedTurnsRef.current.has(res.turn)) {
        autoPlayedTurnsRef.current.add(res.turn)
        try {
          await playOnce(res.rockyAudioUrl)
          setStatus('')
        } catch {
          setStatus('Tap play on Rocky’s message if you don’t hear audio.')
        }
      }

      setTurn((t) => t + 1)
    } catch (e: any) {
      setAwaitingUserTranscribe(false)
      if (optimisticUserAdded) {
        setMessages((m) => {
          const last = m[m.length - 1]
          if (last?.role === 'user' && last.turn === sendTurn) {
            return m.slice(0, -1)
          }
          return m
        })
      }
      setStatus(String(e?.message ?? e))
    } finally {
      setAwaitingRocky(false)
      setIsLoading(false)
    }
  }

  function onMicClick() {
    if (micDisabled && !isRecording && !isArmingMic) return
    if (isRecording) {
      void stopRecording()
      return
    }
    if (!canRecord) return
    if (isStartingMicRef.current) return

    isStartingMicRef.current = true
    setIsArmingMic(true)
    revokePendingRecordingPreview()
    setTypedText('')
    dictationLiveTextRef.current = ''
    setDictationLiveText('')

    dictationRef.current = isBrowserDictationAvailable()
      ? startDictationSession({
          onTranscript: (t) => {
            dictationLiveTextRef.current = t
            flushSync(() => {
              setDictationLiveText(t)
            })
          },
          onServiceError: (code) => {
            if (code === 'no-speech' || code === 'aborted') return
            setStatus(`Dictation: ${code}. If the box stays empty, you can still send after stopping the mic.`)
          },
        })
      : null

    async function attachMediaRecorder() {
      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          dictationRef.current?.discard()
          dictationRef.current = null
          setStatus('Microphone recording is not supported in this browser.')
          return
        }
        await ensureSessionId()
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
        chunksRef.current = []
        mr.ondataavailable = (e) => {
          if (e.data.size > 0) chunksRef.current.push(e.data)
        }
        mr.onstop = () => {
          stream.getTracks().forEach((t) => t.stop())
        }
        mediaRecorderRef.current = mr
        mr.start()
        setIsRecording(true)
        recordStartedAtRef.current = Date.now()
        setStatus(dictationRef.current ? 'Recording… (dictation on)' : 'Recording…')
      } catch (e: any) {
        dictationRef.current?.discard()
        dictationRef.current = null
        setStatus(String(e?.message ?? e))
      } finally {
        setIsArmingMic(false)
        isStartingMicRef.current = false
      }
    }

    void attachMediaRecorder()
  }

  const showEmptyHint = !sessionId && messages.length === 0

  return (
    <div className="appShell chatLayout">
      <header className="chatTopBar">
        <div className="chatTopBarMain">
          <div className="title">Rocky</div>
          <div className="subtitle">Your friend from Erid</div>
        </div>
      </header>

      <main className="chatMain">
        <div className="messageList" role="log" aria-label="Conversation">
          {showEmptyHint ? (
            <div className="emptyChat">
              <p>
                Tap the <strong>mic</strong> to start your first message. A session starts automatically when you record.
                Stop the mic to fill the box; tap <strong>send</strong> when you want Rocky to reply.
              </p>
            </div>
          ) : null}

          {messages.map((m, idx) =>
            m.role === 'user' ? (
              <div key={`${m.turn}-${m.role}-${idx}`} className="bubbleRow bubbleRowUser">
                <div className="bubble bubbleUser">
                  <div className="bubbleText">{m.text}</div>
                  {m.audioUrl ? (
                    <div className="bubbleMeta">
                      <button
                        type="button"
                        className="iconBtn iconBtnUser"
                        onClick={() => playOnce(m.audioUrl!)}
                        aria-label="Play your recording"
                      >
                        <IconPlay />
                      </button>
                      <a className="bubbleDownload" href={m.audioUrl} download={`user-turn-${m.turn}.webm`}>
                        Download
                      </a>
                    </div>
                  ) : null}
                </div>
                <AvatarUser />
              </div>
            ) : (
              <div key={`${m.turn}-${m.role}-${idx}`} className="bubbleRow bubbleRowRocky">
                <AvatarRocky />
                <div className="bubble bubbleRocky">
                  <div className="bubbleText">{m.text}</div>
                  {m.audioUrl ? (
                    <div className="bubbleMeta">
                      <button
                        type="button"
                        className="iconBtn iconBtnRocky"
                        onClick={() => playOnce(m.audioUrl!)}
                        aria-label="Play Rocky’s voice"
                      >
                        <IconPlay />
                      </button>
                      <a className="bubbleDownload" href={m.audioUrl} download={`rocky-turn-${m.turn}.wav`}>
                        Download
                      </a>
                    </div>
                  ) : null}
                </div>
              </div>
            ),
          )}

          {awaitingUserTranscribe || awaitingDictationWrapup ? (
            <TypingBubbleUser
              label={
                awaitingDictationWrapup
                  ? 'Finishing on-device dictation'
                  : 'Transcribing your message on the server'
              }
            />
          ) : null}
          {awaitingRocky ? <TypingBubbleRocky /> : null}
          <div ref={listEndRef} className="listAnchor" />
        </div>
      </main>

      <footer className="composerWrap">
        <div className="composerBar">
          <div className="composerInner">
            <div className="composerMicCluster">
              <button
                type="button"
                className={`micButton${isRecording || isArmingMic ? ' micButtonRecording' : ''}`}
                onClick={onMicClick}
                disabled={micDisabled && !isRecording && !isArmingMic}
                aria-pressed={isRecording || isArmingMic}
                aria-label={isRecording ? 'Stop recording' : 'Start recording'}
              >
                <IconMic recording={isRecording || isArmingMic} />
              </button>
              {isRecording ? (
                <button
                  type="button"
                  className="discardRecordingBtn"
                  onClick={(e) => {
                    e.preventDefault()
                    discardRecording()
                  }}
                  aria-label="Discard recording"
                >
                  <IconTrash />
                </button>
              ) : null}
            </div>
            <input
              className="composerInput"
              type="text"
              value={isRecording || isArmingMic ? dictationLiveText : typedText}
              onChange={(e) => {
                if (isRecording || isArmingMic) return
                setTypedText(e.target.value)
              }}
              placeholder={isRecording || isArmingMic ? 'Listening…' : 'Write something…'}
              readOnly={isRecording || isArmingMic}
              disabled={inputDisabled}
              onKeyDown={(e) => {
                if (e.key !== 'Enter' || e.shiftKey) return
                e.preventDefault()
                if (isArmingMic) return
                void sendTyped()
              }}
            />
            <button
              type="button"
              className="sendFab"
              onClick={() => void sendTyped()}
              disabled={inputDisabled}
              aria-label="Send message"
            >
              <IconSend />
            </button>
          </div>
        </div>
        <div className="statusLine" role="status" aria-live="polite">
          {status}
        </div>
      </footer>

      <audio ref={audioRef} className="srOnly" preload="auto" />
    </div>
  )
}

export default App
