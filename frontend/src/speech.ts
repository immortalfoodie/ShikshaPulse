// Read-aloud (speechSynthesis) and voice input (SpeechRecognition) with graceful fallbacks.
import { useCallback, useEffect, useRef, useState } from 'react'
import { speechCode, type Lang } from './i18n'

export function useSpeaker(lang: Lang) {
  const [speaking, setSpeaking] = useState(false)
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window
  useEffect(
    () => () => {
      if (supported) window.speechSynthesis.cancel()
    },
    [supported],
  )
  const speak = useCallback(
    (text: string) => {
      if (!supported || !text) return
      window.speechSynthesis.cancel()
      const u = new SpeechSynthesisUtterance(text.replace(/\bpp\b/g, 'points'))
      u.lang = speechCode(lang)
      const voice =
        window.speechSynthesis.getVoices().find((v) => v.lang === u.lang) ??
        window.speechSynthesis.getVoices().find((v) => v.lang.startsWith(u.lang.slice(0, 2)))
      if (voice) u.voice = voice
      u.rate = 0.92
      u.onend = () => setSpeaking(false)
      u.onerror = () => setSpeaking(false)
      setSpeaking(true)
      window.speechSynthesis.speak(u)
    },
    [lang, supported],
  )
  const stop = useCallback(() => {
    if (supported) window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])
  return { speak, stop, speaking, supported }
}

type Rec = {
  lang: string
  interimResults: boolean
  continuous: boolean
  start: () => void
  stop: () => void
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
}

export function useListener(lang: Lang, onText: (t: string) => void) {
  const Ctor =
    typeof window !== 'undefined'
      ? (((window as unknown as Record<string, unknown>).SpeechRecognition ??
          (window as unknown as Record<string, unknown>).webkitSpeechRecognition) as (new () => Rec) | undefined)
      : undefined
  const [listening, setListening] = useState(false)
  const ref = useRef<Rec | null>(null)
  const start = useCallback(() => {
    if (!Ctor) return
    const r = new Ctor()
    r.lang = speechCode(lang)
    r.interimResults = false
    r.continuous = false
    r.onresult = (e) => {
      const t = e.results[0]?.[0]?.transcript
      if (t) onText(t)
    }
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    ref.current = r
    setListening(true)
    r.start()
  }, [Ctor, lang, onText])
  const stop = useCallback(() => {
    ref.current?.stop()
    setListening(false)
  }, [])
  return { start, stop, listening, supported: !!Ctor }
}
