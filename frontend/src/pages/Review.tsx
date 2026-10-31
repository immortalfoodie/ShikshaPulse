// Monthly review meeting — a step-by-step agenda; decisions become owned, dated tasks on the spot.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, ArrowRight, CheckCircle2, FileText, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { EarlyWarningCard } from '../components/EarlyWarning'
import { PageHeader, UnitPicker } from '../components/Layout'
import { Card, Delta, OutcomeBadge, Spinner } from '../components/ui'
import { colOf, useActionTitle } from '../lib/actions'
import { pct } from '../lib/format'
import { useReasonText } from '../lib/localizedText'
import { unitQs, useApp } from '../state'
import type { Action, ChildReason, Overview, Trend } from '../types'
import { ActionDrawer } from './Actions'

type Owner = { id: string; name: string; role: string }

export default function Review() {
  const { unit, t } = useApp()
  const nav = useNavigate()
  const qc = useQueryClient()
  const reasonText = useReasonText()
  const title = useActionTitle()
  const q = unitQs(unit)
  const [step, setStep] = useState(0)
  const [open, setOpen] = useState<number | null>(null)
  const [dec, setDec] = useState({ text: '', owner: '', due: '' })
  const [added, setAdded] = useState<string[]>([])
  const ov = useQuery({ queryKey: ['overview', q], queryFn: () => api.get<Overview>(`/overview?${q}`) })
  const tr = useQuery({ queryKey: ['trend', q], queryFn: () => api.get<Trend>(`/trend?${q}`) })
  const kids = useQuery({
    queryKey: ['children', q],
    queryFn: () => api.get<ChildReason[]>(`/children-reasons?${q}`),
    enabled: unit.unit_type !== 'block',
  })
  const acts = useQuery({
    queryKey: ['actions', q, false],
    queryFn: () => api.get<{ actions: Action[] }>(`/actions?${q}&mine=false`),
  })
  const owners = useQuery({ queryKey: ['owners', q], queryFn: () => api.get<Owner[]>(`/owners?${q}`) })
  const create = useMutation({
    mutationFn: () => {
      const o = owners.data?.find((x) => x.id === dec.owner)
      return api.post('/actions', {
        title: dec.text,
        description: t('rev.title'),
        unit_type: unit.unit_type,
        unit: unit.unit ?? 'State',
        owner_name: o?.name,
        owner_id: o?.id,
        owner_role: o?.role,
        due_date: dec.due || undefined,
        priority: 'High',
        issue_title: t('rev.title'),
      })
    },
    onSuccess: () => {
      setAdded((a) => [...a, dec.text])
      setDec({ text: '', owner: dec.owner, due: dec.due })
      qc.invalidateQueries({ queryKey: ['actions'] })
    },
  })
  const steps = ['rev.s1', 'rev.s2', 'rev.s3', 'rev.s4', 'rev.s5', 'rev.s6']
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName?.match(/INPUT|TEXTAREA|SELECT/)) return
      if (e.key === 'ArrowRight') setStep((s) => Math.min(steps.length - 1, s + 1))
      if (e.key === 'ArrowLeft') setStep((s) => Math.max(0, s - 1))
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [steps.length])
  const follow = (acts.data?.actions ?? []).filter((a) => ['overdue', 'verify'].includes(colOf(a)))
  const o = ov.data
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHeader title={t('rev.title')} sub={t('rev.sub')} right={<UnitPicker />} />
      <ol className="flex flex-wrap gap-1.5">
        {steps.map((s, i) => (
          <li key={s}>
            <button
              onClick={() => setStep(i)}
              className={clsx(
                'rounded-full px-3 py-1.5 text-[0.84rem] font-semibold',
                i === step ? 'bg-forest text-surface' : i < step ? 'bg-forest-50 text-forest' : 'bg-sunk text-ink-2',
              )}
            >
              {i + 1}. {t(s)}
            </button>
          </li>
        ))}
      </ol>
      <div className="min-h-[420px]">
        {step === 0 &&
          (o ? (
            <Card title={t('rev.s1')}>
              <div className="grid gap-4 md:grid-cols-3">
                {o.kpis.slice(0, 3).map((k) => (
                  <div key={k.metric} className="panel-sunk p-4">
                    <div className="text-[0.86rem] font-semibold text-ink-2">{t(`m.${k.metric}`)}</div>
                    <div className="num-xl mt-1">{pct(k.latest)}</div>
                    <Delta v={k.change_pp} higherIsBetter={k.higher_is_better} />
                  </div>
                ))}
              </div>
              {tr.data && (
                <div className="mt-4 flex flex-wrap gap-6 tabnum">
                  {tr.data.points.map((p) => (
                    <div key={p.year}>
                      <div className="text-[0.8rem] text-muted">{p.year}</div>
                      <div className="text-[1.6rem] font-bold">{pct(p.value)}</div>
                    </div>
                  ))}
                </div>
              )}
              {o.rank && (
                <div className="mt-4 rounded-lg border-l-4 border-brick bg-brick-50 p-3 font-semibold">
                  {t('home.rank', {
                    pos: o.rank.state_position,
                    of: o.rank.state_of,
                    units: t(`home.units.${o.unit_type}`),
                  })}
                </div>
              )}
            </Card>
          ) : (
            <Spinner />
          ))}
        {step === 1 && <EarlyWarningCard unit={unit} />}
        {step === 2 && (
          <Card title={t('rev.s3')}>
            {follow.length === 0 ? (
              <div className="text-ink-2">{t('rev.noFollow')}</div>
            ) : (
              <ul className="divide-y divide-line">
                {follow.map((a) => (
                  <li key={a.id}>
                    <button
                      className="flex w-full items-center justify-between gap-3 py-3 text-left hover:bg-sunk"
                      onClick={() => setOpen(a.id)}
                    >
                      <span>
                        <span className="block font-semibold">{title(a)}</span>
                        <span className="text-[0.84rem] text-ink-2">
                          {a.owner_name} · {a.due_date}
                        </span>
                      </span>
                      <OutcomeBadge s={a.outcome_status} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
        {step === 3 && (
          <Card title={t('rev.s4')}>
            {!kids.data ? (
              <Spinner />
            ) : (
              <ul className="grid gap-3 md:grid-cols-2">
                {kids.data
                  .filter((k) => k.needs_review)
                  .map((k) => (
                    <li key={k.unit} className="panel-sunk p-4">
                      <div className="flex items-center justify-between">
                        <span className="text-[1.05rem] font-semibold">{k.name}</span>
                        <Delta v={k.change_pp} />
                      </div>
                      <ul className="reasons mt-2">
                        {k.reason_items.map((x, i) => (
                          <li key={i}>{reasonText(x)}</li>
                        ))}
                      </ul>
                      <button
                        className="btn btn-quiet mt-3 !min-h-8 !py-1"
                        onClick={() => {
                          setDec({ ...dec, text: `${k.name}: ` })
                          setStep(4)
                        }}
                      >
                        <Plus className="h-4 w-4" /> {t('rev.add')}
                      </button>
                    </li>
                  ))}
              </ul>
            )}
          </Card>
        )}
        {step === 4 && (
          <Card title={t('rev.s5')}>
            <div className="grid gap-3 md:grid-cols-[2fr_1.2fr_0.8fr_auto] md:items-end">
              <label>
                <span className="eyebrow">{t('rev.decision')}</span>
                <input
                  className="field mt-1 w-full"
                  value={dec.text}
                  placeholder={t('rev.decisionPh')}
                  onChange={(e) => setDec({ ...dec, text: e.target.value })}
                />
              </label>
              <label>
                <span className="eyebrow">{t('rev.owner')}</span>
                <select
                  className="field mt-1 w-full"
                  value={dec.owner}
                  onChange={(e) => setDec({ ...dec, owner: e.target.value })}
                >
                  <option value="">—</option>
                  {owners.data?.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.name} — {x.role}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span className="eyebrow">{t('rev.due')}</span>
                <input
                  type="date"
                  className="field mt-1 w-full"
                  value={dec.due}
                  onChange={(e) => setDec({ ...dec, due: e.target.value })}
                />
              </label>
              <button
                className="btn btn-primary"
                disabled={!dec.text.trim() || !dec.owner || create.isPending}
                onClick={() => create.mutate()}
              >
                <Plus className="h-4 w-4" /> {t('rev.add')}
              </button>
            </div>
            {added.length > 0 && (
              <div className="mt-4">
                <div className="eyebrow mb-1">{t('rev.added', { n: added.length })}</div>
                <ul className="space-y-1">
                  {added.map((a, i) => (
                    <li key={i} className="flex items-center gap-2 text-[0.92rem]">
                      <CheckCircle2 className="h-4 w-4 text-good" />
                      {a}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        )}
        {step === 5 && (
          <Card title={t('rev.s6')}>
            <p className="text-[1.05rem]">{t('rev.done', { n: added.length })}</p>
            <button className="btn btn-primary mt-4" onClick={() => nav('/brief')}>
              <FileText className="h-4 w-4" /> {t('rev.brief')}
            </button>
          </Card>
        )}
      </div>
      <div className="flex items-center justify-between">
        <button className="btn btn-quiet" disabled={step === 0} onClick={() => setStep(step - 1)}>
          <ArrowLeft className="h-4 w-4" /> {t('rev.prev')}
        </button>
        <span className="text-[0.85rem] text-muted">{t('rev.step', { a: step + 1, b: steps.length })}</span>
        <button className="btn btn-primary" disabled={step === steps.length - 1} onClick={() => setStep(step + 1)}>
          {t('rev.next')} <ArrowRight className="h-4 w-4" />
        </button>
      </div>
      <ActionDrawer id={open} onClose={() => setOpen(null)} />
    </div>
  )
}
