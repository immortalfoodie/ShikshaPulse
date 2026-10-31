// Hooks that render structured server codes (reasons, open questions, data warnings) in the user's language.
import { useApp } from '../state'
import { signed } from './format'

/** A structured reason code returned by the diagnosis API. */
export type ReasonItem = { kind: string; factor?: string; change?: number | null; cls?: string; pp?: number | null }

/** An unresolved question attached to a diagnosis. */
export type OpenQuestion = {
  kind?: string
  pp?: number | null
  factor?: string
  coverage_pct?: number
  child?: string
  child_verdict?: string
  text: string
}

/** A data-quality warning attached to a diagnosis. */
export type DataWarning = {
  kind: string
  source?: string
  pct?: number
  n?: number
  from_year?: string
  to_year?: string
}

/** Render structured reason codes in the user's language. */
export function useReasonText() {
  const { t } = useApp()
  return (reason: ReasonItem) => {
    switch (reason.kind) {
      case 'signal':
        return t('why.signal', {
          factor: t(`fk.${reason.factor}`),
          change: signed(reason.change),
          cls: t(`cls.${reason.cls}`).toLowerCase(),
        })
      case 'decline':
      case 'below_expected':
      case 'unexplained':
        return t(`why.${reason.kind}`, { pp: reason.pp })
      default:
        return t(`why.${reason.kind}`)
    }
  }
}

/** Render an open question in the user's language, falling back to the server text. */
export function useOpenQuestionText() {
  const { t } = useApp()
  return (question: OpenQuestion) => {
    switch (question.kind) {
      case 'remainder':
        return t('q.remainder', { pp: question.pp })
      case 'insufficient':
        return t('q.insufficient', { factor: t(`fk.${question.factor}`), cov: question.coverage_pct })
      case 'conflicting':
        return t('q.conflicting', { factor: t(`fk.${question.factor}`) })
      case 'child':
        return t(`q.child.${question.child_verdict}`, { child: question.child, pp: question.pp })
      case 'noncomparable':
        return t('q.noncomparable')
      case 'too_few':
        return t('q.too_few')
      default:
        return question.text
    }
  }
}

/** Render a data-quality warning in the user's language. */
export function useWarningText() {
  const { t } = useApp()
  return (warning: DataWarning) => {
    switch (warning.kind) {
      case 'low':
        return t('w.low', { source: t(`src.${warning.source}`), pct: warning.pct })
      case 'thin':
        return t('w.thin', { n: warning.n })
      default:
        return t('w.comparability', { from: warning.from_year, to: warning.to_year })
    }
  }
}
