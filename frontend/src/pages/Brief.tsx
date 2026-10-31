import { useQuery } from '@tanstack/react-query'
import { Download, Printer, ShieldCheck } from 'lucide-react'
import { api, downloadFile } from '../api'
import { Mark, PageHeader, UnitPicker } from '../components/Layout'
import { ErrorBox, FindingLabel, HelpStrip, OutcomeBadge, Speak, Spinner } from '../components/ui'
import { useActionTitle } from '../lib/actions'
import { pct } from '../lib/format'
import { useReasonText, useWarningText, type ReasonItem } from '../lib/localizedText'
import { unitQs, useApp } from '../state'
import type { AskResult, ChildReason } from '../types'

type BriefT = {
  unit_type: string
  unit: string
  generated_at: string
  prepared_for: string
  period: string
  data_confidence: number
  summary: AskResult['answer']
  guard: AskResult['guard']
  engine: string
  trend: { year: string; value: number | null }[]
  trend_change: number | null
  rank: { state_position: number; state_of: number } | null
  concentration?: ChildReason[]
  peers?: {
    block: string
    peers: unknown[]
    summary: { low: number; high: number; median: number; unit_change: number; gap_vs_median: number } | null
  }
  radar: {
    n_schools: number
    n_flagged: number
    n_priority: number
    schools: { school_name: string; block: string; flags: string[] }[]
  }
  actions: {
    id: number
    title: string
    intervention_key: string | null
    unit: string
    owner: string
    due: string
    outcome_status: string
    simulated: boolean
  }[]
  actions_summary: Record<string, number>
  limitation_items: { kind: string; source?: string; pct?: number; n?: number; from_year?: string; to_year?: string }[]
  data_gap_keys: string[]
}

function SectionHeading({ label }: { label: string }) {
  return <h3 className="mb-2 border-b border-line pb-1 text-[1rem] font-bold text-forest">{label}</h3>
}

export default function Brief() {
  const { unit, lang, t } = useApp()
  const reasonText = useReasonText()
  const wText = useWarningText()
  const title = useActionTitle()
  const q = unitQs(unit)
  const b = useQuery({ queryKey: ['brief', q, lang], queryFn: () => api.get<BriefT>(`/brief?${q}&lang=${lang}`) })
  const name = !b.data
    ? ''
    : b.data.unit_type === 'state'
      ? t('c.wholeState')
      : b.data.unit_type === 'district'
        ? t('c.districtLabel', { d: b.data.unit })
        : t('c.blockLabel', { b: b.data.unit })
  const p = b.data?.peers
  const peerText = p?.summary
    ? t('peers.summary', {
        n: (p.peers as unknown[]).length,
        lo: p.summary.low,
        hi: p.summary.high,
        med: p.summary.median,
        block: p.block,
        u: p.summary.unit_change,
        gap: Math.abs(p.summary.gap_vs_median),
        dir: t(p.summary.gap_vs_median < 0 ? 'peers.below' : 'peers.above'),
      })
    : ''
  return (
    <div className="space-y-5">
      <PageHeader
        title={t('brief.title')}
        sub={t('brief.sub')}
        right={
          <>
            <UnitPicker />
            {b.data && <Speak text={[b.data.summary.summary, ...b.data.summary.next_steps].join(' ')} />}
            <button className="btn btn-quiet" onClick={() => window.print()}>
              <Printer className="h-4 w-4" /> {t('c.print')}
            </button>
            <button
              className="btn btn-primary"
              onClick={() =>
                downloadFile(`/brief.pdf?${q}&lang=${lang}`, `ShikshaPulse_brief_${unit.unit ?? 'state'}.pdf`)
              }
            >
              <Download className="h-4 w-4" /> {t('c.pdf')}
            </button>
          </>
        }
      />
      <HelpStrip k="help.brief" />
      {b.isError && <ErrorBox error={b.error} />}
      {!b.data ? (
        <Spinner label={t('brief.composing')} />
      ) : (
        <article className="panel mx-auto max-w-4xl space-y-6 p-10 print:p-0">
          <header className="flex items-start justify-between gap-4 border-b-2 border-forest pb-4">
            <div>
              <div className="eyebrow !text-mustard">{t('app.synthetic')}</div>
              <h2 className="mt-1 text-[1.6rem] font-bold leading-tight">
                {t('brief.title')} — {name}
              </h2>
              <div className="mt-1 text-[0.86rem] text-ink-2">
                {t('brief.meta', {
                  p: b.data.period,
                  d: b.data.generated_at,
                  who: b.data.prepared_for,
                  c: b.data.data_confidence,
                })}
                {b.data.rank && (
                  <>
                    {' '}
                    ·{' '}
                    {t('home.rank', {
                      pos: b.data.rank.state_position,
                      of: b.data.rank.state_of,
                      units: t(`home.units.${b.data.unit_type}`),
                    })}
                  </>
                )}
              </div>
            </div>
            <Mark size={42} />
          </header>
          <section>
            <SectionHeading label={t('brief.h.summary')} />
            <p className="text-[1rem] leading-relaxed">{b.data.summary.summary}</p>
            <ul className="mt-3 space-y-2">
              {b.data.summary.findings.slice(0, 8).map((f, i) => (
                <li key={i} className="flex gap-2 text-[0.92rem]">
                  <span className="shrink-0">
                    <FindingLabel label={f.label} />
                  </span>
                  <span>{f.text}</span>
                </li>
              ))}
            </ul>
            <div className="mt-3 inline-flex items-center gap-1 text-[0.8rem] text-good">
              <ShieldCheck className="h-4 w-4" />
              {t('ask.verified', { a: b.data.guard.numbers_verified, b: b.data.guard.numbers_checked })}
            </div>
          </section>
          <section>
            <SectionHeading label={t('brief.h.trend')} />
            <div className="flex flex-wrap gap-8 tabnum">
              {b.data.trend.map((x) => (
                <div key={x.year}>
                  <div className="text-[0.8rem] text-muted">{x.year}</div>
                  <div className="text-[1.5rem] font-bold">{x.value === null ? '—' : pct(x.value)}</div>
                </div>
              ))}
              <div>
                <div className="text-[0.8rem] text-muted">{t('c.change')}</div>
                <div className="text-[1.5rem] font-bold">
                  {b.data.trend_change} {t('c.pts')}
                </div>
              </div>
            </div>
          </section>
          {b.data.concentration && (
            <section>
              <SectionHeading label={t('brief.h.where')} />
              <table className="w-full text-[0.9rem] tabnum">
                <tbody>
                  {b.data.concentration.map((c) => (
                    <tr key={c.unit} className="border-t border-line align-top">
                      <td className="py-2 pr-3 font-semibold">{c.name}</td>
                      <td className="pr-3">
                        {pct(c.baseline)} → {c.comparable ? pct(c.latest) : '—'}
                      </td>
                      <td className="pr-3">
                        {c.change_pp} {t('c.pts')}
                      </td>
                      <td>
                        <ul className="reasons">
                          {c.reason_items.map((x: ReasonItem, i: number) => (
                            <li key={i}>{reasonText(x)}</li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
          {peerText && (
            <section>
              <SectionHeading label={t('brief.h.peers')} />
              <p className="text-[0.95rem]">{peerText}</p>
              <p className="mt-1 text-[0.92rem] text-ink-2">
                {t(p!.summary!.gap_vs_median <= -4 ? 'peers.big' : 'peers.small')}
              </p>
            </section>
          )}
          <section>
            <SectionHeading label={t('brief.h.radar')} />
            <p className="text-[0.95rem]">
              {t('brief.radar', { f: b.data.radar.n_flagged, n: b.data.radar.n_schools, p: b.data.radar.n_priority })}
            </p>
            <ul className="mt-2 space-y-1 text-[0.9rem]">
              {b.data.radar.schools.map((s) => (
                <li key={s.school_name}>
                  <b>{s.school_name}</b> <span className="text-muted">({s.block})</span>:{' '}
                  {s.flags.map((f) => t(`r.${f}`)).join('; ')}
                </li>
              ))}
            </ul>
          </section>
          <section>
            <SectionHeading label={t('brief.h.actions')} />
            <p className="mb-2 text-[0.92rem]">
              {t('brief.actions', {
                t: b.data.actions_summary.total,
                o: b.data.actions_summary.overdue,
                i: b.data.actions_summary.implemented_improved,
                n: b.data.actions_summary.not_implemented,
              })}
            </p>
            <table className="w-full text-[0.88rem]">
              <tbody>
                {b.data.actions.slice(0, 10).map((a) => (
                  <tr key={a.id} className="border-t border-line align-top">
                    <td className="py-2 pr-3">
                      {title(a)}
                      {a.simulated && <span className="text-muted"> ({t('c.simulated')})</span>}
                    </td>
                    <td className="pr-3">{a.owner}</td>
                    <td className="pr-3 tabnum">{a.due}</td>
                    <td>
                      <OutcomeBadge s={a.outcome_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          {b.data.summary.next_steps.length > 0 && (
            <section>
              <SectionHeading label={t('brief.h.decisions')} />
              <ol className="ml-5 list-decimal space-y-1 text-[0.95rem]">
                {b.data.summary.next_steps.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ol>
            </section>
          )}
          <section>
            <SectionHeading label={t('brief.h.limits')} />
            <ul className="reasons">
              {b.data.limitation_items.map((w, i) => (
                <li key={i}>{wText(w)}</li>
              ))}
              {b.data.data_gap_keys.map((g) => (
                <li key={g}>{t(`gap.${g}`)}</li>
              ))}
            </ul>
            <p className="mt-3 text-[0.8rem] text-muted">{t('brief.note')}</p>
          </section>
        </article>
      )}
    </div>
  )
}
