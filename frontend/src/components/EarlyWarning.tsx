// Early warnings from monthly attendance — shown at the top of the Overview and Block report.
import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { BellRing, CheckCircle2 } from 'lucide-react'
import { api } from '../api'
import { unitQs, useApp, type Unit } from '../state'
import { Card, Spinner } from './ui'

export type EWAlert = { kind: string; block: string; n?: number; of?: number; avg_drop?: number; months: string[]; min_value?: number; n_blocks?: number; severity: 'high' | 'medium' }
export type EWRes = { months?: string[]; alerts: EWAlert[]; schools: { udise_code: string; school_name: string; block: string; drop: number; now: number; before: number }[] }

export function useEwText() {
  const { t } = useApp()
  return (a: EWAlert) => t(`ew.${a.kind}`, { d: a.avg_drop, n: a.n, of: a.of, v: a.min_value, nb: a.n_blocks, block: a.block, months: a.months.join(', ') })
}

export function EarlyWarningCard({ unit, onPick, compact = false }: { unit: Unit; onPick?: (block: string) => void; compact?: boolean }) {
  const { t } = useApp()
  const text = useEwText()
  const q = unitQs(unit)
  const w = useQuery({ queryKey: ['early-warning', q], queryFn: () => api.get<EWRes>(`/early-warning?${q}`) })
  if (!w.data) return <Card title={t('ew.title')}><Spinner /></Card>
  const alerts = w.data.alerts.slice(0, compact ? 3 : 6)
  return (
    <Card title={<span className="flex items-center gap-2"><BellRing className="h-4 w-4 text-mustard" />{t('ew.title')}</span>}
      sub={t('ew.sub', { m: (w.data.months ?? []).join(', ') })} info={t('ew.info')}>
      {alerts.length === 0 ? <div className="flex items-center gap-2 text-good"><CheckCircle2 className="h-4 w-4" />{t('ew.none')}</div> : (
        <ul className="space-y-2">
          {alerts.map((a, i) => (
            <li key={i}>
              <button onClick={() => onPick?.(a.block)} className={clsx('w-full rounded-lg border-l-4 p-3 text-left transition hover:brightness-[.98]',
                a.severity === 'high' ? 'border-brick bg-brick-50' : 'border-s2 bg-saffron-50')}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{a.kind === 'teacher_dip_multi' ? t('c.district') : a.block}</span>
                  <span className={clsx('tag', a.severity === 'high' ? '!text-brick' : '!text-mustard')}>{t(a.severity === 'high' ? 'ew.high' : 'ew.medium')}</span>
                </div>
                <div className="mt-0.5 text-[0.88rem] text-ink-2">{text(a)}</div>
              </button>
            </li>
          ))}
        </ul>
      )}
      {!compact && w.data.schools.length > 0 && (
        <div className="mt-4">
          <div className="eyebrow mb-1">{t('ew.schools')}</div>
          <ul className="divide-y divide-line text-[0.86rem]">
            {w.data.schools.slice(0, 5).map((s) => (
              <li key={s.udise_code} className="flex justify-between gap-2 py-1.5">
                <span className="truncate">{s.school_name} <span className="text-muted">· {s.block}</span></span>
                <span className="tabnum shrink-0 text-brick">{s.before}% → {s.now}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}
