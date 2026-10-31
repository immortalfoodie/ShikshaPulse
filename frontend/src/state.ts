// App-wide state contract and hooks: persona, selected area, language, text size, Ask panel.
// The provider component that owns this state lives in `AppProvider.tsx`.
import { useQuery } from '@tanstack/react-query'
import { createContext, useContext } from 'react'
import { api } from './api'
import type { Key, Lang } from './i18n'
import type { ChildReason, Meta, User } from './types'

/** The administrative area currently in focus (state → district → block → school). */
export type Unit = { unit_type: 'state' | 'district' | 'block' | 'school'; unit: string | null }

/** Translate a key into the active language, interpolating `{var}` placeholders. */
export type Translate = (key: Key | string, vars?: Record<string, string | number | null | undefined>) => string

/** Everything exposed through {@link useApp}. */
export type AppContextValue = {
  user: User | null
  meta: Meta | undefined
  unit: Unit
  setUnit: (unit: Unit) => void
  login: (personaId: string) => Promise<void>
  logout: () => void
  /** Open the Ask panel, optionally pre-filled with a question. */
  ask: (question?: string) => void
  askOpen: boolean
  askSeed: string | null
  setAskOpen: (open: boolean) => void
  lang: Lang
  setLang: (lang: Lang) => void
  /** True once the user has explicitly picked a language. */
  langChosen: boolean
  /** Index into the text-size scale (0 = default). */
  textSize: number
  setTextSize: (size: number) => void
  t: Translate
}

export const AppContext = createContext<AppContextValue | null>(null)

/** Access app-wide state. Must be used inside `<AppProvider>`. */
export function useApp(): AppContextValue {
  const context = useContext(AppContext)
  if (!context) throw new Error('useApp outside provider')
  return context
}

/** Shorthand for the translate function. */
export const useT = () => useApp().t

/** Build the `unit_type=…&unit=…` query string for a unit. */
export const unitQs = (unit: Unit) =>
  `unit_type=${unit.unit_type}${unit.unit ? `&unit=${encodeURIComponent(unit.unit)}` : ''}`

const childrenReasonsQuery = (query: string) => ({
  queryKey: ['children', query],
  queryFn: () => api.get<ChildReason[]>(`/children-reasons?${query}`),
})

/** Block shown on block-level pages: the selected block, else the first block needing review in the selected area. */
export function useFocusBlock(): string | null {
  const { unit, meta } = useApp()
  const children = useQuery({
    ...childrenReasonsQuery(unitQs(unit)),
    enabled: unit.unit_type === 'district' || unit.unit_type === 'state',
  })
  // At state level the first child is a district: look one level down for its most affected block
  // (instead of the alphabetically first block, which says nothing about need).
  const topDistrict = children.data?.[0]?.unit_type === 'district' ? children.data[0].unit : null
  const grandchildren = useQuery({
    queryKey: ['children', `unit_type=district&unit=${topDistrict}`],
    queryFn: () =>
      api.get<ChildReason[]>(`/children-reasons?unit_type=district&unit=${encodeURIComponent(topDistrict!)}`),
    enabled: !!topDistrict,
  })

  if (unit.unit_type === 'block') return unit.unit
  if (!meta || !children.data) return null
  const first = children.data[0]
  if (!first) return Object.values(meta.tree)[0]?.[0] ?? null
  if (first.unit_type === 'block') return first.unit
  const topBlock = grandchildren.data?.[0]?.unit
  if (topBlock != null) return topBlock
  if (grandchildren.isLoading) return null
  return meta.tree[first.unit]?.[0] ?? null
}
