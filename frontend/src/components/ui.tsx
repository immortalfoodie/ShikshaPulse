// Shared UI primitives (localised). Colours: forest/green + saffron + brick; no blue/purple.
import clsx from 'clsx'
import {
  AlertTriangle, ArrowDownRight, ArrowUpRight, CheckCircle2, ChevronDown, CircleDot, HelpCircle, Info, Loader2, Minus,
  Square, Volume2, X, XCircle,
} from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useSpeaker } from '../speech'
import { useApp } from '../state'

export const C = {
  s1: '#1f7a4a', s2: '#dd8f22', grid: '#e7e0d3', axis: '#cfc6b5', muted: '#8a847b', ink: '#1f1d1a', ink2: '#57524b',
  good: '#1f6b3a', brick: '#b4432a', mustard: '#8a5a0b', mid: '#ece7dc', surface: '#fffdf8',
}

// Diverging change scale: brick (worse) ↔ green (better), warm-gray midpoint. Always paired with signed numbers.
const NEG = ['#f4dcd2', '#e8ae9b', '#d67d63', '#b9533a', '#8c3423']
const POS = ['#dcebdf', '#b2d4ba', '#7fb68f', '#3f8f5d', '#1f6b3a']
export function divergingColor(v: number | null | undefined, max = 15): string {
  if (v === null || v === undefined) return '#e7e2d7'
  if (Math.abs(v) < 1) return C.mid
  const arm = v < 0 ? NEG : POS
  return arm[Math.min(arm.length - 1, Math.floor((Math.abs(v) / max) * arm.length))]
}
export const inkOn = (bg: string) => (['#b9533a', '#8c3423', '#3f8f5d', '#1f6b3a', '#d67d63'].includes(bg) ? '#fffdf8' : '#1f1d1a')
export const SEQ = ['#f3efe4', '#dcebdf', '#b2d4ba', '#7fb68f', '#3f8f5d', '#2a6f47', '#1e4d36']

export const pct = (v: number | null | undefined, d = 1) => (v === null || v === undefined ? '—' : `${Number(v).toFixed(d)}%`)
export const signed = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${v}`)

/** ⓘ — tap/hover explanation. Keyboard accessible. */
export function InfoTip({ text, label, side = 'bottom' }: { text: string; label?: string; side?: 'bottom' | 'top' }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    if (!open) return
    const h = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])
  return (
    <span ref={ref} className="relative inline-flex align-middle">
      <button type="button" aria-label={label ?? text} aria-expanded={open} onClick={(e) => { e.stopPropagation(); setOpen(!open) }}
        onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
        className="grid h-5 w-5 place-items-center rounded-full text-muted hover:bg-sunk hover:text-forest">
        <Info className="h-[15px] w-[15px]" />
      </button>
      {open && (
        <span role="tooltip" className={clsx('absolute left-1/2 z-50 w-72 -translate-x-1/2 rounded-lg border border-line-2 bg-surface p-3 text-left text-[0.82rem] font-normal normal-case leading-snug tracking-normal text-ink-2 shadow-lg',
          side === 'bottom' ? 'top-6' : 'bottom-6')}>
          {text}
        </span>
      )}
    </span>
  )
}

export function Card({ title, sub, info, right, children, className, pad = true }: {
  title?: ReactNode; sub?: ReactNode; info?: string; right?: ReactNode; children: ReactNode; className?: string; pad?: boolean
}) {
  return (
    <section className={clsx('panel', pad && 'p-5', className)}>
      {(title || right) && (
        <header className={clsx('mb-4 flex items-start justify-between gap-3', !pad && 'px-5 pt-5')}>
          <div>
            {title && <h2 className="h-card flex items-center gap-1.5">{title}{info && <InfoTip text={info} />}</h2>}
            {sub && <p className="mt-0.5 text-[0.86rem] text-ink-2">{sub}</p>}
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  )
}

/** Collapsible "How to use this page" strip, text from help.* keys ('|' separated). */
export function HelpStrip({ k }: { k: string }) {
  const { t } = useApp()
  const storageKey = `sp_help_${k}`
  const [open, setOpen] = useState(() => localStorage.getItem(storageKey) !== 'closed')
  const items = t(k).split('|')
  return (
    <div className="no-print rounded-lg border border-dashed border-line-2 bg-sunk">
      <button className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-[0.9rem] font-semibold text-forest"
        onClick={() => { localStorage.setItem(storageKey, open ? 'closed' : 'open'); setOpen(!open) }} aria-expanded={open}>
        <HelpCircle className="h-4 w-4" /> {t('c.help')}
        <ChevronDown className={clsx('ml-auto h-4 w-4 transition', open && 'rotate-180')} />
      </button>
      {open && (
        <ol className="grid gap-1.5 px-4 pb-3 text-[0.88rem] text-ink-2 md:grid-cols-2">
          {items.map((s, i) => (
            <li key={i} className="flex gap-2"><span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-forest text-[0.7rem] font-bold text-surface">{i + 1}</span>{s}</li>
          ))}
        </ol>
      )}
    </div>
  )
}

export function Speak({ text, className, label }: { text: string; className?: string; label?: string }) {
  const { lang, t } = useApp()
  const { speak, stop, speaking, supported } = useSpeaker(lang)
  if (!supported) return null
  return (
    <button type="button" className={clsx('btn btn-quiet', className)} onClick={() => (speaking ? stop() : speak(text))} aria-pressed={speaking}>
      {speaking ? <Square className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />} {label ?? (speaking ? t('c.stop') : t('c.listen'))}
    </button>
  )
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useApp()
  return <div className="flex items-center gap-2 p-6 text-[0.9rem] text-ink-2"><Loader2 className="h-4 w-4 animate-spin" /> {label ?? t('c.loading')}</div>
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error)
  return <div className="flex items-start gap-2 rounded-lg border border-brick/30 bg-brick-50 p-3 text-[0.9rem] text-brick"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {msg}</div>
}

/** Change in points with arrow + sign, so meaning never rides on colour alone. */
export function Delta({ v, higherIsBetter = true, className, unit = true }: { v: number | null | undefined; higherIsBetter?: boolean; className?: string; unit?: boolean }) {
  const { t } = useApp()
  if (v === null || v === undefined) return <span className="text-muted">{t('c.nc')}</span>
  const flat = Math.abs(v) < 0.5
  const good = flat ? null : (v > 0) === higherIsBetter
  const Icon = flat ? Minus : v > 0 ? ArrowUpRight : ArrowDownRight
  return (
    <span className={clsx('tabnum inline-flex items-center gap-0.5 font-semibold', className)} style={{ color: good === null ? C.ink2 : good ? C.good : C.brick }}>
      <Icon className="h-4 w-4" />{v > 0 ? '+' : ''}{v}{unit && <span className="ml-0.5 text-[0.8em] font-medium">{t('c.pts')}</span>}
    </span>
  )
}

const CLS_STYLE: Record<string, string> = {
  HIGH: 'bg-brick-50 text-brick border-brick/25', MEDIUM: 'bg-saffron-50 text-mustard border-s2/30', CONFLICTING: 'bg-sunk text-ink border-line-2',
  INSUFFICIENT_EVIDENCE: 'bg-sunk text-ink-2 border-line-2', CONTEXT: 'bg-forest-50 text-forest border-forest/20', NONE: 'bg-sunk text-muted border-line',
}
export function ClassBadge({ c, withInfo = false }: { c: string; withInfo?: boolean }) {
  const { t } = useApp()
  return (
    <span className="inline-flex items-center gap-1">
      <span className={clsx('tag', CLS_STYLE[c] ?? CLS_STYLE.NONE)}>
        {c === 'HIGH' ? <CircleDot className="h-3 w-3" /> : c === 'INSUFFICIENT_EVIDENCE' ? <HelpCircle className="h-3 w-3" /> : null}{t(`cls.${c}`)}
      </span>
      {withInfo && <InfoTip text={t(`clsi.${c}`)} />}
    </span>
  )
}

export function FindingLabel({ label }: { label: 'observed_fact' | 'associated_signal' | 'unresolved_question' }) {
  const { t } = useApp()
  const map = {
    observed_fact: { icon: CheckCircle2, cls: 'bg-forest-50 text-forest border-forest/20' },
    associated_signal: { icon: ArrowUpRight, cls: 'bg-saffron-50 text-mustard border-s2/30' },
    unresolved_question: { icon: HelpCircle, cls: 'bg-sunk text-ink-2 border-line-2 border-dashed' },
  }
  const m = map[label] ?? map.associated_signal
  const Icon = m.icon
  return (
    <span className="inline-flex items-center gap-1">
      <span className={clsx('tag', m.cls)}><Icon className="h-3 w-3" /> {t(`f.${label}`)}</span>
      <InfoTip text={t(`fi.${label}`)} />
    </span>
  )
}

const OUTCOME_ICON: Record<string, { color: string; icon: typeof CheckCircle2 }> = {
  not_started: { color: C.ink2, icon: Minus }, in_progress: { color: '#2a6247', icon: Loader2 },
  overdue: { color: C.brick, icon: AlertTriangle }, not_implemented: { color: C.brick, icon: XCircle },
  implemented_awaiting_outcome: { color: C.mustard, icon: HelpCircle }, implemented_improved: { color: C.good, icon: CheckCircle2 },
  implemented_no_change: { color: C.mustard, icon: Minus },
}
export function OutcomeBadge({ s }: { s: string }) {
  const { t } = useApp()
  const o = OUTCOME_ICON[s] ?? { color: C.ink2, icon: Minus }
  const Icon = o.icon
  const info = t(`oi.${s}`)
  return (
    <span className="inline-flex items-center gap-1">
      <span className="tag" style={{ color: o.color }}><Icon className="h-3 w-3" /> {t(`o.${s}`)}</span>
      {info !== `oi.${s}` && <InfoTip text={info} />}
    </span>
  )
}

export function VerdictBanner({ verdict }: { verdict: string }) {
  const { t } = useApp()
  const tone: Record<string, string> = {
    EXPLAINED_BY_ASSOCIATED_SIGNALS: 'border-s2 bg-saffron-50', PARTIALLY_EXPLAINED: 'border-s2 bg-saffron-50',
    UNEXPLAINED: 'border-brick bg-brick-50', INSUFFICIENT_EVIDENCE: 'border-line-2 bg-sunk', NON_COMPARABLE: 'border-line-2 bg-sunk',
    STABLE: 'border-s1 bg-good-50',
  }
  return (
    <div className={clsx('rounded-lg border-l-4 p-4', tone[verdict] ?? 'border-line bg-surface')}>
      <div className="text-[1rem] font-semibold">{t(`v.${verdict}`)}</div>
      <div className="mt-0.5 text-[0.9rem] text-ink-2">{t(`vr.${verdict}`)}</div>
    </div>
  )
}

export function Sparkline({ values, color = C.s1 }: { values: (number | null)[]; color?: string }) {
  const v = values.map((x) => (x === null ? NaN : x))
  const ok = v.filter((x) => !Number.isNaN(x))
  if (ok.length < 2) return null
  const min = Math.min(...ok), max = Math.max(...ok), w = 70, h = 24
  const pts = v.map((x, i) => (Number.isNaN(x) ? null : [(i / (v.length - 1)) * (w - 8) + 4, h - 4 - ((x - min) / (max - min || 1)) * (h - 8)]))
  const d = pts.filter(Boolean).map((p, i) => `${i ? 'L' : 'M'}${p![0]},${p![1]}`).join(' ')
  const last = pts.filter(Boolean).at(-1)!
  return (
    <svg width={w} height={h} aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r={3.5} fill={color} stroke={C.surface} strokeWidth={2} />
    </svg>
  )
}

export function Drawer({ open, onClose, title, children, width = 'max-w-xl' }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; width?: string }) {
  const { t } = useApp()
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/30" onClick={onClose}>
      <div className={clsx('h-full w-full overflow-y-auto border-l border-line bg-surface p-6', width)} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal>
        <div className="mb-5 flex items-start justify-between gap-3">
          <h3 className="text-[1.1rem] font-semibold">{title}</h3>
          <button className="btn btn-quiet !min-h-0 !p-1.5" onClick={onClose} aria-label={t('c.close')}><X className="h-4 w-4" /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  const { t } = useApp()
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4" onClick={onClose}>
      <div className="max-h-[88vh] w-full max-w-4xl overflow-y-auto rounded-xl border border-line bg-surface p-6" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal>
        <div className="mb-4 flex items-start justify-between">
          <h3 className="text-[1.1rem] font-semibold">{title}</h3>
          <button className="btn btn-quiet !min-h-0 !p-1.5" onClick={onClose} aria-label={t('c.close')}><X className="h-4 w-4" /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

export type ReasonItem = { kind: string; factor?: string; change?: number | null; cls?: string; pp?: number | null }
/** Render structured reason codes in the user's language. */
export function useReasonText() {
  const { t } = useApp()
  return (r: ReasonItem) => {
    if (r.kind === 'signal') return t('why.signal', { factor: t(`fk.${r.factor}`), change: signed(r.change), cls: t(`cls.${r.cls}`).toLowerCase() })
    if (r.kind === 'decline') return t('why.decline', { pp: r.pp })
    if (r.kind === 'below_expected') return t('why.below_expected', { pp: r.pp })
    if (r.kind === 'unexplained') return t('why.unexplained', { pp: r.pp })
    return t(`why.${r.kind}`)
  }
}

export function useOpenQuestionText() {
  const { t } = useApp()
  return (u: { kind?: string; pp?: number | null; factor?: string; coverage_pct?: number; child?: string; child_verdict?: string; text: string }) => {
    switch (u.kind) {
      case 'remainder': return t('q.remainder', { pp: u.pp })
      case 'insufficient': return t('q.insufficient', { factor: t(`fk.${u.factor}`), cov: u.coverage_pct })
      case 'conflicting': return t('q.conflicting', { factor: t(`fk.${u.factor}`) })
      case 'child': return t(`q.child.${u.child_verdict}`, { child: u.child, pp: u.pp })
      case 'noncomparable': return t('q.noncomparable')
      case 'too_few': return t('q.too_few')
      default: return u.text
    }
  }
}

export function useWarningText() {
  const { t } = useApp()
  return (w: { kind: string; source?: string; pct?: number; n?: number; from_year?: string; to_year?: string }) =>
    w.kind === 'low' ? t('w.low', { source: t(`src.${w.source}`), pct: w.pct })
      : w.kind === 'thin' ? t('w.thin', { n: w.n })
        : t('w.comparability', { from: w.from_year, to: w.to_year })
}
