// One-page school report card in the reader's language — for the notice board, parents and the SMC.
import { useQuery } from '@tanstack/react-query'
import { MessageCircle, Printer } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import { Mark } from '../components/Layout'
import { ErrorBox, Speak, Spinner } from '../components/ui'
import { useActionTitle } from '../lib/actions'
import { useApp } from '../state'
import type { Action } from '../types'

type Res = {
  school: { school_name: string; udise_code: string; block: string; years: Record<string, number | string | null>[] }
  flags: string[]
  block_kpis: Record<string, number | null>
  actions: Action[]
  baseline_year: string
  latest_year: string
}

export default function ReportCard() {
  const { udise } = useParams()
  const { t } = useApp()
  const title = useActionTitle()
  const r = useQuery({
    queryKey: ['report-card', udise],
    queryFn: () => api.get<Res>(`/my-school${udise ? `?udise=${udise}` : ''}`),
  })
  if (r.isError) return <ErrorBox error={r.error} />
  if (!r.data) return <Spinner />
  const { school, flags, block_kpis: bk, actions } = r.data
  const ys = school.years
  const last = ys[ys.length - 1]
  const n = (v: unknown) => (typeof v === 'number' ? v : null)
  const max = Math.max(1, ...ys.map((y) => n(y.numeracy) ?? 0))
  const san = n(last.maths_sanctioned) ?? 0,
    vac = n(last.maths_vacant) ?? 0
  const tips = [
    flags.includes('attendance_decline') || (n(last.student_att) ?? 100) < 80 ? 'rc.p.attendance' : null,
    'rc.p.maths',
    flags.includes('maths_vacancy') ? 'rc.p.teacher' : null,
    'rc.p.smc',
  ].filter(Boolean) as string[]
  const open = actions.filter((a) => !['verified', 'closed_not_implemented'].includes(a.status))
  const lines = [
    `*${t('rc.title')} — ${school.school_name}*`,
    `${t('m.numeracy')}: ${last.numeracy ?? '—'}% (${t('my.blockAvg', { v: `${bk.numeracy ?? '—'}%` })})`,
    `${t('my.att')}: ${last.student_att ?? '—'}%`,
    `${t('my.teachers')}: ${san ? `${san - vac}/${san}` : '—'}`,
    ...flags.map((f) => `• ${t(`r.${f}`)}`),
    '',
    `${t('rc.parents')}:`,
    ...tips.map((k) => `• ${t(k)}`),
    '',
    t('rc.footer'),
  ]
  const shareUrl = `https://wa.me/?text=${encodeURIComponent(lines.join('\n'))}`
  return (
    <div className="space-y-4">
      <div className="no-print flex flex-wrap items-center justify-end gap-2">
        <Speak text={lines.join('. ').replace(/\*/g, '')} />
        <a className="btn btn-quiet" href={shareUrl} target="_blank" rel="noreferrer">
          <MessageCircle className="h-4 w-4" /> {t('rc.share')}
        </a>
        <button className="btn btn-primary" onClick={() => window.print()}>
          <Printer className="h-4 w-4" /> {t('rc.print')}
        </button>
      </div>
      <article className="panel mx-auto max-w-3xl space-y-6 p-10 print:p-4">
        <header className="flex items-start justify-between gap-4 border-b-2 border-forest pb-4">
          <div>
            <div className="eyebrow">
              {t('rc.title')} · {r.data.latest_year}
            </div>
            <h1 className="mt-1 text-[1.8rem] font-bold leading-tight">{school.school_name}</h1>
            <div className="text-[0.95rem] text-ink-2">
              {t('c.blockLabel', { b: school.block })} · UDISE {school.udise_code}
            </div>
          </div>
          <Mark size={46} />
        </header>
        <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            [
              t('my.maths'),
              n(last.numeracy) !== null ? `${last.numeracy}%` : '—',
              t('my.blockAvg', { v: `${bk.numeracy ?? '—'}%` }),
            ],
            [
              t('my.att'),
              n(last.student_att) !== null ? `${last.student_att}%` : '—',
              t('my.blockAvg', { v: `${bk.student_att ?? '—'}%` }),
            ],
            [t('my.teachers'), san ? `${san - vac}/${san}` : '—', ''],
            [
              t('my.facilities'),
              n(last.infra_index) !== null ? `${Math.round((n(last.infra_index)! / 100) * 6)}/6` : '—',
              '',
            ],
          ].map(([a, b, c]) => (
            <div key={a} className="rounded-lg border border-line p-3">
              <div className="text-[0.85rem] font-semibold text-ink-2">{a}</div>
              <div className="mt-1 text-[1.9rem] font-bold leading-none">{b}</div>
              {c && <div className="mt-1 text-[0.76rem] text-muted">{c}</div>}
            </div>
          ))}
        </section>
        <section>
          <h2 className="mb-2 font-bold text-forest">{t('rc.trend')}</h2>
          <div className="flex items-end gap-6">
            {ys.map((y) => (
              <div key={String(y.academic_year)} className="flex flex-col items-center gap-1">
                <span className="text-[0.9rem] font-semibold tabnum">
                  {n(y.numeracy) !== null ? `${y.numeracy}%` : '—'}
                </span>
                <div
                  className="w-14 rounded-t-md bg-s1"
                  style={{ height: `${((n(y.numeracy) ?? 0) / max) * 110}px` }}
                />
                <span className="text-[0.8rem] text-muted">{String(y.academic_year)}</span>
              </div>
            ))}
          </div>
        </section>
        {flags.length > 0 && (
          <section>
            <h2 className="mb-2 font-bold text-forest">{t('my.help')}</h2>
            <ul className="reasons">
              {flags.map((f) => (
                <li key={f} className="!text-[0.95rem] !text-ink">
                  {t(`ri.${f}`)}
                </li>
              ))}
            </ul>
          </section>
        )}
        <section>
          <h2 className="mb-2 font-bold text-forest">{t('rc.doing')}</h2>
          {open.length === 0 ? (
            <p className="text-ink-2">{t('rc.noTasks')}</p>
          ) : (
            <ul className="reasons">
              {open.map((a) => (
                <li key={a.id} className="!text-[0.95rem] !text-ink">
                  {title(a)} · {t('my.taskDue', { d: a.due_date })}
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="rounded-lg bg-saffron-50 p-4">
          <h2 className="mb-2 font-bold text-mustard">{t('rc.parents')}</h2>
          <ul className="reasons">
            {tips.map((k) => (
              <li key={k} className="!text-[0.95rem] !text-ink">
                {t(k)}
              </li>
            ))}
          </ul>
        </section>
        <footer className="text-[0.76rem] text-muted">
          {t('rc.footer')} · {t('app.synthetic')}
        </footer>
      </article>
    </div>
  )
}
