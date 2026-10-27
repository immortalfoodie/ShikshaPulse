import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, CalendarClock, CheckCircle2, ClipboardPlus, FlaskConical, History, Paperclip, UserRound } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import { DraftActions } from '../components/DraftActions'
import { PageHeader, UnitPicker } from '../components/Layout'
import { C, Drawer, ErrorBox, HelpStrip, InfoTip, OutcomeBadge, Spinner } from '../components/ui'
import { unitQs, useApp } from '../state'
import type { Action, ActionSummary, Measurement } from '../types'

const COLS = ['todo', 'progress', 'overdue', 'verify', 'closed'] as const
export const colOf = (a: Action) =>
  ['verified', 'closed_not_implemented'].includes(a.status) ? 'closed' : a.status === 'awaiting_verification' ? 'verify' : a.overdue ? 'overdue' : a.status === 'in_progress' ? 'progress' : 'todo'

export function useActionTitle() {
  const { t } = useApp()
  return (a: Pick<Action, 'intervention_key' | 'title' | 'unit' | 'unit_name'>) => {
    const k = a.intervention_key ? `iv.${a.intervention_key}` : ''
    return k && t(k) !== k ? `${t(k)} — ${a.unit_name ?? a.unit}` : a.title
  }
}

function ActionCard({ a, onClick }: { a: Action; onClick: () => void }) {
  const { t } = useApp()
  const title = useActionTitle()
  return (
    <button onClick={onClick} className={clsx('panel w-full p-3 text-left transition hover:border-forest', a.overdue && '!border-brick/50')}>
      <div className="text-[0.92rem] font-semibold leading-snug">{title(a)}</div>
      <div className="mt-1.5 grid gap-0.5 text-[0.78rem] text-ink-2">
        <span className="inline-flex items-center gap-1"><UserRound className="h-3.5 w-3.5" />{a.owner_name}</span>
        <span className="inline-flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" />{a.due_date}</span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        <OutcomeBadge s={a.outcome_status} />
        {a.priority === 'High' && <span className="tag !text-brick">{t('c.priorityHigh')}</span>}
        {a.is_simulated && <span className="tag !text-muted"><FlaskConical className="h-3 w-3" /> {t('c.simulated')}</span>}
      </div>
    </button>
  )
}

function MeasureBlock({ m, all }: { m: Measurement; all: Measurement[] }) {
  const { t } = useApp()
  const latest = [...all].reverse().find((x) => x.kind === m.kind && x.value !== null)
  if (m.kind === 'implementation') {
    const ratio = latest && m.target ? Math.min(1.2, latest.value! / m.target) : 0
    return (
      <div className="panel-sunk p-3.5">
        <div className="eyebrow flex items-center gap-1">{t('act.impl')} <InfoTip text={t('act.implInfo')} /></div>
        <div className="mt-0.5 text-[0.9rem] font-medium">{m.unit ?? m.indicator}</div>
        <div className="mt-2 h-3 w-full rounded-full bg-surface ring-1 ring-line"><div className="h-3 rounded-full" style={{ width: `${Math.min(100, ratio * 100)}%`, background: ratio >= 0.8 ? C.good : ratio >= 0.5 ? C.s2 : C.brick }} /></div>
        <div className="mt-1 text-[0.82rem] text-ink-2 tabnum">{latest ? t('act.ofTarget', { v: latest.value, t: m.target, p: Math.round(ratio * 100) }) : t('act.notReported', { t: m.target })}</div>
      </div>
    )
  }
  const change = latest && m.baseline !== null ? Math.round((latest.value! - m.baseline) * 10) / 10 : null
  return (
    <div className="panel-sunk p-3.5">
      <div className="eyebrow flex items-center gap-1">{t('act.learn')} <InfoTip text={t('act.learnInfo')} /></div>
      <div className="mt-0.5 text-[0.9rem] font-medium">{m.unit ?? m.indicator}</div>
      <div className="mt-1 text-[0.86rem] tabnum">{m.baseline ?? '—'} ({m.baseline_date}) → {latest ? `${latest.value} (${latest.measured_at})` : t('act.pending')}
        {change !== null && <b style={{ color: change >= 2 ? C.good : change <= -2 ? C.brick : C.ink2 }}> {change > 0 ? '+' : ''}{change} {t('c.pts')}</b>}
      </div>
    </div>
  )
}

export function ActionDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  const qc = useQueryClient()
  const { user, t } = useApp()
  const title = useActionTitle()
  const a = useQuery({ queryKey: ['action', id], queryFn: () => api.get<Action>(`/actions/${id}`), enabled: id !== null })
  const [note, setNote] = useState('')
  const [val, setVal] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const refresh = () => { qc.invalidateQueries({ queryKey: ['action', id] }); qc.invalidateQueries({ queryKey: ['actions'] }); qc.invalidateQueries({ queryKey: ['actions-summary'] }); qc.invalidateQueries({ queryKey: ['my-school'] }) }
  const status = useMutation({ mutationFn: (s: string) => api.post(`/actions/${id}/status`, { status: s, note, evidence_note: note || undefined }), onSuccess: () => { setNote(''); refresh() } })
  const measure = useMutation({ mutationFn: (kind: string) => api.post(`/actions/${id}/measurement`, { kind, value: Number(val), evidence: note }), onSuccess: () => { setVal(''); refresh() } })
  const upload = useMutation({ mutationFn: () => { const f = new FormData(); f.append('file', file!); f.append('note', note); return api.upload(`/actions/${id}/evidence`, f) }, onSuccess: () => { setFile(null); refresh() } })
  if (id === null) return null
  const x = a.data
  const isOfficer = user && ['district', 'state'].includes(user.role)
  const err = status.error || measure.error || upload.error
  return (
    <Drawer open onClose={onClose} title={x ? title(x) : ''} width="max-w-2xl">
      {!x ? <Spinner /> : (
        <div className="space-y-5 text-[0.92rem]">
          <div className="flex flex-wrap gap-1.5">
            <OutcomeBadge s={x.outcome_status} />
            <span className="tag">{t(`st.${x.status}`)}</span>
            {x.is_simulated && <span className="tag !text-muted"><FlaskConical className="h-3 w-3" /> {t('c.simulated')}</span>}
          </div>
          {x.overdue && <div className="flex items-center gap-2 rounded-lg border-l-4 border-brick bg-brick-50 p-3 text-brick"><AlertTriangle className="h-4 w-4" /> {t('act.overdueBy', { n: Math.abs(x.days_to_due ?? 0), who: x.created_by })}</div>}
          <div className="grid grid-cols-2 gap-4 text-[0.88rem]">
            <div><div className="eyebrow">{t('act.owner')}</div>{x.owner_name}<div className="text-muted">{x.owner_role}</div></div>
            <div><div className="eyebrow">{t('act.deadline')}</div>{x.due_date}</div>
            <div><div className="eyebrow">{t('act.assignedBy')}</div>{x.created_by} · {x.created_at.slice(0, 10)}</div>
            <div><div className="eyebrow">{t('act.verified')}</div>{x.verified_by ? `${x.verified_by} · ${x.verified_at?.slice(0, 10)}` : '—'}</div>
          </div>
          <div><div className="eyebrow">{t('act.why')}</div><p className="text-ink-2">{x.description}</p></div>
          {x.schools.length > 0 && <div className="text-[0.86rem]"><div className="eyebrow">{t('act.schools')}</div>{x.schools.map((s) => (typeof s === 'string' ? s : s.school_name)).join(', ')}</div>}
          <div className="grid gap-3 md:grid-cols-2">{x.measurements.filter((m, i, arr) => arr.findIndex((y) => y.kind === m.kind) === i).map((m) => <MeasureBlock key={m.id} m={m} all={x.measurements} />)}</div>
          {(x.evidence_note || x.evidence_file) && <div className="panel-sunk p-3 text-[0.86rem]"><div className="eyebrow">{t('act.proof')}</div>{x.evidence_note}{x.evidence_file && <div className="mt-0.5 flex items-center gap-1"><Paperclip className="h-3.5 w-3.5" />{x.evidence_file}</div>}</div>}
          {x.can_update === false ? <div className="panel-sunk p-3 text-[0.88rem] text-ink-2">{t('act.readOnly', { o: x.owner_name })}</div> : <div className="panel p-4">
            <div className="eyebrow mb-2">{t('act.update')}</div>
            <textarea className="field w-full" rows={2} placeholder={t('act.note')} value={note} onChange={(e) => setNote(e.target.value)} />
            <div className="mt-2 flex flex-wrap gap-2">
              {x.status === 'open' && <button className="btn btn-quiet" onClick={() => status.mutate('in_progress')}>{t('act.start')}</button>}
              {['open', 'in_progress'].includes(x.status) && <button className="btn btn-primary" onClick={() => status.mutate('awaiting_verification')}>{t('act.submit')}</button>}
              {x.status === 'awaiting_verification' && isOfficer && <button className="btn btn-primary" onClick={() => status.mutate('verified')}><CheckCircle2 className="h-4 w-4" /> {t('act.verify')}</button>}
              {x.status === 'awaiting_verification' && isOfficer && <button className="btn btn-quiet" onClick={() => status.mutate('in_progress')}>{t('act.sendBack')}</button>}
              {!['verified', 'closed_not_implemented'].includes(x.status) && isOfficer && <button className="btn btn-quiet" onClick={() => status.mutate('closed_not_implemented')}>{t('act.closeNot')}</button>}
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input className="field w-28" type="number" placeholder={t('act.value')} value={val} onChange={(e) => setVal(e.target.value)} />
              <button className="btn btn-quiet" disabled={!val} onClick={() => measure.mutate('implementation')}>{t('act.recordImpl')}</button>
              <button className="btn btn-quiet" disabled={!val} onClick={() => measure.mutate('learning')}>{t('act.recordLearn')}</button>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input type="file" className="text-[0.82rem]" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              <button className="btn btn-quiet" disabled={!file} onClick={() => upload.mutate()}><Paperclip className="h-4 w-4" /> {t('act.upload')}</button>
            </div>
            {err && <div className="mt-2"><ErrorBox error={err} /></div>}
          </div>}
          <div>
            <div className="eyebrow mb-1.5 flex items-center gap-1"><History className="h-3.5 w-3.5" /> {t('act.audit')}</div>
            <ol className="space-y-1 border-l-2 border-line-2 pl-3 text-[0.84rem]">{x.updates.map((u) => <li key={u.id}><span className="text-muted">{u.at.slice(0, 16).replace('T', ' ')}</span> · <b>{u.user_name}</b> — {u.note}</li>)}</ol>
          </div>
        </div>
      )}
    </Drawer>
  )
}

export default function Actions() {
  const { unit, user, t } = useApp()
  const [mine, setMine] = useState(user?.role === 'block' || user?.role === 'headmaster')
  const [open, setOpen] = useState<number | null>(null)
  const [draft, setDraft] = useState(false)
  const q = unit.unit_type === 'state' ? '' : unitQs(unit)
  const acts = useQuery({ queryKey: ['actions', q, mine], queryFn: () => api.get<{ actions: Action[]; summary: ActionSummary }>(`/actions?${q}&mine=${mine}`) })
  if (acts.isError) return <ErrorBox error={acts.error} />
  const s = acts.data?.summary
  const kpis: [string, number | undefined, string?][] = s ? [['act.k.total', s.total], ['act.k.overdue', s.overdue, 'text-brick'], ['act.k.verify', s.awaiting_verification],
    ['act.k.improved', s.implemented_improved, 'text-good'], ['act.k.nochange', s.implemented_no_change, 'text-mustard'], ['act.k.notdone', s.not_implemented, 'text-brick']] : []
  return (
    <div className="space-y-5">
      <PageHeader title={t('act.title')} sub={t('act.sub')}
        right={<>
          {user?.role !== 'headmaster' && <UnitPicker />}
          <label className="btn btn-quiet cursor-pointer"><input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} className="accent-[#1e4d36]" /> {t('c.assignedToMe')}</label>
          {user?.role !== 'headmaster' && <button className="btn btn-primary" disabled={unit.unit_type === 'state'} onClick={() => setDraft(true)}><ClipboardPlus className="h-4 w-4" /> {t('act.draft')}</button>}
          <InfoTip text={t('act.info')} />
        </>} />
      <HelpStrip k="help.actions" />
      {s && (
        <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
          {kpis.map(([k, v, cls]) => <div key={k} className="panel p-4"><div className="text-[0.8rem] font-semibold leading-tight text-ink-2">{t(k)}</div><div className={clsx('num-xl mt-1.5', cls)}>{v}</div></div>)}
        </div>
      )}
      {!acts.data ? <Spinner /> : (
        <div className="grid gap-3 lg:grid-cols-5">
          {COLS.map((c) => {
            const items = acts.data!.actions.filter((a) => colOf(a) === c)
            return (
              <div key={c} className={clsx('rounded-xl border p-3', c === 'overdue' ? 'border-brick/25 bg-brick-50' : 'border-line bg-sunk')}>
                <div className="mb-2.5 flex items-center justify-between px-1"><span className="text-[0.9rem] font-semibold">{t(`act.col.${c}`)}</span><span className="tag">{items.length}</span></div>
                <div className="space-y-2">{items.map((a) => <ActionCard key={a.id} a={a} onClick={() => setOpen(a.id)} />)}</div>
              </div>
            )
          })}
        </div>
      )}
      <ActionDrawer id={open} onClose={() => setOpen(null)} />
      {unit.unit && <DraftActions open={draft} onClose={() => setDraft(false)} unitType={unit.unit_type} unit={unit.unit} />}
    </div>
  )
}
