// Helpers shared by the action tracker pages.
import { useApp } from '../state'
import type { Action } from '../types'

/** Kanban columns on the Actions board, in display order. */
export const ACTION_COLUMNS = ['todo', 'progress', 'overdue', 'verify', 'closed'] as const
export type ActionColumn = (typeof ACTION_COLUMNS)[number]

const CLOSED_STATUSES = ['verified', 'closed_not_implemented']

/** Which board column an action belongs in. Closed and verification states win over "overdue". */
export function actionColumn(action: Action): ActionColumn {
  if (CLOSED_STATUSES.includes(action.status)) return 'closed'
  if (action.status === 'awaiting_verification') return 'verify'
  if (action.overdue) return 'overdue'
  if (action.status === 'in_progress') return 'progress'
  return 'todo'
}

/** Alias kept for callers that used `colOf`. */
export const colOf = actionColumn

/** Localised action title: the translated intervention name plus the unit, else the stored title. */
export function useActionTitle() {
  const { t } = useApp()
  return (action: Pick<Action, 'intervention_key' | 'title' | 'unit' | 'unit_name'>) => {
    const key = action.intervention_key ? `iv.${action.intervention_key}` : ''
    const hasTranslation = key && t(key) !== key
    return hasTranslation ? `${t(key)} — ${action.unit_name ?? action.unit}` : action.title
  }
}
