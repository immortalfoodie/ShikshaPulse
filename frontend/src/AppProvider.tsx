// Owns app-wide state (persona, selected area, language, text size, Ask panel) and exposes it via AppContext.
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, getToken, setToken } from './api'
import { fontFor, translate, type Lang } from './i18n'
import { AppContext, type Translate, type Unit } from './state'
import type { Meta, User } from './types'

const LANG_KEY = 'sp_lang'
const TEXT_SIZE_KEY = 'sp_size'
/** Root font sizes (px) selectable from the text-size control. */
const TEXT_SIZES_PX = [16, 18, 20]

/** The default area a user lands on, derived from their scope. Headmasters see their school's block. */
function defaultUnitFor(user: User): Unit {
  switch (user.scope_type) {
    case 'district':
      return { unit_type: 'district', unit: user.scope }
    case 'block':
      return { unit_type: 'block', unit: user.scope }
    case 'school':
      return { unit_type: 'block', unit: user.block }
    default:
      return { unit_type: 'state', unit: null }
  }
}

/** Provides {@link AppContext} to the tree; restores the session token on mount. */
export function AppProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [unit, setUnit] = useState<Unit>({ unit_type: 'state', unit: null })
  const [askOpen, setAskOpen] = useState(false)
  const [askSeed, setAskSeed] = useState<string | null>(null)
  const [lang, setLangState] = useState<Lang>(() => (localStorage.getItem(LANG_KEY) as Lang) || 'en')
  const [langChosen, setLangChosen] = useState(() => !!localStorage.getItem(LANG_KEY))
  const [textSize, setTextSizeState] = useState<number>(() => Number(localStorage.getItem(TEXT_SIZE_KEY) || 0))
  const meta = useQuery({
    queryKey: ['meta'],
    queryFn: () => api.get<Meta>('/meta'),
    enabled: !!user,
    refetchInterval: 15000,
  })

  const applyUser = useCallback((nextUser: User) => {
    setUser(nextUser)
    setUnit(defaultUnitFor(nextUser))
  }, [])

  // Restore an existing session once on mount.
  useEffect(() => {
    if (getToken())
      api
        .get<User>('/me')
        .then(applyUser)
        .catch(() => setToken(null))
  }, [applyUser])

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.style.setProperty('--font-ui', fontFor(lang))
  }, [lang])

  useEffect(() => {
    document.documentElement.style.fontSize = `${TEXT_SIZES_PX[textSize] ?? 16}px`
  }, [textSize])

  const setLang = (nextLang: Lang) => {
    localStorage.setItem(LANG_KEY, nextLang)
    setLangState(nextLang)
    setLangChosen(true)
  }

  const setTextSize = (size: number) => {
    localStorage.setItem(TEXT_SIZE_KEY, String(size))
    setTextSizeState(size)
  }

  const t = useCallback<Translate>((key, vars) => translate(lang, key, vars), [lang])

  async function login(personaId: string) {
    const session = await api.post<{ token: string; user: User }>('/login', { persona_id: personaId })
    setToken(session.token)
    queryClient.clear()
    applyUser(session.user)
  }

  function logout() {
    setToken(null)
    setUser(null)
    queryClient.clear()
  }

  function ask(question?: string) {
    setAskSeed(question ?? null)
    setAskOpen(true)
  }

  const value = {
    user,
    meta: meta.data,
    unit,
    setUnit,
    login,
    logout,
    ask,
    askOpen,
    askSeed,
    setAskOpen,
    lang,
    setLang,
    langChosen,
    textSize,
    setTextSize,
    t,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}
