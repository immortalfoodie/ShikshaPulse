import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, ArrowRight, Check, Lightbulb } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CartesianGrid, LabelList, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { EarlyWarningCard } from '../components/EarlyWarning'
import { PageHeader, UnitPicker } from '../components/Layout'
import { Card, Delta, ErrorBox, HelpStrip, InfoTip, Speak, Sparkline, Spinner } from '../components/ui'
import { C, divergingColor, inkOn, pct, signed } from '../lib/format'
import { useReasonText, useWarningText, type ReasonItem } from '../lib/localizedText'
import { unitQs, useApp } from '../state'
import type { ActionSummary, ChildReason, Overview, Trend } from '../types'

function unitName(t: ReturnType<typeof useApp>['t'], o: { unit_type: string; unit: string }) {
  return o.unit_type === 'state'
    ? t('c.wholeState')
    : o.unit_type === 'district'
      ? t('c.districtLabel', { d: o.unit })
      : t('c.blockLabel', { b: o.unit })
}

function Kpis({ o }: { o: Overview }) {
  const { t } = useApp()
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {o.kpis.map((k) => (
        <div key={k.metric} className="panel p-4">
          <div className="flex items-start justify-between gap-1">
            <div className="text-[0.84rem] font-semibold leading-tight text-ink-2">{t(`m.${k.metric}`)}</div>
            <InfoTip text={t(`mi.${k.metric}`)} />
          </div>
          <div className="mt-2 flex items-end justify-between">
            <div className="num-xl">{k.latest === null ? '—' : pct(k.latest)}</div>
            <Sparkline values={k.spark} color={k.higher_is_better ? C.s1 : C.s2} />
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-1 text-[0.82rem]">
            <Delta v={k.change_pp} higherIsBetter={k.higher_is_better} />
            <span className="text-muted">{t('c.stateAvg', { v: pct(k.state_latest) })}</span>
          </div>
          <div className="text-[0.74rem] text-muted">{t('c.since', { y: o.baseline_year })}</div>
        </div>
      ))}
    </div>
  )
}

function TrendCard({ unitTrend, stateTrend, label }: { unitTrend: Trend; stateTrend?: Trend; label: string }) {
  const { t } = useApp()
  const data = unitTrend.points.map((p, i) => ({
    year: p.year,
    unit: p.value,
    state: stateTrend?.points[i]?.value ?? null,
  }))
  return (
    <Card
      title={t('home.trend')}
      sub={t('home.trendSub')}
      info={t('home.trendInfo')}
      right={
        <div className="text-right">
          <div className="eyebrow">{t('home.threeYear')}</div>
          <Delta v={unitTrend.change_pp} className="text-[1.25rem]" />
        </div>
      }
    >
      <div className="h-60">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 26, right: 40, left: 14, bottom: 0 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis
              dataKey="year"
              tick={{ fontSize: 13, fill: C.ink2 }}
              axisLine={{ stroke: C.axis }}
              tickLine={false}
              padding={{ left: 24, right: 24 }}
            />
            <YAxis
              domain={['dataMin - 5', 'dataMax + 4']}
              tick={{ fontSize: 12, fill: C.muted }}
              axisLine={false}
              tickLine={false}
              width={38}
              tickFormatter={(v) => `${Math.round(v)}%`}
            />
            <Tooltip
              formatter={(v) => (v === null ? t('c.nc') : `${v}%`)}
              contentStyle={{ borderRadius: 8, borderColor: '#d6cdbd' }}
            />
            <Legend wrapperStyle={{ fontSize: 13 }} />
            <Line
              type="linear"
              dataKey="unit"
              name={label}
              stroke={C.s1}
              strokeWidth={2.5}
              dot={{ r: 5, fill: C.s1, stroke: C.surface, strokeWidth: 2 }}
              activeDot={{ r: 7 }}
              isAnimationActive={false}
            >
              <LabelList
                dataKey="unit"
                position="top"
                offset={12}
                fontSize={13}
                fontWeight={600}
                fill={C.ink}
                formatter={(v) => (v == null ? '' : `${v}%`)}
              />
            </Line>
            {stateTrend && (
              <Line
                type="linear"
                dataKey="state"
                name={t('c.state')}
                stroke={C.s2}
                strokeWidth={2}
                strokeDasharray="6 4"
                dot={{ r: 4, fill: C.s2, stroke: C.surface, strokeWidth: 2 }}
                isAnimationActive={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {unitTrend.caveats.length > 0 && (
        <div className="mt-1 flex gap-1.5 text-[0.84rem] text-mustard">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {t('q.noncomparable')}
        </div>
      )}
    </Card>
  )
}

function ReviewList({ rows }: { rows: ChildReason[] }) {
  const { setUnit, t } = useApp()
  const reasonText = useReasonText()
  const nav = useNavigate()
  return (
    <Card title={t('home.review')} sub={t('home.reviewSub')} pad={false}>
      <div className="divide-y divide-line">
        {rows.map((r) => (
          <button
            key={r.unit}
            className="grid w-full grid-cols-[1fr_auto_auto] items-start gap-x-3 gap-y-1.5 px-4 py-3.5 text-left transition hover:bg-sunk lg:grid-cols-[8rem_6rem_1fr_auto] lg:gap-4 lg:px-5"
            onClick={() => {
              setUnit({ unit_type: r.unit_type as 'block', unit: r.unit })
              nav(r.unit_type === 'block' ? '/block' : '/')
            }}
          >
            <div>
              <div className="text-[1rem] font-semibold">{r.name}</div>
              <div className="tabnum text-[0.8rem] text-muted">
                {pct(r.baseline)} → {r.comparable ? pct(r.latest) : t('c.nc')}
              </div>
            </div>
            <div className="pt-0.5">
              <Delta v={r.change_pp} />
            </div>
            {r.reason_items.length ? (
              <ul className="reasons order-last col-span-3 lg:order-none lg:col-span-1">
                {r.reason_items.map((x: ReasonItem, i: number) => (
                  <li key={i}>{reasonText(x)}</li>
                ))}
              </ul>
            ) : (
              <span className="order-last col-span-3 text-[0.88rem] text-muted lg:order-none lg:col-span-1">
                {t('home.noAdverse')}
              </span>
            )}
            {r.needs_review ? (
              <span className="tag !border-brick/30 !bg-brick-50 !text-brick">
                <AlertTriangle className="h-3 w-3" /> {t('c.review')}
              </span>
            ) : (
              <span />
            )}
          </button>
        ))}
      </div>
    </Card>
  )
}

type ReviewOrder = { blocks: { block: string; position: number; reason_items: ReasonItem[] }[] }

function InstinctVsEvidence({ district, blocks }: { district: string; blocks: string[] }) {
  const { t } = useApp()
  const reasonText = useReasonText()
  const [picked, setPicked] = useState<string[]>([])
  const [show, setShow] = useState(false)
  const ro = useQuery({
    queryKey: ['review-order', district],
    queryFn: () => api.get<ReviewOrder>(`/review-order?district=${district}`),
    enabled: show,
  })
  const toggle = (b: string) => setPicked((p) => (p.includes(b) ? p.filter((x) => x !== b) : [...p, b]))
  const missed = ro.data
    ? ro.data.blocks.slice(0, Math.max(2, picked.length)).filter((b) => !picked.includes(b.block))
    : []
  return (
    <Card title={t('home.instinct')} sub={t('home.instinctSub')} info={t('home.instinctInfo')}>
      <div className="flex flex-wrap items-center gap-2">
        {blocks.map((b) => (
          <button
            key={b}
            aria-pressed={picked.includes(b)}
            onClick={() => toggle(b)}
            className={clsx('btn !min-h-9 !px-3', picked.includes(b) ? 'btn-primary' : 'btn-quiet')}
          >
            {picked.includes(b) && <Check className="h-4 w-4" />} {b}
          </button>
        ))}
        <button className="btn btn-accent ml-auto" disabled={!picked.length} onClick={() => setShow(true)}>
          {t('home.compare')} <ArrowRight className="h-4 w-4" />
        </button>
      </div>
      {show && ro.isLoading && <Spinner />}
      {show && ro.data && (
        <div className="mt-4">
          {missed.length > 0 && (
            <div className="mb-3 flex items-start gap-2.5 rounded-lg border-l-4 border-s2 bg-saffron-50 p-3 text-[0.93rem]">
              <Lightbulb className="mt-0.5 h-5 w-5 shrink-0 text-mustard" />
              <div>
                <b>{t('home.evidencePoints', { blocks: missed.map((m) => m.block).join(', ') })}</b>
                <ul className="reasons mt-1">
                  {missed[0].reason_items.map((x, i) => (
                    <li key={i}>{reasonText(x)}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          <ol className="divide-y divide-line rounded-lg border border-line">
            {ro.data.blocks.map((b) => (
              <li
                key={b.block}
                className="grid grid-cols-[2rem_1fr_auto] items-start gap-x-3 gap-y-1 px-3 py-2.5 lg:grid-cols-[2rem_7rem_1fr_auto] lg:gap-3"
              >
                <span className="grid h-7 w-7 place-items-center rounded-full bg-sunk text-[0.85rem] font-bold">
                  {b.position}
                </span>
                <span className="pt-0.5 font-semibold">{b.block}</span>
                <ul className="reasons order-last col-span-2 col-start-2 lg:order-none lg:col-span-1 lg:col-start-auto">
                  {b.reason_items.map((x, i) => (
                    <li key={i}>{reasonText(x)}</li>
                  ))}
                </ul>
                {picked.includes(b.block) ? (
                  <span className="tag !text-forest">
                    <Check className="h-3 w-3" /> {t('home.yourPick')}
                  </span>
                ) : (
                  <span />
                )}
              </li>
            ))}
          </ol>
          <p className="mt-2 text-[0.78rem] text-muted">{t('home.method')}</p>
        </div>
      )}
    </Card>
  )
}

type Tile = { district: string; block: string; latest: number | null; change_pp: number | null; comparable: boolean }
function TileMap({ y0 }: { y0: string }) {
  const { setUnit, t, user } = useApp()
  const nav = useNavigate()
  // everyone sees every block for comparison; the officer's own block/district is marked
  const myBlock = user?.role === 'block' ? (user.block ?? user.scope) : null
  const myDistrict = user?.role === 'district' ? user.scope : user?.role === 'block' ? user.district : null
  const tiles = useQuery({ queryKey: ['tiles'], queryFn: () => api.get<Tile[]>('/tiles') })
  if (!tiles.data)
    return (
      <Card title={t('home.tiles')}>
        <Spinner />
      </Card>
    )
  const byD: Record<string, Tile[]> = {}
  tiles.data.forEach((x) => (byD[x.district] ??= []).push(x))
  return (
    <Card title={t('home.tiles')} sub={t('home.tilesSub', { y0 })} info={t('home.tilesInfo')}>
      <div className="space-y-2">
        {Object.entries(byD).map(([d, ts]) => (
          <div key={d}>
            <div className="mb-1 flex items-center gap-2 text-[0.78rem] font-semibold text-ink-2">
              {t('c.districtLabel', { d })}
              {d === myDistrict && !myBlock && <span className="tag !py-0 !text-forest">{t('home.yours')}</span>}
            </div>
            <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-5">
              {ts.map((x) => {
                const bg = x.comparable ? divergingColor(x.change_pp) : '#e7e2d7'
                return (
                  <button
                    key={x.block}
                    onClick={() => {
                      setUnit({ unit_type: 'block', unit: x.block })
                      nav('/block')
                    }}
                    title={`${x.block}: ${x.comparable ? `${x.latest}% (${signed(x.change_pp)} ${t('c.pts')})` : t('c.nc')}`}
                    className={`flex h-14 flex-col items-center justify-center rounded-md text-[0.76rem] font-semibold leading-tight transition hover:ring-2 hover:ring-s2 ${x.block === myBlock ? 'ring-[3px] ring-ink ring-offset-2 ring-offset-surface' : ''}`}
                    style={{
                      background: x.comparable
                        ? bg
                        : 'repeating-linear-gradient(45deg,#ece7dc,#ece7dc 4px,#d9d1c1 4px,#d9d1c1 6px)',
                      color: inkOn(bg),
                    }}
                  >
                    <span className="max-w-full truncate px-1">{x.block}</span>
                    <span className="tabnum text-[0.86rem]">{x.comparable ? signed(x.change_pp) : '—'}</span>
                    {x.block === myBlock && <span className="sr-only">{t('home.yours')}</span>}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-1 text-[0.72rem] text-muted">
        <span>−15</span>
        {[-14, -10, -6, -3, 0, 3, 6, 10, 14].map((v) => (
          <span key={v} className="h-2.5 w-5 rounded-sm" style={{ background: divergingColor(v) }} />
        ))}
        <span>+15 {t('c.pts')}</span>
      </div>
    </Card>
  )
}

export default function CommandCenter() {
  const { unit, meta, ask, t, setUnit } = useApp()
  const nav = useNavigate()
  const warnText = useWarningText()
  const q = unitQs(unit)
  const ov = useQuery({ queryKey: ['overview', q], queryFn: () => api.get<Overview>(`/overview?${q}`) })
  const tr = useQuery({ queryKey: ['trend', q], queryFn: () => api.get<Trend>(`/trend?${q}`) })
  const st = useQuery({ queryKey: ['trend', 'state'], queryFn: () => api.get<Trend>('/trend?unit_type=state') })
  const kids = useQuery({
    queryKey: ['children', q],
    queryFn: () => api.get<ChildReason[]>(`/children-reasons?${q}`),
    enabled: unit.unit_type === 'state' || unit.unit_type === 'district',
  })
  const acts = useQuery({
    queryKey: ['actions-summary'],
    queryFn: () => api.get<{ summary: ActionSummary }>('/actions'),
  })
  if (ov.isError) return <ErrorBox error={ov.error} />
  const o = ov.data
  const name = o ? unitName(t, o) : ''
  const rankLine = o?.rank
    ? t('home.rank', { pos: o.rank.state_position, of: o.rank.state_of, units: t(`home.units.${o.unit_type}`) }) +
      (o.rank.within === 'district' ? t('home.rankBlock', { pos: o.rank.position, of: o.rank.of }) : '')
    : ''
  const speech = o
    ? [
        rankLine,
        ...o.kpis.slice(0, 3).map((k) => `${t(`m.${k.metric}`)} ${k.latest}%, ${signed(k.change_pp)} ${t('c.pts')}`),
      ].join('. ')
    : ''
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow={o ? t('home.sub', { n: o.n_schools, y0: o.baseline_year, y1: o.latest_year }) : ' '}
        title={o ? t('home.title', { unit: name }) : ''}
        right={
          <>
            <UnitPicker />
            <Speak text={speech} />
            <button className="btn btn-primary" onClick={() => ask(t('ask.s1'))}>
              {t('nav.why')}
            </button>
          </>
        }
      />
      <HelpStrip k="help.home" />
      {o?.rank && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border-l-4 border-brick bg-brick-50 px-4 py-3">
          <AlertTriangle className="h-5 w-5 text-brick" />
          <span className="text-[1rem] font-semibold">{rankLine}</span>
          <button
            className="ml-auto inline-flex items-center gap-1 font-semibold text-brick hover:underline"
            onClick={() => nav('/why')}
          >
            {t('home.seeWhy')} <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      )}
      {o ? <Kpis o={o} /> : <Spinner />}
      <div className="grid gap-5 xl:grid-cols-[1.55fr_1fr]">
        <div className="space-y-5">
          {tr.data && (
            <TrendCard unitTrend={tr.data} stateTrend={unit.unit_type === 'state' ? undefined : st.data} label={name} />
          )}
          {kids.data && <ReviewList rows={kids.data} />}
          {unit.unit_type === 'district' && meta?.tree[unit.unit!] && (
            <InstinctVsEvidence district={unit.unit!} blocks={meta.tree[unit.unit!]} />
          )}
        </div>
        <div className="space-y-5">
          <EarlyWarningCard
            unit={unit}
            compact
            onPick={(b) => {
              setUnit({ unit_type: 'block', unit: b })
              nav('/block')
            }}
          />
          {o && <TileMap y0={o.baseline_year} />}
          <Card
            title={t('home.tasks')}
            right={
              <button className="btn btn-quiet" onClick={() => nav('/actions')}>
                {t('c.open')} <ArrowRight className="h-4 w-4" />
              </button>
            }
          >
            {acts.data ? (
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <div className="num-xl">{acts.data.summary.total}</div>
                  <div className="eyebrow mt-1">{t('home.tasks')}</div>
                </div>
                <div>
                  <div className="num-xl text-brick">{acts.data.summary.overdue}</div>
                  <div className="eyebrow mt-1 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    {t('home.overdue')}
                  </div>
                </div>
                <div>
                  <div className="num-xl text-good">{acts.data.summary.implemented_improved}</div>
                  <div className="eyebrow mt-1">{t('home.improved')}</div>
                </div>
              </div>
            ) : (
              <Spinner />
            )}
          </Card>
          {o && (
            <Card title={t('home.confidence')} info={t('home.confidenceInfo')}>
              <div className="flex items-end gap-3">
                <div className="num-xl">
                  {o.quality.confidence}
                  <span className="text-[1rem] font-medium text-muted">/100</span>
                </div>
                <span className="tag">{t(`conf.${o.quality.label}`)}</span>
              </div>
              <ul className="reasons mt-3">
                {o.quality.warning_items.slice(0, 4).map((w, i) => (
                  <li key={i}>{warnText(w)}</li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
