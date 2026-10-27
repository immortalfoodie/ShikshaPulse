import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowRight, FileSpreadsheet, Scale } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { EarlyWarningCard } from '../components/EarlyWarning'
import { SharingCard } from '../components/Smart'
import { PageHeader, UnitPicker } from '../components/Layout'
import { C, Card, ClassBadge, Delta, ErrorBox, HelpStrip, InfoTip, Modal, Spinner, VerdictBanner, pct, signed, useOpenQuestionText } from '../components/ui'
import { useApp, useFocusBlock } from '../state'
import type { Diagnosis, Overview, RadarSchool } from '../types'

type Expected = {
  ok: boolean; years: { year: string; actual: number; expected: number; residual: number }[]; latest: { residual: number; expected: number; actual: number }
  category: string; pattern: string | null; residual_change: number | null
  contributions: { feature: string; label: string; effect_pp: number }[]; model: { r2_heldout: number; mae_heldout: number }
}
const CAT_TONE: Record<string, string> = {
  underperforming_conditions: 'border-brick bg-brick-50', outperforming_conditions: 'border-s1 bg-good-50',
  conditions_constrained: 'border-s2 bg-saffron-50', in_line: 'border-line-2 bg-sunk',
}

function ExpectedCard({ block }: { block: string }) {
  const { t } = useApp()
  const e = useQuery({ queryKey: ['expected', block], queryFn: () => api.get<Expected>(`/expected?unit_type=block&unit=${block}`) })
  if (!e.data) return <Card title={t('block.expected')}><Spinner /></Card>
  if (!e.data.ok) return <Card title={t('block.expected')}>{t('c.noData')}</Card>
  const x = e.data
  const interpKey = x.category === 'underperforming_conditions' ? `interp.underperforming_conditions.${x.pattern ?? 'persistent'}` : `interp.${x.category}`
  const contribs = x.contributions.map((c) => ({ ...c, name: t(`feat.${c.feature}`) }))
  return (
    <Card title={<span className="flex items-center gap-2"><Scale className="h-4 w-4 text-forest" />{t('block.expected')}</span>} sub={t('block.expectedSub')} info={t('block.expectedInfo')}>
      <div className={clsx('mb-4 rounded-lg border-l-4 p-3.5', CAT_TONE[x.category])}>
        <div className="font-semibold">{t(`cat.${x.category}`)}</div>
        <div className="text-[0.9rem] text-ink-2">{t(interpKey, { res: Math.abs(x.latest.residual), chg: Math.abs(x.residual_change ?? 0), y0: x.years[0]?.year })}</div>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <div className="h-56">
          <ResponsiveContainer>
            <LineChart data={x.years} margin={{ top: 20, right: 24, left: 0 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="year" tick={{ fontSize: 12, fill: C.ink2 }} />
              <YAxis domain={['dataMin - 5', 'dataMax + 4']} tick={{ fontSize: 12, fill: C.muted }} width={38} tickFormatter={(v) => `${Math.round(v)}%`} />
              <Tooltip formatter={(v) => `${v}%`} contentStyle={{ borderRadius: 8, borderColor: '#d6cdbd' }} />
              <Legend wrapperStyle={{ fontSize: 12.5 }} />
              <Line dataKey="expected" name={t('block.expectedLine')} stroke={C.s2} strokeDasharray="6 4" strokeWidth={2} dot={{ r: 4, fill: C.s2 }} isAnimationActive={false} />
              <Line dataKey="actual" name={t('block.actualLine')} stroke={C.s1} strokeWidth={2.5} dot={{ r: 5, fill: C.s1, stroke: C.surface, strokeWidth: 2 }} isAnimationActive={false}>
                <LabelList dataKey="actual" position="bottom" offset={10} fontSize={12} fontWeight={600} fill={C.ink} formatter={(v) => `${v}%`} />
              </Line>
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div>
          <div className="eyebrow mb-1">{t('block.effects')}</div>
          <div className="h-52">
            <ResponsiveContainer>
              <BarChart data={contribs} layout="vertical" margin={{ left: 6, right: 34 }}>
                <CartesianGrid stroke={C.grid} horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: C.muted }} domain={[(m: number) => Math.min(-1, Math.floor(m)), (m: number) => Math.max(1, Math.ceil(m))]} />
                <YAxis type="category" dataKey="name" width={128} tick={{ fontSize: 12 }} />
                <ReferenceLine x={0} stroke={C.axis} />
                <Tooltip formatter={(v) => `${v} ${t('c.pts')}`} />
                <Bar dataKey="effect_pp" name={t('c.change')} radius={4} barSize={14}>
                  {contribs.map((c) => <Cell key={c.feature} fill={(c.effect_pp ?? 0) < 0 ? '#d67d63' : C.s1} />)}
                  <LabelList dataKey="effect_pp" position="right" fontSize={11} fill={C.ink} formatter={(v) => signed(Number(v))} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      <div className="mt-2 text-[0.76rem] text-muted">R² {x.model.r2_heldout} · ± {x.model.mae_heldout} {t('c.pts')}</div>
    </Card>
  )
}

type Profile = { udise_code: string; school_name: string; years: Record<string, number | string | null>[] }
type Lineage = { records: Record<string, Record<string, string | number | null>[]>; files: Record<string, { transforms: string[] }> }

export function SchoolModal({ udise, onClose }: { udise: string | null; onClose: () => void }) {
  const { t } = useApp()
  const p = useQuery({ queryKey: ['school', udise], queryFn: () => api.get<Profile>(`/school/${udise}`), enabled: !!udise })
  const l = useQuery({ queryKey: ['lineage', udise], queryFn: () => api.get<Lineage>(`/lineage?udise=${udise}`), enabled: !!udise })
  const [tab, setTab] = useState<'profile' | 'lineage'>('profile')
  return (
    <Modal open={!!udise} onClose={onClose} title={p.data ? `${p.data.school_name} · ${p.data.udise_code}` : ''}>
      <div className="seg mb-4">
        <button aria-pressed={tab === 'profile'} onClick={() => setTab('profile')}>{t('school.profile')}</button>
        <button aria-pressed={tab === 'lineage'} onClick={() => setTab('lineage')}>{t('school.lineage')}</button>
      </div>
      {udise && <a className="btn btn-quiet mb-4 ml-2" href={`/report-card/${udise}`}>{t('rc.open')}</a>}
      {tab === 'profile' && p.data && (
        <table className="w-full text-[0.9rem] tabnum">
          <thead className="text-left text-[0.8rem] text-muted"><tr>{[t('school.year'), t('m.numeracy'), t('m.literacy'), t('m.student_att'), t('m.teacher_att'), t('m.maths_vacancy'), t('m.infra_index'), t('school.instrument')].map((h) => <th key={h} className="py-1 pr-2 font-medium">{h}</th>)}</tr></thead>
          <tbody>{p.data.years.map((y) => (
            <tr key={String(y.academic_year)} className="border-t border-line">
              <td className="py-2">{y.academic_year}</td><td>{pct(y.numeracy as number)}</td><td>{pct(y.literacy as number)}</td><td>{pct(y.student_att as number)}</td>
              <td>{pct(y.teacher_att as number)}</td><td>{y.maths_vacancy === null ? '—' : `${y.maths_vacant}/${y.maths_sanctioned}`}</td><td>{pct(y.infra_index as number, 0)}</td>
              <td className="text-[0.78rem]">{y.assessment_type} ({y.scoring_scale})</td>
            </tr>
          ))}</tbody>
        </table>
      )}
      {tab === 'lineage' && l.data && (
        <div className="space-y-4 text-[0.8rem]">
          <p className="text-ink-2">{t('school.lineageInfo')}</p>
          {Object.entries(l.data.records).map(([tb, rows]) => (
            <div key={tb}>
              <div className="eyebrow mb-1">{tb}</div>
              <div className="max-h-40 overflow-auto rounded-md border border-line">
                <table className="w-full"><thead className="sticky top-0 bg-sunk text-left text-muted"><tr>{rows[0] && Object.keys(rows[0]).map((k) => <th key={k} className="px-2 py-1 font-medium">{k.replace(/^_/, '')}</th>)}</tr></thead>
                  <tbody>{rows.slice(0, 12).map((r, i) => <tr key={i} className="border-t border-line">{Object.values(r).map((v, j) => <td key={j} className="px-2 py-0.5">{String(v ?? '')}</td>)}</tr>)}</tbody></table>
              </div>
            </div>
          ))}
          <div><div className="eyebrow mb-1">{t('school.transforms')}</div>
            {Object.entries(l.data.files).map(([f, v]) => <div key={f} className="mb-1"><FileSpreadsheet className="mr-1 inline h-3.5 w-3.5 text-s1" /><b>{f}</b>: {v.transforms.join(' · ')}</div>)}</div>
        </div>
      )}
    </Modal>
  )
}

export default function Block() {
  const { ask, t } = useApp()
  const qText = useOpenQuestionText()
  const nav = useNavigate()
  const [school, setSchool] = useState<string | null>(null)
  const block = useFocusBlock()
  const ov = useQuery({ queryKey: ['overview', 'block', block], queryFn: () => api.get<Overview>(`/overview?unit_type=block&unit=${block}`), enabled: !!block })
  const dg = useQuery({ queryKey: ['diagnose', 'block', block], queryFn: () => api.get<Diagnosis>(`/diagnose?unit_type=block&unit=${block}`), enabled: !!block })
  const rd = useQuery({ queryKey: ['radar', 'block', block], queryFn: () => api.get<{ schools: RadarSchool[]; n_flagged: number; n_schools: number }>(`/radar?unit_type=block&unit=${block}&min_flags=2`), enabled: !!block })
  if (!block) return <Spinner />
  if (ov.isError) return <ErrorBox error={ov.error} />
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={ov.data ? t('block.sub', { n: ov.data.n_schools, c: ov.data.quality.confidence }) : ' '} title={t('block.title', { block })}
        right={<><UnitPicker blocksOnly block={block} /><button className="btn btn-quiet" onClick={() => nav('/peers')}>{t('block.peers')}</button><button className="btn btn-primary" onClick={() => ask(`${t('ask.s1').replace(/\?$/, '')} — ${block}?`)}>{t('c.askAI')}</button></>} />
      <HelpStrip k="help.block" />
      {ov.data && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
          {ov.data.kpis.map((k) => (
            <div key={k.metric} className="panel p-4">
              <div className="flex items-start justify-between gap-1"><div className="text-[0.82rem] font-semibold leading-tight text-ink-2">{t(`m.${k.metric}`)}</div><InfoTip text={t(`mi.${k.metric}`)} /></div>
              <div className="mt-1.5 text-[1.5rem] font-bold">{k.latest === null ? '—' : pct(k.latest)}</div>
              <Delta v={k.change_pp} higherIsBetter={k.higher_is_better} className="text-[0.82rem]" />
            </div>
          ))}
        </div>
      )}
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <ExpectedCard block={block} />
        {dg.data && (
          <Card title={t('block.signals')} right={<button className="btn btn-quiet" onClick={() => nav('/why')}>{t('block.graph')} <ArrowRight className="h-4 w-4" /></button>}>
            <VerdictBanner verdict={dg.data.verdict} />
            <ul className="mt-3 divide-y divide-line">
              {dg.data.signals.filter((s) => s.classification !== 'NONE').map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-2 py-2 text-[0.92rem]">
                  <span>{t(`fk.${s.factor}`)} {s.change !== undefined && <span className="text-[0.82rem] text-ink-2">({signed(s.change)} {t('c.pts')})</span>}</span>
                  <ClassBadge c={s.classification} withInfo />
                </li>
              ))}
            </ul>
            {dg.data.unresolved.map((u) => <div key={u.id} className="mt-2 rounded-md border border-dashed border-line-2 bg-sunk p-2.5 text-[0.86rem]">{qText(u)}</div>)}
          </Card>
        )}
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <EarlyWarningCard unit={{ unit_type: 'block', unit: block }} />
        <SharingCard block={block} />
      </div>
      <Card title={t('block.investigate')} sub={rd.data ? t('block.investigateSub', { n: rd.data.n_flagged, total: rd.data.n_schools }) : ''}
        right={<button className="btn btn-quiet" onClick={() => nav('/radar')}>{t('nav.radar')} <ArrowRight className="h-4 w-4" /></button>}>
        {rd.data ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {rd.data.schools.slice(0, 9).map((s) => (
              <button key={s.udise_code} className="panel-sunk p-3.5 text-left hover:border-forest" onClick={() => setSchool(s.udise_code)}>
                <div className="flex items-start justify-between gap-2"><span className="font-semibold leading-snug">{s.school_name}</span><span className="tag shrink-0">{t('block.flags', { n: s.n_flags })}</span></div>
                <ul className="reasons mt-2">{s.flags.map((f) => <li key={f}>{t(`r.${f}`)}</li>)}</ul>
              </button>
            ))}
          </div>
        ) : <Spinner />}
      </Card>
      <SchoolModal udise={school} onClose={() => setSchool(null)} />
    </div>
  )
}
