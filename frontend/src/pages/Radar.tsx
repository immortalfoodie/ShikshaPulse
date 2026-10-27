import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { CircleSlash, ClipboardPlus } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import { DraftActions } from '../components/DraftActions'
import { PageHeader, UnitPicker } from '../components/Layout'
import { Card, Delta, ErrorBox, HelpStrip, InfoTip, SEQ, Spinner, pct } from '../components/ui'
import { unitQs, useApp } from '../state'
import type { RadarSchool } from '../types'
import { SchoolModal } from './Block'

type RadarRes = { unit_type: string; unit: string; rules: Record<string, string>; n_schools: number; n_flagged: number; n_priority: number; schools: RadarSchool[] }
type Matrix = { keys: string[]; matrix: number[][] }

function OverlapMatrix({ q }: { q: string }) {
  const { t } = useApp()
  const m = useQuery({ queryKey: ['matrix', q], queryFn: () => api.get<Matrix>(`/radar/matrix?${q}`) })
  if (!m.data) return <Spinner />
  const max = Math.max(1, ...m.data.matrix.flat())
  return (
    <Card title={t('radar.overlap')} sub={t('radar.overlapSub')}>
      <div className="overflow-x-auto">
        <table className="text-[0.76rem]">
          <thead><tr><th />{m.data.keys.map((k) => <th key={k} className="w-[4.4rem] px-0.5 pb-1.5 text-center align-bottom font-medium leading-tight text-ink-2">{t(`r.${k}`)}</th>)}</tr></thead>
          <tbody>{m.data.matrix.map((row, i) => (
            <tr key={i}>
              <td className="pr-2 text-right font-medium leading-tight text-ink-2">{t(`r.${m.data!.keys[i]}`)}</td>
              {row.map((v, j) => {
                const idx = Math.min(SEQ.length - 1, Math.round((v / max) * (SEQ.length - 1)))
                return (
                  <td key={j} className="p-0.5" title={`${t(`r.${m.data!.keys[i]}`)} + ${t(`r.${m.data!.keys[j]}`)}: ${v}`}>
                    <div className="grid h-10 place-items-center rounded tabnum text-[0.85rem] font-semibold" style={{ background: SEQ[idx], color: idx >= 4 ? '#fffdf8' : '#1f1d1a', outline: i === j ? '2px solid #1f1d1a22' : undefined }}>{v}</div>
                  </td>
                )
              })}
            </tr>
          ))}</tbody>
        </table>
      </div>
    </Card>
  )
}

export default function RadarPage() {
  const { unit, t } = useApp()
  const [minFlags, setMinFlags] = useState(2)
  const [sel, setSel] = useState<string[]>([])
  const [draft, setDraft] = useState(false)
  const [school, setSchool] = useState<string | null>(null)
  const [filter, setFilter] = useState<string | null>(null)
  const q = unitQs(unit)
  const r = useQuery({ queryKey: ['radar', q, minFlags], queryFn: () => api.get<RadarRes>(`/radar?${q}&min_flags=${minFlags}`) })
  if (r.isError) return <ErrorBox error={r.error} />
  const schools = (r.data?.schools ?? []).filter((s) => !filter || s.flags.includes(filter))
  const toggle = (c: string) => setSel((s) => (s.includes(c) ? s.filter((x) => x !== c) : [...s, c]))
  const draftUnit = r.data && r.data.unit_type !== 'state' ? r.data : null
  return (
    <div className="space-y-5">
      <PageHeader title={t('radar.title')} sub={t('radar.sub')}
        right={<>
          <UnitPicker />
          <label className="flex items-center gap-2 text-[0.88rem] font-semibold text-ink-2">{t('c.minFlags')}
            <select className="field !min-h-9" value={minFlags} onChange={(e) => setMinFlags(Number(e.target.value))}>{[1, 2, 3, 4].map((n) => <option key={n} value={n}>{t('radar.flagged', { n })}</option>)}</select>
            <InfoTip text={t('radar.info')} />
          </label>
          <button className="btn btn-primary" disabled={!draftUnit} onClick={() => setDraft(true)}><ClipboardPlus className="h-4 w-4" /> {sel.length ? t('radar.draftN', { n: sel.length }) : t('radar.draft')}</button>
        </>} />
      <HelpStrip k="help.radar" />
      {!r.data ? <Spinner /> : (
        <div className="grid gap-5 xl:grid-cols-[1fr_1.9fr]">
          <div className="space-y-5">
            <Card title={r.data.unit === 'State' ? t('c.wholeState') : r.data.unit}>
              <div className="grid grid-cols-3 gap-3">
                <div><div className="num-xl">{r.data.n_schools}</div><div className="eyebrow mt-1">{t('radar.schools')}</div></div>
                <div><div className="num-xl text-mustard">{r.data.n_flagged}</div><div className="eyebrow mt-1">{t('radar.flagged', { n: minFlags })}</div></div>
                <div><div className="num-xl text-brick">{r.data.n_priority}</div><div className="eyebrow mt-1">{t('radar.priority')}</div></div>
              </div>
              <div className="rule my-4" />
              <div className="space-y-1">
                <button className={clsx('flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-left text-[0.9rem]', !filter ? 'bg-forest text-surface' : 'hover:bg-sunk')} onClick={() => setFilter(null)}>{t('c.all')}</button>
                {Object.keys(r.data.rules).map((k) => (
                  <div key={k} className="flex items-center gap-1">
                    <button className={clsx('flex flex-1 items-center justify-between rounded-md px-2.5 py-1.5 text-left text-[0.9rem]', filter === k ? 'bg-forest text-surface' : 'hover:bg-sunk')} onClick={() => setFilter(k)}>{t(`r.${k}`)}</button>
                    <InfoTip text={t(`ri.${k}`)} />
                  </div>
                ))}
              </div>
            </Card>
            <OverlapMatrix q={q} />
          </div>
          <Card title={t('radar.list', { n: schools.length })} sub={t('radar.listSub')} pad={false}>
            <div className="max-h-[78vh] divide-y divide-line overflow-y-auto">
              {schools.map((s) => (
                <div key={s.udise_code} className="grid grid-cols-[auto_1fr] items-start gap-x-3 gap-y-2 px-4 py-3.5 lg:grid-cols-[auto_1fr_auto] lg:gap-4 lg:px-5">
                  <input type="checkbox" className="mt-1.5 h-4 w-4 accent-[#1e4d36]" checked={sel.includes(s.udise_code)} onChange={() => toggle(s.udise_code)} aria-label={s.school_name} />
                  <div className="min-w-0">
                    <button className="text-left text-[0.98rem] font-semibold hover:underline" onClick={() => setSchool(s.udise_code)}>{s.school_name}</button>
                    <div className="text-[0.76rem] text-muted">{s.block} · {s.udise_code}</div>
                    <ul className="reasons mt-1.5">{s.flags.map((f) => <li key={f}>{t(`r.${f}`)}</li>)}</ul>
                    {s.missing.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{s.missing.map((x) => <span key={x} className="tag !text-muted"><CircleSlash className="h-3 w-3" /> {t('r.missing', { x: t(`r.x.${x}`) })}</span>)}</div>}
                  </div>
                  <div className="col-start-2 text-[0.84rem] tabnum lg:col-start-auto lg:text-right">
                    <span className={clsx('tag mb-1.5', s.tier === 'priority_support' ? '!border-brick/30 !bg-brick-50 !text-brick' : '!text-mustard')}>{t(`radar.tier.${s.tier}`)}</span>
                    <div>{t('m.numeracy')} {pct(s.numeracy)} <Delta v={s.numeracy_change} unit={false} /></div>
                    <div>{t('m.student_att')} {pct(s.attendance)} <Delta v={s.attendance_change} unit={false} /></div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
      {draftUnit && <DraftActions open={draft} onClose={() => setDraft(false)} unitType={draftUnit.unit_type} unit={draftUnit.unit} schools={sel.length ? sel : undefined} />}
      <SchoolModal udise={school} onClose={() => setSchool(null)} />
    </div>
  )
}
