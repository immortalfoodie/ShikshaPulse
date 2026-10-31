// Smarter actions: what happened when this action was used before, and concrete teacher-sharing pairs.
import { useQuery } from '@tanstack/react-query'
import { History, Users } from 'lucide-react'
import { api } from '../api'
import { useApp } from '../state'
import { Card, InfoTip, Spinner } from './ui'

export type TrackRecord = {
  uses: number
  implemented?: number
  not_implemented?: number
  improved?: number
  no_change?: number
  avg_change?: number | null
  simulated?: boolean
}
export type Pair = {
  receiver: { udise_code: string; school_name: string; vacant: number; sanctioned: number }
  donor: { udise_code: string; school_name: string; working: number; load: number }
  scope: 'cluster' | 'block'
  cluster: string
  days_per_week: number
}

export function TrackRecordLine({ tr }: { tr?: TrackRecord }) {
  const { t } = useApp()
  if (!tr) return null
  return (
    <div className="flex items-start gap-1.5 text-[0.84rem] text-ink-2">
      <History className="mt-0.5 h-4 w-4 shrink-0 text-forest" />
      <span>
        <b>{t('act.track')}:</b>{' '}
        {tr.uses
          ? t('act.trackLine', { u: tr.uses, i: tr.improved, c: tr.no_change, x: tr.not_implemented }) +
            (tr.avg_change != null ? t('act.trackAvg', { v: `${tr.avg_change > 0 ? '+' : ''}${tr.avg_change}` }) : '') +
            (tr.simulated ? ` (${t('c.simulated')})` : '')
          : t('act.trackNone')}
      </span>
      <InfoTip text={t('act.trackInfo')} />
    </div>
  )
}

export function PairList({ pairs, limit = 6 }: { pairs: Pair[]; limit?: number }) {
  const { t } = useApp()
  if (!pairs.length) return <div className="text-[0.88rem] text-ink-2">{t('share.none')}</div>
  return (
    <ul className="space-y-2">
      {pairs.slice(0, limit).map((p, i) => (
        <li key={i} className="panel-sunk p-3">
          <div className="text-[0.92rem] font-semibold">
            {t('share.line', { d: p.donor.school_name, r: p.receiver.school_name, days: p.days_per_week })}
          </div>
          <div className="mt-0.5 text-[0.8rem] text-ink-2">
            {t('share.detail', {
              r: p.receiver.school_name,
              v: p.receiver.vacant,
              s: p.receiver.sanctioned,
              d: p.donor.school_name,
              w: p.donor.working,
              l: p.donor.load,
            })}{' '}
            · {t(`share.${p.scope}`)} ({p.cluster})
          </div>
        </li>
      ))}
    </ul>
  )
}

export function SharingCard({ block }: { block: string }) {
  const { t } = useApp()
  const r = useQuery({
    queryKey: ['redistribution', block],
    queryFn: () => api.get<{ pairs: Pair[]; receivers: number }>(`/redistribution?unit_type=block&unit=${block}`),
  })
  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <Users className="h-4 w-4 text-forest" />
          {t('share.title')}
        </span>
      }
      sub={t('share.sub')}
      info={t('share.info')}
    >
      {!r.data ? <Spinner /> : <PairList pairs={r.data.pairs} />}
    </Card>
  )
}
