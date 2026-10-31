// Shared UI primitives (localised). Colour and number helpers live in `lib/format.ts`.
import clsx from 'clsx'
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  HelpCircle,
  Info,
  Loader2,
  Minus,
  Square,
  Volume2,
  X,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { C } from '../lib/format'
import { useSpeaker } from '../speech'
import { useApp } from '../state'

/** ⓘ — tap/hover explanation. Keyboard accessible. */
export function InfoTip({ text, label, side = 'bottom' }: { text: string; label?: string; side?: 'bottom' | 'top' }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)

  // Close when clicking anywhere outside the tip.
  useEffect(() => {
    if (!open) return
    const handleOutsideClick = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [open])

  return (
    <span ref={ref} className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label={label ?? text}
        aria-expanded={open}
        onClick={(event) => {
          event.stopPropagation()
          setOpen(!open)
        }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="grid h-5 w-5 place-items-center rounded-full text-muted hover:bg-sunk hover:text-forest"
      >
        <Info className="h-[15px] w-[15px]" />
      </button>
      {open && (
        <span
          role="tooltip"
          className={clsx(
            'absolute left-1/2 z-50 w-72 -translate-x-1/2 rounded-lg border border-line-2 bg-surface p-3 text-left text-[0.82rem] font-normal normal-case leading-snug tracking-normal text-ink-2 shadow-lg',
            side === 'bottom' ? 'top-6' : 'bottom-6',
          )}
        >
          {text}
        </span>
      )}
    </span>
  )
}

/** Panel with an optional title row (title, subtitle, ⓘ tip and right-aligned slot). */
export function Card({
  title,
  sub,
  info,
  right,
  children,
  className,
  pad = true,
}: {
  title?: ReactNode
  sub?: ReactNode
  info?: string
  right?: ReactNode
  children: ReactNode
  className?: string
  pad?: boolean
}) {
  return (
    <section className={clsx('panel', pad && 'p-5', className)}>
      {(title || right) && (
        <header className={clsx('mb-4 flex items-start justify-between gap-3', !pad && 'px-5 pt-5')}>
          <div>
            {title && (
              <h2 className="h-card flex items-center gap-1.5">
                {title}
                {info && <InfoTip text={info} />}
              </h2>
            )}
            {sub && <p className="mt-0.5 text-[0.86rem] text-ink-2">{sub}</p>}
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  )
}

/** Collapsible "How to use this page" strip, text from help.* keys ('|' separated). Open state persists. */
export function HelpStrip({ k: helpKey }: { k: string }) {
  const { t } = useApp()
  const storageKey = `sp_help_${helpKey}`
  const [open, setOpen] = useState(() => localStorage.getItem(storageKey) !== 'closed')
  const steps = t(helpKey).split('|')

  const toggle = () => {
    localStorage.setItem(storageKey, open ? 'closed' : 'open')
    setOpen(!open)
  }

  return (
    <div className="no-print rounded-lg border border-dashed border-line-2 bg-sunk">
      <button
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-[0.9rem] font-semibold text-forest"
        onClick={toggle}
        aria-expanded={open}
      >
        <HelpCircle className="h-4 w-4" /> {t('c.help')}
        <ChevronDown className={clsx('ml-auto h-4 w-4 transition', open && 'rotate-180')} />
      </button>
      {open && (
        <ol className="grid gap-1.5 px-4 pb-3 text-[0.88rem] text-ink-2 md:grid-cols-2">
          {steps.map((step, index) => (
            <li key={index} className="flex gap-2">
              <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-forest text-[0.7rem] font-bold text-surface">
                {index + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

/** Read-aloud toggle button (hidden when the browser has no speech synthesis). */
export function Speak({ text, className, label }: { text: string; className?: string; label?: string }) {
  const { lang, t } = useApp()
  const { speak, stop, speaking, supported } = useSpeaker(lang)
  if (!supported) return null
  const defaultLabel = speaking ? t('c.stop') : t('c.listen')
  return (
    <button
      type="button"
      className={clsx('btn btn-quiet', className)}
      onClick={() => (speaking ? stop() : speak(text))}
      aria-pressed={speaking}
    >
      {speaking ? <Square className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />} {label ?? defaultLabel}
    </button>
  )
}

/** Inline loading indicator. */
export function Spinner({ label }: { label?: string }) {
  const { t } = useApp()
  return (
    <div className="flex items-center gap-2 p-6 text-[0.9rem] text-ink-2">
      <Loader2 className="h-4 w-4 animate-spin" /> {label ?? t('c.loading')}
    </div>
  )
}

/** Displays an error (or any thrown value) as a message box. */
export function ErrorBox({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error)
  return (
    <div className="flex items-start gap-2 rounded-lg border border-brick/30 bg-brick-50 p-3 text-[0.9rem] text-brick">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {message}
    </div>
  )
}

/** Change in points with arrow + sign, so meaning never rides on colour alone. */
export function Delta({
  v: value,
  higherIsBetter = true,
  className,
  unit = true,
}: {
  v: number | null | undefined
  higherIsBetter?: boolean
  className?: string
  unit?: boolean
}) {
  const { t } = useApp()
  if (value === null || value === undefined) return <span className="text-muted">{t('c.nc')}</span>

  const isFlat = Math.abs(value) < 0.5
  const isImprovement = value > 0 === higherIsBetter
  let color = C.ink2
  let Icon: LucideIcon = Minus
  if (!isFlat) {
    color = isImprovement ? C.good : C.brick
    Icon = value > 0 ? ArrowUpRight : ArrowDownRight
  }

  return (
    <span className={clsx('tabnum inline-flex items-center gap-0.5 font-semibold', className)} style={{ color }}>
      <Icon className="h-4 w-4" />
      {value > 0 ? '+' : ''}
      {value}
      {unit && <span className="ml-0.5 text-[0.8em] font-medium">{t('c.pts')}</span>}
    </span>
  )
}

const CLASSIFICATION_STYLE: Record<string, string> = {
  HIGH: 'bg-brick-50 text-brick border-brick/25',
  MEDIUM: 'bg-saffron-50 text-mustard border-s2/30',
  CONFLICTING: 'bg-sunk text-ink border-line-2',
  INSUFFICIENT_EVIDENCE: 'bg-sunk text-ink-2 border-line-2',
  CONTEXT: 'bg-forest-50 text-forest border-forest/20',
  NONE: 'bg-sunk text-muted border-line',
}

const CLASSIFICATION_ICON: Record<string, LucideIcon> = {
  HIGH: CircleDot,
  INSUFFICIENT_EVIDENCE: HelpCircle,
}

/** Evidence-strength badge for a signal classification (HIGH, MEDIUM, …). */
export function ClassBadge({ c: classification, withInfo = false }: { c: string; withInfo?: boolean }) {
  const { t } = useApp()
  const Icon = CLASSIFICATION_ICON[classification]
  return (
    <span className="inline-flex items-center gap-1">
      <span className={clsx('tag', CLASSIFICATION_STYLE[classification] ?? CLASSIFICATION_STYLE.NONE)}>
        {Icon && <Icon className="h-3 w-3" />}
        {t(`cls.${classification}`)}
      </span>
      {withInfo && <InfoTip text={t(`clsi.${classification}`)} />}
    </span>
  )
}

type FindingKind = 'observed_fact' | 'associated_signal' | 'unresolved_question'

const FINDING_STYLE: Record<FindingKind, { icon: LucideIcon; className: string }> = {
  observed_fact: { icon: CheckCircle2, className: 'bg-forest-50 text-forest border-forest/20' },
  associated_signal: { icon: ArrowUpRight, className: 'bg-saffron-50 text-mustard border-s2/30' },
  unresolved_question: { icon: HelpCircle, className: 'bg-sunk text-ink-2 border-line-2 border-dashed' },
}

/** Labels a finding as fact, associated signal or open question. */
export function FindingLabel({ label }: { label: FindingKind }) {
  const { t } = useApp()
  const style = FINDING_STYLE[label] ?? FINDING_STYLE.associated_signal
  const Icon = style.icon
  return (
    <span className="inline-flex items-center gap-1">
      <span className={clsx('tag', style.className)}>
        <Icon className="h-3 w-3" /> {t(`f.${label}`)}
      </span>
      <InfoTip text={t(`fi.${label}`)} />
    </span>
  )
}

const OUTCOME_STYLE: Record<string, { color: string; icon: LucideIcon }> = {
  not_started: { color: C.ink2, icon: Minus },
  in_progress: { color: '#2a6247', icon: Loader2 },
  overdue: { color: C.brick, icon: AlertTriangle },
  not_implemented: { color: C.brick, icon: XCircle },
  implemented_awaiting_outcome: { color: C.mustard, icon: HelpCircle },
  implemented_improved: { color: C.good, icon: CheckCircle2 },
  implemented_no_change: { color: C.mustard, icon: Minus },
}
const DEFAULT_OUTCOME_STYLE = { color: C.ink2, icon: Minus }

/** Badge for an action's outcome status, with an ⓘ tip when a translation exists. */
export function OutcomeBadge({ s: status }: { s: string }) {
  const { t } = useApp()
  const style = OUTCOME_STYLE[status] ?? DEFAULT_OUTCOME_STYLE
  const Icon = style.icon
  const infoKey = `oi.${status}`
  const info = t(infoKey)
  return (
    <span className="inline-flex items-center gap-1">
      <span className="tag" style={{ color: style.color }}>
        <Icon className="h-3 w-3" /> {t(`o.${status}`)}
      </span>
      {info !== infoKey && <InfoTip text={info} />}
    </span>
  )
}

const VERDICT_TONE: Record<string, string> = {
  EXPLAINED_BY_ASSOCIATED_SIGNALS: 'border-s2 bg-saffron-50',
  PARTIALLY_EXPLAINED: 'border-s2 bg-saffron-50',
  UNEXPLAINED: 'border-brick bg-brick-50',
  INSUFFICIENT_EVIDENCE: 'border-line-2 bg-sunk',
  NON_COMPARABLE: 'border-line-2 bg-sunk',
  STABLE: 'border-s1 bg-good-50',
}

/** Headline verdict of a diagnosis with its one-line explanation. */
export function VerdictBanner({ verdict }: { verdict: string }) {
  const { t } = useApp()
  return (
    <div className={clsx('rounded-lg border-l-4 p-4', VERDICT_TONE[verdict] ?? 'border-line bg-surface')}>
      <div className="text-[1rem] font-semibold">{t(`v.${verdict}`)}</div>
      <div className="mt-0.5 text-[0.9rem] text-ink-2">{t(`vr.${verdict}`)}</div>
    </div>
  )
}

const SPARK_WIDTH = 70
const SPARK_HEIGHT = 24
const SPARK_PADDING = 4

/** Tiny trend line; gaps (null) are skipped. Renders nothing with fewer than two points. */
export function Sparkline({ values, color = C.s1 }: { values: (number | null)[]; color?: string }) {
  const isKnown = (value: number | null): value is number => value !== null && !Number.isNaN(value)
  const known = values.filter(isKnown)
  if (known.length < 2) return null

  const min = Math.min(...known)
  const max = Math.max(...known)
  const range = max - min || 1
  const points = values.flatMap((value, index) => {
    if (!isKnown(value)) return []
    const x = (index / (values.length - 1)) * (SPARK_WIDTH - 2 * SPARK_PADDING) + SPARK_PADDING
    const y = SPARK_HEIGHT - SPARK_PADDING - ((value - min) / range) * (SPARK_HEIGHT - 2 * SPARK_PADDING)
    return [[x, y] as const]
  })
  const path = points.map(([x, y], index) => `${index ? 'L' : 'M'}${x},${y}`).join(' ')
  const [lastX, lastY] = points[points.length - 1]

  return (
    <svg width={SPARK_WIDTH} height={SPARK_HEIGHT} aria-hidden>
      <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" />
      <circle cx={lastX} cy={lastY} r={3.5} fill={color} stroke={C.surface} strokeWidth={2} />
    </svg>
  )
}

/** Title row with a close button, shared by Drawer and Modal. */
function DialogHeader({ title, onClose, className }: { title: ReactNode; onClose: () => void; className: string }) {
  const { t } = useApp()
  return (
    <div className={className}>
      <h3 className="text-[1.1rem] font-semibold">{title}</h3>
      <button className="btn btn-quiet !min-h-0 !p-1.5" onClick={onClose} aria-label={t('c.close')}>
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

type DialogProps = { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }

/** Right-hand slide-over panel; clicking the backdrop closes it. */
export function Drawer({ open, onClose, title, children, width = 'max-w-xl' }: DialogProps & { width?: string }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/30" onClick={onClose}>
      <div
        className={clsx('h-full w-full overflow-y-auto border-l border-line bg-surface p-6', width)}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal
      >
        <DialogHeader title={title} onClose={onClose} className="mb-5 flex items-start justify-between gap-3" />
        {children}
      </div>
    </div>
  )
}

/** Centred modal dialog; clicking the backdrop closes it. */
export function Modal({ open, onClose, title, children }: DialogProps) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4" onClick={onClose}>
      <div
        className="max-h-[88vh] w-full max-w-4xl overflow-y-auto rounded-xl border border-line bg-surface p-6"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal
      >
        <DialogHeader title={title} onClose={onClose} className="mb-4 flex items-start justify-between" />
        {children}
      </div>
    </div>
  )
}
