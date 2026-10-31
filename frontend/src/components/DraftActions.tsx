// Suggested tasks from the intervention library — edited and assigned by the officer, never auto-ordered.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ClipboardCheck } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import { useApp } from '../state'
import { PairList, TrackRecordLine, type Pair, type TrackRecord } from './Smart'
import { ErrorBox, InfoTip, Modal, Spinner } from './ui'

type Draft = {
  intervention_key: string
  trigger: string
  title: string
  description: string
  owner_role: string
  unit_type: string
  unit: string
  priority: string
  due_date: string
  schools: { udise_code: string; school_name: string }[]
  alternatives: { key: string; title: string }[]
  evidence: unknown[]
  issue_title: string
  rationale_by?: string
  implementation: { label: string }
  learning: { label: string }
  track_record?: TrackRecord
  sharing?: Pair[]
}
type Owner = { id: string; name: string; role: string }

export function DraftActions({
  open,
  onClose,
  unitType,
  unit,
  schools,
}: {
  open: boolean
  onClose: () => void
  unitType: string
  unit: string
  schools?: string[]
}) {
  const qc = useQueryClient()
  const { user, t } = useApp()
  const drafts = useQuery({
    queryKey: ['drafts', unitType, unit, schools?.join(',')],
    queryFn: () => api.post<{ drafts: Draft[] }>('/actions/draft', { unit_type: unitType, unit, schools }),
    enabled: open,
  })
  const owners = useQuery({
    queryKey: ['owners', unitType, unit],
    queryFn: () => api.get<Owner[]>(`/owners?unit_type=${unitType}&unit=${unit}`),
    enabled: open,
  })
  const [edits, setEdits] = useState<Record<number, { owner_id?: string; due_date?: string }>>({})
  const [created, setCreated] = useState<number[]>([])
  function defaultOwner(d: Draft) {
    const o = owners.data ?? []
    if (d.owner_role.includes('District')) return o.find((x) => x.role.includes('District'))?.id
    const blk = d.unit_type === 'block' ? d.unit : null
    return (
      (blk && o.find((x) => x.role.includes(`Block Education Officer, ${blk}`))?.id) ||
      o.find((x) => x.role.includes('Block Education Officer'))?.id
    )
  }
  const create = useMutation({
    mutationFn: async (i: number) => {
      const d = { ...drafts.data!.drafts[i], ...edits[i] }
      const owner = owners.data?.find((o) => o.id === (edits[i]?.owner_id ?? defaultOwner(d)))
      // Stored in English; every viewer sees it in their own language via the intervention key.
      return api.post('/actions', {
        ...d,
        owner_name: owner?.name ?? d.owner_role,
        owner_id: owner?.id,
        owner_role: owner?.role ?? d.owner_role,
      })
    },
    onSuccess: (_, i) => {
      setCreated((c) => [...c, i])
      qc.invalidateQueries({ queryKey: ['actions'] })
      qc.invalidateQueries({ queryKey: ['actions-summary'] })
    },
  })
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={
        <span className="flex items-center gap-2">
          <ClipboardCheck className="h-5 w-5 text-forest" /> {t('act.draftTitle', { unit })}
        </span>
      }
    >
      {drafts.isLoading && <Spinner />}
      {drafts.isError && <ErrorBox error={drafts.error} />}
      {drafts.data && (
        <div className="space-y-3">
          <p className="text-[0.88rem] text-ink-2">{t('act.draftNote')}</p>
          {drafts.data.drafts.length === 0 && <div>{t('act.draftNone')}</div>}
          {drafts.data.drafts.map((d, i) => {
            const e = edits[i] ?? {}
            const done = created.includes(i)
            const title = t(`iv.${d.intervention_key}`)
            return (
              <div key={i} className="panel p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="text-[1.02rem] font-semibold">
                    {title === `iv.${d.intervention_key}` ? d.title : `${title} — ${d.unit}`}
                  </div>
                  <span className={d.priority === 'High' ? 'tag !border-brick/30 !bg-brick-50 !text-brick' : 'tag'}>
                    {d.priority === 'High' ? t('c.priorityHigh') : t('c.priority', { p: d.priority })}
                  </span>
                </div>
                <p className="mt-1.5 text-[0.88rem] text-ink-2">
                  {d.description}{' '}
                  {d.rationale_by === 'ai' && (
                    <span className="text-[0.76rem] text-muted">({t('act.aiRationale')})</span>
                  )}
                </p>
                <div className="mt-3 grid gap-3 text-[0.86rem] md:grid-cols-3">
                  <label className="block">
                    <span className="eyebrow">{t('act.owner')}</span>
                    <select
                      className="field mt-1 w-full"
                      value={e.owner_id ?? defaultOwner(d) ?? ''}
                      onChange={(ev) => setEdits({ ...edits, [i]: { ...e, owner_id: ev.target.value } })}
                      disabled={done}
                    >
                      {owners.data?.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.name} — {o.role}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="eyebrow">{t('act.deadline')}</span>
                    <input
                      type="date"
                      className="field mt-1 w-full"
                      value={e.due_date ?? d.due_date}
                      onChange={(ev) => setEdits({ ...edits, [i]: { ...e, due_date: ev.target.value } })}
                      disabled={done}
                    />
                  </label>
                  <div>
                    <span className="eyebrow flex items-center gap-1">
                      {t('act.tracks')} <InfoTip text={`${t('act.implInfo')} ${t('act.learnInfo')}`} />
                    </span>
                    <div className="mt-1">
                      {t('act.impl')} <b>{d.implementation.label}</b>
                      <br />
                      {t('act.learn')} <b>{d.learning.label}</b>
                    </div>
                  </div>
                </div>
                <div className="mt-3">
                  <TrackRecordLine tr={d.track_record} />
                </div>
                {d.sharing && (
                  <div className="mt-3">
                    <div className="eyebrow mb-1 flex items-center gap-1">
                      {t('share.title')} <InfoTip text={t('share.info')} />
                    </div>
                    <PairList pairs={d.sharing} limit={3} />
                  </div>
                )}
                {d.schools.length > 0 && (
                  <div className="mt-2 text-[0.82rem] text-ink-2">
                    {t('act.schools')} ({d.schools.length}):{' '}
                    {d.schools
                      .slice(0, 6)
                      .map((s) => s.school_name)
                      .join(', ')}
                    {d.schools.length > 6 ? '…' : ''}
                  </div>
                )}
                {d.alternatives.length > 0 && (
                  <div className="mt-1 text-[0.78rem] text-muted">
                    {t('act.alternatives')}:{' '}
                    {d.alternatives
                      .map((a) => (t(`iv.${a.key}`) === `iv.${a.key}` ? a.title : t(`iv.${a.key}`)))
                      .join(' · ')}
                  </div>
                )}
                <div className="mt-3 flex justify-end">
                  {done ? (
                    <span className="tag !text-forest">
                      <CheckCircle2 className="h-3.5 w-3.5" /> {t('act.assigned')}
                    </span>
                  ) : (
                    <button
                      className="btn btn-primary"
                      disabled={create.isPending || user?.role === 'headmaster'}
                      onClick={() => create.mutate(i)}
                    >
                      {t('act.assign')}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
          {create.isError && <ErrorBox error={create.error} />}
        </div>
      )}
    </Modal>
  )
}
