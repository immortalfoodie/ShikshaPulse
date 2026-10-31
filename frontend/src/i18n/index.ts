// Tiny i18n runtime: dictionaries, interpolation and language metadata.
import bn from './bn'
import en, { type Key } from './en'
import hi from './hi'
import mr from './mr'
import ta from './ta'
import te from './te'
import { bnX, enX, hiX, mrX, taX, teX } from './extra'
import { bnG, enG, hiG, mrG, taG, teG } from './guide'

export type Lang = 'en' | 'hi' | 'mr' | 'bn' | 'ta' | 'te'
export type { Key }

export const LANGS: { code: Lang; native: string; english: string; speech: string; sample: string }[] = [
  { code: 'hi', native: 'हिन्दी', english: 'Hindi', speech: 'hi-IN', sample: 'नमस्ते' },
  { code: 'en', native: 'English', english: 'English', speech: 'en-IN', sample: 'Hello' },
  { code: 'mr', native: 'मराठी', english: 'Marathi', speech: 'mr-IN', sample: 'नमस्कार' },
  { code: 'bn', native: 'বাংলা', english: 'Bengali', speech: 'bn-IN', sample: 'নমস্কার' },
  { code: 'ta', native: 'தமிழ்', english: 'Tamil', speech: 'ta-IN', sample: 'வணக்கம்' },
  { code: 'te', native: 'తెలుగు', english: 'Telugu', speech: 'te-IN', sample: 'నమస్తే' },
]

const DICTS: Record<Lang, Record<string, string>> = {
  en: { ...en, ...enX, ...enG },
  hi: { ...hi, ...hiX, ...hiG },
  mr: { ...mr, ...mrX, ...mrG },
  bn: { ...bn, ...bnX, ...bnG },
  ta: { ...ta, ...taX, ...taG },
  te: { ...te, ...teX, ...teG },
} as Record<Lang, Record<string, string>>

export function translate(
  lang: Lang,
  key: Key | string,
  vars?: Record<string, string | number | null | undefined>,
): string {
  const s = DICTS[lang][key] ?? DICTS.en[key] ?? String(key)
  if (!vars) return s
  return s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] === undefined || vars[k] === null ? '' : String(vars[k])))
}

export const has = (key: string) => key in DICTS.en
export const speechCode = (lang: Lang) => LANGS.find((l) => l.code === lang)?.speech ?? 'en-IN'

/** Font stack per script (bundled @fontsource fonts). */
export const fontFor = (lang: Lang) =>
  lang === 'ta'
    ? '"Noto Sans Tamil", "Mukta", system-ui, sans-serif'
    : lang === 'te'
      ? '"Noto Sans Telugu", "Mukta", system-ui, sans-serif'
      : lang === 'bn'
        ? '"Noto Sans Bengali", "Mukta", system-ui, sans-serif'
        : '"Mukta", system-ui, "Segoe UI", sans-serif'
