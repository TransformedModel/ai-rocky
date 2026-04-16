export type VoiceMode = 'design' | 'clone'

export type Voice = {
  id: string
  label: string
  mode: VoiceMode
  instruct?: string | null
  ref_audio_name?: string | null
}

