// App-wide state: persona, selected area, language, text size, Ask panel.
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, getToken, setToken } from './api'
import { fontFor, translate, type Key, type Lang } from './i18n'
import type { ChildReason, Meta, User } from './types'

export type Unit = { unit_type: 'state' | 'district' | 'block' | 'school'; unit: string | null }
type T = (key: Key | string, vars?: Record<string, string | number | null | undefined>) => string

type Ctx = {
  user: User | null
  meta: Meta | undefined
  unit: Unit
  setUnit: (u: Unit) => void
  login: (personaId: string) => Promise<void>
  logout: () => void
  ask: (q?: string) => void
  askOpen: boolean
  askSeed: string | null
  setAskOpen: (b: boolean) => void
  lang: Lang
  setLang: (l: Lang) => void
  langChosen: boolean
  textSize: number
  setTextSize: (n: number) => void
  t: T
}

const AppCtx = createContext<Ctx | null>(null)
const SIZES = [16, 18, 20]

export function AppProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [unit, setUnit] = useState<Unit>({ unit_type: 'state', unit: null })
  const [askOpen, setAskOpen] = useState(false)
  const [askSeed, setAskSeed] = useState<string | null>(null)
  const [lang, setLangState] = useState<Lang>(() => (localStorage.getItem('sp_lang') as Lang) || 'en')
  const [langChosen, setLangChosen] = useState(() => !!localStorage.getItem('sp_lang'))
  const [textSize, setTextSizeState] = useState<number>(() => Number(localStorage.getItem('sp_size') || 0))
  const meta = useQuery({ queryKey: ['meta'], queryFn: () => api.get<Meta>('/meta'), enabled: !!user, refetchInterval: 15000 })

  useEffect(() => {
    if (getToken()) api.get<User>('/me').then(applyUser).catch(() => setToken(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.style.setProperty('--font-ui', fontFor(lang))
  }, [lang])
  useEffect(() => { document.documentElement.style.fontSize = `${SIZES[textSize] ?? 16}px` }, [textSize])

  const setLang = (l: Lang) => {
    localStorage.setItem('sp_lang', l)
    setLangState(l)
    setLangChosen(true)
  }
  const setTextSize = (n: number) => {
    localStorage.setItem('sp_size', String(n))
    setTextSizeState(n)
  }
  const t = useCallback<T>((key, vars) => translate(lang, key, vars), [lang])

  function applyUser(u: User) {
    setUser(u)
    if (u.scope_type === 'district') setUnit({ unit_type: 'district', unit: u.scope })
    else if (u.scope_type === 'block') setUnit({ unit_type: 'block', unit: u.scope })
    else if (u.scope_type === 'school') setUnit({ unit_type: 'block', unit: u.block })
    else setUnit({ unit_type: 'state', unit: null })
  }

  async function login(personaId: string) {
    const r = await api.post<{ token: string; user: User }>('/login', { persona_id: personaId })
    setToken(r.token)
    qc.clear()
    applyUser(r.user)
  }

  function logout() {
    setToken(null)
    setUser(null)
    qc.clear()
  }

  function ask(q?: string) {
    setAskSeed(q ?? null)
    setAskOpen(true)
  }

  return (
    <AppCtx.Provider value={{ user, meta: meta.data, unit, setUnit, login, logout, ask, askOpen, askSeed, setAskOpen,
      lang, setLang, langChosen, textSize, setTextSize, t }}>
      {children}
    </AppCtx.Provider>
  )
}

export function useApp() {
  const c = useContext(AppCtx)
  if (!c) throw new Error('useApp outside provider')
  return c
}

export const useT = () => useApp().t

export const unitQs = (u: Unit) => `unit_type=${u.unit_type}${u.unit ? `&unit=${encodeURIComponent(u.unit)}` : ''}`

/** Block shown on block-level pages: the selected block, else the first block needing review in the selected area. */
export function useFocusBlock(): string | null {
  const { unit, meta } = useApp()
  const q = unitQs(unit)
  const kids = useQuery({
    queryKey: ['children', q], queryFn: () => api.get<ChildReason[]>(`/children-reasons?${q}`),
    enabled: unit.unit_type === 'district' || unit.unit_type === 'state',
  })
  // At state level the first child is a district: look one level down for its most affected block
  // (instead of the alphabetically first block, which says nothing about need).
  const topDistrict = kids.data?.[0]?.unit_type === 'district' ? kids.data[0].unit : null
  const grand = useQuery({
    queryKey: ['children', `unit_type=district&unit=${topDistrict}`], enabled: !!topDistrict,
    queryFn: () => api.get<ChildReason[]>(`/children-reasons?unit_type=district&unit=${encodeURIComponent(topDistrict!)}`),
  })
  if (unit.unit_type === 'block') return unit.unit
  if (!meta || !kids.data) return null
  const first = kids.data[0]
  if (!first) return Object.values(meta.tree)[0]?.[0] ?? null
  if (first.unit_type === 'block') return first.unit
  return grand.data?.[0]?.unit ?? (grand.isLoading ? null : meta.tree[first.unit]?.[0] ?? null)
}
