import { useQuery } from '@tanstack/react-query'
import { Vote } from 'lucide-react'
import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import { PageHeader, UnitPicker } from '../components/Layout'
import { Card, ErrorBox, HelpStrip, Speak, Spinner } from '../components/ui'
import { C, pct } from '../lib/format'
import { useApp, useFocusBlock } from '../state'

type PeerRow = {
  block: string
  district: string
  distance: number
  baseline: number
  latest: number
  change_pp: number
  teacher_days_lost: number
}
type PeerRes = {
  block: string
  unit: PeerRow
  peers: PeerRow[]
  election_threshold_days: number
  baseline_year: string
  latest_year: string
  summary: { low: number; high: number; median: number; unit_change: number; gap_vs_median: number } | null
}

export default function Peers() {
  const { ask, t } = useApp()
  const [election, setElection] = useState(true)
  const [other, setOther] = useState(true)
  const block = useFocusBlock()
  const p = useQuery({
    queryKey: ['peers', block, election, other],
    queryFn: () => api.get<PeerRes>(`/peers?block=${block}&election_only=${election}&other_districts=${other}`),
    enabled: !!block,
  })
  if (p.isError) return <ErrorBox error={p.error} />
  const data = p.data ? [{ ...p.data.unit, me: true }, ...p.data.peers.map((x) => ({ ...x, me: false }))] : []
  const s = p.data?.summary
  const summary =
    s && p.data
      ? t('peers.summary', {
          n: p.data.peers.length,
          lo: s.low,
          hi: s.high,
          med: s.median,
          block: p.data.block,
          u: s.unit_change,
          gap: Math.abs(s.gap_vs_median),
          dir: t(s.gap_vs_median < 0 ? 'peers.below' : 'peers.above'),
        })
      : ''
  const interp = s && election ? t(s.gap_vs_median <= -4 ? 'peers.big' : 'peers.small') : ''
  return (
    <div className="space-y-5">
      <PageHeader
        title={t('peers.title')}
        sub={t('peers.sub')}
        right={
          <>
            <UnitPicker blocksOnly block={block} />
            <label className="btn btn-quiet cursor-pointer">
              <input
                type="checkbox"
                checked={election}
                onChange={(e) => setElection(e.target.checked)}
                className="accent-[#1e4d36]"
              />{' '}
              <Vote className="h-4 w-4" /> {t('peers.election')}
            </label>
            <label className="btn btn-quiet cursor-pointer">
              <input
                type="checkbox"
                checked={other}
                onChange={(e) => setOther(e.target.checked)}
                className="accent-[#1e4d36]"
              />{' '}
              {t('peers.other')}
            </label>
          </>
        }
      />
      <HelpStrip k="help.peers" />
      {!p.data ? (
        <Spinner />
      ) : (
        <>
          {s ? (
            <div className="panel border-l-4 !border-l-s2 p-5">
              <p className="text-[1.1rem] font-semibold leading-snug">{summary}</p>
              {interp && <p className="mt-1.5 text-[0.95rem] text-ink-2">{interp}</p>}
              <div className="mt-3 flex flex-wrap gap-2">
                <Speak text={`${summary} ${interp}`} />
                <button className="btn btn-quiet" onClick={() => ask(t('ask.s3').replace('Poti', p.data!.block))}>
                  {t('c.askAI')}
                </button>
              </div>
            </div>
          ) : (
            <div className="panel p-4 text-[0.95rem]">{t('peers.none')}</div>
          )}
          <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
            <Card
              title={t('peers.chart', { y0: p.data.baseline_year, y1: p.data.latest_year })}
              sub={t('peers.chartSub', { block: p.data.block })}
              info={t('peers.info')}
            >
              <div className="h-80">
                <ResponsiveContainer>
                  <BarChart data={data} layout="vertical" margin={{ left: 10, right: 30 }}>
                    <CartesianGrid stroke={C.grid} horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 12, fill: C.muted }}
                      domain={[
                        (m: number) => Math.min(0, Math.floor(m - 2)),
                        (m: number) => Math.max(0, Math.ceil(m + 1)),
                      ]}
                    />
                    <YAxis type="category" dataKey="block" width={92} tick={{ fontSize: 13 }} />
                    <ReferenceLine x={0} stroke={C.axis} />
                    {s && (
                      <ReferenceLine
                        x={s.median}
                        stroke={C.s2}
                        strokeDasharray="6 4"
                        label={{
                          value: t('peers.median', { v: s.median }),
                          fontSize: 11,
                          fill: C.mustard,
                          position: 'top',
                        }}
                      />
                    )}
                    <Tooltip formatter={(v) => `${v} ${t('c.pts')}`} />
                    <Bar dataKey="change_pp" name={t('c.change')} radius={4} barSize={20}>
                      {data.map((d) => (
                        <Cell key={d.block} fill={d.me ? C.brick : C.s1} />
                      ))}
                      <LabelList
                        dataKey="change_pp"
                        position={data.every((d) => d.change_pp <= 0) ? 'left' : 'right'}
                        fontSize={12}
                        fontWeight={600}
                        fill={C.ink}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card title={t('peers.who')} info={t('peers.info')}>
              <table className="w-full text-[0.88rem] tabnum">
                <thead className="text-left text-[0.78rem] text-muted">
                  <tr>
                    <th className="py-1 font-medium">{t('peers.th.block')}</th>
                    <th className="font-medium">{t('peers.th.district')}</th>
                    <th className="text-right font-medium">{t('peers.th.start')}</th>
                    <th className="text-right font-medium">{t('peers.th.days')}</th>
                    <th className="text-right font-medium">{t('peers.th.sim')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((r) => (
                    <tr key={r.block} className={`border-t border-line ${r.me ? 'font-semibold' : ''}`}>
                      <td className="py-2">{r.block}</td>
                      <td>{r.district}</td>
                      <td className="text-right">{pct(r.baseline)}</td>
                      <td className="text-right">{r.teacher_days_lost}</td>
                      <td className="text-right">{r.me ? '—' : r.distance}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-[0.78rem] text-muted">{t('peers.closeNote')}</p>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
