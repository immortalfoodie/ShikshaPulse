// Simple, big-type school view for headmasters and teachers — every line can be read aloud.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  BookOpen,
  Building,
  CalendarClock,
  CheckCircle2,
  MessageCircleQuestion,
  PlayCircle,
  Send,
  Users,
} from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import { HelpStrip, InfoTip, OutcomeBadge, Speak, Spinner, ErrorBox } from '../components/ui'
import { useActionTitle } from '../lib/actions'
import { useApp } from '../state'
import type { Action } from '../types'
import { ActionDrawer } from './Actions'

type MySchoolRes = {
  school: { school_name: string; udise_code: string; block: string; years: Record<string, number | string | null>[] }
  flags: string[]
  block_kpis: Record<string, number | null>
  actions: Action[]
  latest_year: string
  baseline_year: string
}

function BigStat({
  icon: Icon,
  title,
  value,
  line,
  sub,
  tone,
  info,
}: {
  icon: typeof Users
  title: string
  value: string
  line: string
  sub?: string
  tone: 'good' | 'bad' | 'flat'
  info: string
}) {
  const color = tone === 'good' ? 'text-good' : tone === 'bad' ? 'text-brick' : 'text-ink-2'
  return (
    <div className="panel p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[1rem] font-semibold">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-forest-50 text-forest">
            <Icon className="h-5 w-5" />
          </span>
          {title}
        </div>
        <InfoTip text={info} />
      </div>
      <div className="mt-3 text-[2.6rem] font-bold leading-none">{value}</div>
      <div className={`mt-2 text-[1rem] font-semibold ${color}`}>{line}</div>
      {sub && <div className="mt-0.5 text-[0.88rem] text-muted">{sub}</div>}
    </div>
  )
}

export default function MySchool() {
  const { user, ask, t } = useApp()
  const qc = useQueryClient()
  const title = useActionTitle()
  const [open, setOpen] = useState<number | null>(null)
  const r = useQuery({ queryKey: ['my-school'], queryFn: () => api.get<MySchoolRes>('/my-school') })
  const status = useMutation({
    mutationFn: ({ id, s }: { id: number; s: string }) => api.post(`/actions/${id}/status`, { status: s, note: '' }),
    onSuccess: () => qc.invalidateQueries(),
  })
  if (r.isError) return <ErrorBox error={r.error} />
  if (!r.data) return <Spinner />
  const { school, flags, block_kpis: bk, actions } = r.data
  const ys = school.years
  const first = ys[0],
    last = ys[ys.length - 1]
  const n = (v: unknown) => (typeof v === 'number' ? v : null)
  const change = (a: unknown, b: unknown) =>
    n(a) !== null && n(b) !== null ? Math.round((n(b)! - n(a)!) * 10) / 10 : null
  const sentence = (d: number | null) =>
    d === null
      ? ''
      : Math.abs(d) < 1
        ? t('my.same', { y0: r.data.baseline_year })
        : d > 0
          ? t('my.up', { d, y0: r.data.baseline_year })
          : t('my.down', { d: Math.abs(d), y0: r.data.baseline_year })
  const tone = (d: number | null, higher = true) =>
    (d === null || Math.abs(d) < 1 ? 'flat' : d > 0 === higher ? 'good' : 'bad') as 'good' | 'bad' | 'flat'
  const dNum = change(first.numeracy, last.numeracy)
  const dAtt = change(first.student_att, last.student_att)
  const san = n(last.maths_sanctioned) ?? 0,
    vac = n(last.maths_vacant) ?? 0
  const mine = actions.filter((a) => a.can_update)
  const others = actions.filter((a) => !a.can_update && !['verified', 'closed_not_implemented'].includes(a.status))
  const posts = san ? (vac ? t('my.posts', { w: san - vac, s: san }) : t('my.allPosts')) : t('c.noData')
  const speech = [
    t('my.speech', { school: school.school_name, m: last.numeracy ?? '—', a: last.student_att ?? '—', posts }),
    sentence(dNum),
    flags.length ? `${t('my.help')}: ${flags.map((f) => t(`ri.${f}`)).join(' ')}` : t('my.ok'),
  ].join(' ')
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">{t('my.title')}</div>
          <h1 className="h-page mt-1">{t('my.hello', { name: user?.name })}</h1>
          <p className="mt-1 text-[1.05rem] text-ink-2">
            {t('my.sub', { school: school.school_name, block: school.block })}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Speak text={speech} label={t('my.listenAll')} className="!min-h-12 !px-5 !text-[1rem]" />
          <a className="btn btn-quiet !min-h-12 !px-5 !text-[1rem]" href={`/report-card/${school.udise_code}`}>
            {t('rc.open')}
          </a>
          <button className="btn btn-accent !min-h-12 !px-5 !text-[1rem]" onClick={() => ask(t('ask.s7'))}>
            <MessageCircleQuestion className="h-5 w-5" /> {t('my.ask')}
          </button>
        </div>
      </div>
      <HelpStrip k="help.my" />
      <div className="grid gap-4 sm:grid-cols-2">
        <BigStat
          icon={BookOpen}
          title={t('my.maths')}
          value={n(last.numeracy) !== null ? `${last.numeracy}%` : '—'}
          line={sentence(dNum)}
          sub={t('my.blockAvg', { v: bk.numeracy !== null ? `${bk.numeracy}%` : '—' })}
          tone={tone(dNum)}
          info={t('mi.numeracy')}
        />
        <BigStat
          icon={Users}
          title={t('my.att')}
          value={n(last.student_att) !== null ? `${last.student_att}%` : '—'}
          line={sentence(dAtt)}
          sub={t('my.blockAvg', { v: bk.student_att !== null ? `${bk.student_att}%` : '—' })}
          tone={tone(dAtt)}
          info={t('mi.student_att')}
        />
        <BigStat
          icon={Users}
          title={t('my.teachers')}
          value={san ? `${san - vac}/${san}` : '—'}
          line={posts}
          tone={vac ? 'bad' : 'good'}
          info={t('mi.maths_vacancy')}
        />
        <BigStat
          icon={Building}
          title={t('my.facilities')}
          value={n(last.infra_index) !== null ? `${Math.round((n(last.infra_index)! / 100) * 6)}/6` : '—'}
          line={n(last.infra_index) !== null ? `${last.infra_index}%` : ''}
          tone={(n(last.infra_index) ?? 100) <= 50 ? 'bad' : 'flat'}
          info={t('mi.infra_index')}
        />
      </div>
      <section className="panel p-5">
        <h2 className="h-card mb-3 flex items-center gap-1.5">
          {t('my.help')} <InfoTip text={t('my.helpInfo')} />
        </h2>
        {flags.length === 0 ? (
          <div className="flex items-center gap-2 text-[1rem] text-good">
            <CheckCircle2 className="h-5 w-5" /> {t('my.ok')}
          </div>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2">
            {flags.map((f) => (
              <li key={f} className="flex items-start gap-3 rounded-lg border-l-4 border-brick bg-brick-50 p-3.5">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-brick" />
                <div>
                  <div className="text-[1rem] font-semibold">{t(`r.${f}`)}</div>
                  <div className="text-[0.9rem] text-ink-2">{t(`ri.${f}`)}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="panel p-5">
        <h2 className="h-card mb-3">{t('my.tasks')}</h2>
        {mine.length === 0 ? (
          <div className="text-[1rem] text-ink-2">{t('my.noTasks')}</div>
        ) : (
          <ul className="space-y-3">
            {mine.map((a) => (
              <li key={a.id} className="panel-sunk p-4">
                <button
                  className="text-left text-[1.05rem] font-semibold hover:underline"
                  onClick={() => setOpen(a.id)}
                >
                  {title(a)}
                </button>
                <div className="mt-1 flex flex-wrap items-center gap-3 text-[0.9rem] text-ink-2">
                  <span className="inline-flex items-center gap-1">
                    <CalendarClock className="h-4 w-4" />
                    {t('my.taskDue', { d: a.due_date })}
                  </span>
                  <OutcomeBadge s={a.outcome_status} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {a.status === 'open' && (
                    <button
                      className="btn btn-quiet !min-h-12 !px-5 !text-[1rem]"
                      onClick={() => status.mutate({ id: a.id, s: 'in_progress' })}
                    >
                      <PlayCircle className="h-5 w-5" /> {t('my.started')}
                    </button>
                  )}
                  {['open', 'in_progress'].includes(a.status) && (
                    <button
                      className="btn btn-primary !min-h-12 !px-5 !text-[1rem]"
                      onClick={() => status.mutate({ id: a.id, s: 'awaiting_verification' })}
                    >
                      <Send className="h-5 w-5" /> {t('my.done')}
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
        {others.length > 0 && (
          <div className="mt-5">
            <h3 className="text-[1rem] font-semibold">{t('my.others')}</h3>
            <p className="mb-2 text-[0.88rem] text-muted">{t('my.othersSub')}</p>
            <ul className="divide-y divide-line">
              {others.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                  <button className="min-w-0 text-left text-[0.95rem] hover:underline" onClick={() => setOpen(a.id)}>
                    {title(a)}
                    <span className="block text-[0.84rem] text-muted">
                      {a.owner_name} · {t('my.taskDue', { d: a.due_date })}
                    </span>
                  </button>
                  <OutcomeBadge s={a.outcome_status} />
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
      <ActionDrawer id={open} onClose={() => setOpen(null)} />
    </div>
  )
}
