// Action tracker: kanban board of assigned actions, with a drawer to update, measure and verify each one.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ClipboardPlus,
  FlaskConical,
  History,
  Paperclip,
  UserRound,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { api } from '../api'
import { DraftActions } from '../components/DraftActions'
import { PageHeader, UnitPicker } from '../components/Layout'
import { Drawer, ErrorBox, HelpStrip, InfoTip, OutcomeBadge, Spinner } from '../components/ui'
import { ACTION_COLUMNS, actionColumn, useActionTitle } from '../lib/actions'
import { C } from '../lib/format'
import { unitQs, useApp } from '../state'
import type { Action, ActionSummary, Measurement } from '../types'

const CLOSED_STATUSES = ['verified', 'closed_not_implemented']
const OFFICER_ROLES = ['district', 'state']

function SimulatedTag() {
  const { t } = useApp()
  return (
    <span className="tag !text-muted">
      <FlaskConical className="h-3 w-3" /> {t('c.simulated')}
    </span>
  )
}

/** Compact card shown in a board column. */
function ActionCard({ action, onClick }: { action: Action; onClick: () => void }) {
  const { t } = useApp()
  const title = useActionTitle()
  return (
    <button
      onClick={onClick}
      className={clsx(
        'panel w-full p-3 text-left transition hover:border-forest',
        action.overdue && '!border-brick/50',
      )}
    >
      <div className="text-[0.92rem] font-semibold leading-snug">{title(action)}</div>
      <div className="mt-1.5 grid gap-0.5 text-[0.78rem] text-ink-2">
        <span className="inline-flex items-center gap-1">
          <UserRound className="h-3.5 w-3.5" />
          {action.owner_name}
        </span>
        <span className="inline-flex items-center gap-1">
          <CalendarClock className="h-3.5 w-3.5" />
          {action.due_date}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        <OutcomeBadge s={action.outcome_status} />
        {action.priority === 'High' && <span className="tag !text-brick">{t('c.priorityHigh')}</span>}
        {action.is_simulated && <SimulatedTag />}
      </div>
    </button>
  )
}

/** Progress bar colour for implementation coverage (ratio of target reached). */
const implementationColor = (ratio: number) => {
  if (ratio >= 0.8) return C.good
  if (ratio >= 0.5) return C.s2
  return C.brick
}

/** Colour for a learning-outcome change in points: ±2 is the meaningful threshold. */
const learningChangeColor = (change: number) => {
  if (change >= 2) return C.good
  if (change <= -2) return C.brick
  return C.ink2
}

/** Latest implementation or learning measurement compared with its target / baseline. */
function MeasureBlock({ measurement, all }: { measurement: Measurement; all: Measurement[] }) {
  const { t } = useApp()
  const latest = [...all].reverse().find((entry) => entry.kind === measurement.kind && entry.value !== null)
  const label = measurement.unit ?? measurement.indicator

  if (measurement.kind === 'implementation') {
    const ratio = latest && measurement.target ? Math.min(1.2, latest.value! / measurement.target) : 0
    return (
      <div className="panel-sunk p-3.5">
        <div className="eyebrow flex items-center gap-1">
          {t('act.impl')} <InfoTip text={t('act.implInfo')} />
        </div>
        <div className="mt-0.5 text-[0.9rem] font-medium">{label}</div>
        <div className="mt-2 h-3 w-full rounded-full bg-surface ring-1 ring-line">
          <div
            className="h-3 rounded-full"
            style={{ width: `${Math.min(100, ratio * 100)}%`, background: implementationColor(ratio) }}
          />
        </div>
        <div className="mt-1 text-[0.82rem] text-ink-2 tabnum">
          {latest
            ? t('act.ofTarget', { v: latest.value, t: measurement.target, p: Math.round(ratio * 100) })
            : t('act.notReported', { t: measurement.target })}
        </div>
      </div>
    )
  }

  const change =
    latest && measurement.baseline !== null ? Math.round((latest.value! - measurement.baseline) * 10) / 10 : null
  return (
    <div className="panel-sunk p-3.5">
      <div className="eyebrow flex items-center gap-1">
        {t('act.learn')} <InfoTip text={t('act.learnInfo')} />
      </div>
      <div className="mt-0.5 text-[0.9rem] font-medium">{label}</div>
      <div className="mt-1 text-[0.86rem] tabnum">
        {measurement.baseline ?? '—'} ({measurement.baseline_date}) →{' '}
        {latest ? `${latest.value} (${latest.measured_at})` : t('act.pending')}
        {change !== null && (
          <b style={{ color: learningChangeColor(change) }}>
            {' '}
            {change > 0 ? '+' : ''}
            {change} {t('c.pts')}
          </b>
        )}
      </div>
    </div>
  )
}

/** Small labelled field in the drawer's facts grid. */
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      {children}
    </div>
  )
}

/** Slide-over with full action details, status/measurement/evidence updates and the audit trail. */
export function ActionDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const { user, t } = useApp()
  const title = useActionTitle()
  const actionQuery = useQuery({
    queryKey: ['action', id],
    queryFn: () => api.get<Action>(`/actions/${id}`),
    enabled: id !== null,
  })
  const [note, setNote] = useState('')
  const [value, setValue] = useState('')
  const [file, setFile] = useState<File | null>(null)

  const refresh = () => {
    for (const key of ['action', 'actions', 'actions-summary', 'my-school']) {
      queryClient.invalidateQueries({ queryKey: key === 'action' ? ['action', id] : [key] })
    }
  }
  const statusMutation = useMutation({
    mutationFn: (status: string) =>
      api.post(`/actions/${id}/status`, { status, note, evidence_note: note || undefined }),
    onSuccess: () => {
      setNote('')
      refresh()
    },
  })
  const measureMutation = useMutation({
    mutationFn: (kind: string) =>
      api.post(`/actions/${id}/measurement`, { kind, value: Number(value), evidence: note }),
    onSuccess: () => {
      setValue('')
      refresh()
    },
  })
  const uploadMutation = useMutation({
    mutationFn: () => {
      const form = new FormData()
      form.append('file', file!)
      form.append('note', note)
      return api.upload(`/actions/${id}/evidence`, form)
    },
    onSuccess: () => {
      setFile(null)
      refresh()
    },
  })

  if (id === null) return null
  const action = actionQuery.data
  const isOfficer = user && OFFICER_ROLES.includes(user.role)
  const error = statusMutation.error || measureMutation.error || uploadMutation.error
  const setStatus = (status: string) => () => statusMutation.mutate(status)
  // One block per measurement kind (the first entry of each kind).
  const measurementKinds = action?.measurements.filter(
    (entry, index, list) => list.findIndex((other) => other.kind === entry.kind) === index,
  )

  return (
    <Drawer open onClose={onClose} title={action ? title(action) : ''} width="max-w-2xl">
      {!action ? (
        <Spinner />
      ) : (
        <div className="space-y-5 text-[0.92rem]">
          <div className="flex flex-wrap gap-1.5">
            <OutcomeBadge s={action.outcome_status} />
            <span className="tag">{t(`st.${action.status}`)}</span>
            {action.is_simulated && <SimulatedTag />}
          </div>
          {action.overdue && (
            <div className="flex items-center gap-2 rounded-lg border-l-4 border-brick bg-brick-50 p-3 text-brick">
              <AlertTriangle className="h-4 w-4" />{' '}
              {t('act.overdueBy', { n: Math.abs(action.days_to_due ?? 0), who: action.created_by })}
            </div>
          )}
          <div className="grid grid-cols-2 gap-4 text-[0.88rem]">
            <Fact label={t('act.owner')}>
              {action.owner_name}
              <div className="text-muted">{action.owner_role}</div>
            </Fact>
            <Fact label={t('act.deadline')}>{action.due_date}</Fact>
            <Fact label={t('act.assignedBy')}>
              {action.created_by} · {action.created_at.slice(0, 10)}
            </Fact>
            <Fact label={t('act.verified')}>
              {action.verified_by ? `${action.verified_by} · ${action.verified_at?.slice(0, 10)}` : '—'}
            </Fact>
          </div>
          <div>
            <div className="eyebrow">{t('act.why')}</div>
            <p className="text-ink-2">{action.description}</p>
          </div>
          {action.schools.length > 0 && (
            <div className="text-[0.86rem]">
              <div className="eyebrow">{t('act.schools')}</div>
              {action.schools.map((school) => (typeof school === 'string' ? school : school.school_name)).join(', ')}
            </div>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            {measurementKinds?.map((entry) => (
              <MeasureBlock key={entry.id} measurement={entry} all={action.measurements} />
            ))}
          </div>
          {(action.evidence_note || action.evidence_file) && (
            <div className="panel-sunk p-3 text-[0.86rem]">
              <div className="eyebrow">{t('act.proof')}</div>
              {action.evidence_note}
              {action.evidence_file && (
                <div className="mt-0.5 flex items-center gap-1">
                  <Paperclip className="h-3.5 w-3.5" />
                  {action.evidence_file}
                </div>
              )}
            </div>
          )}
          {action.can_update === false ? (
            <div className="panel-sunk p-3 text-[0.88rem] text-ink-2">
              {t('act.readOnly', { o: action.owner_name })}
            </div>
          ) : (
            <div className="panel p-4">
              <div className="eyebrow mb-2">{t('act.update')}</div>
              <textarea
                className="field w-full"
                rows={2}
                placeholder={t('act.note')}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
              <div className="mt-2 flex flex-wrap gap-2">
                {action.status === 'open' && (
                  <button className="btn btn-quiet" onClick={setStatus('in_progress')}>
                    {t('act.start')}
                  </button>
                )}
                {['open', 'in_progress'].includes(action.status) && (
                  <button className="btn btn-primary" onClick={setStatus('awaiting_verification')}>
                    {t('act.submit')}
                  </button>
                )}
                {action.status === 'awaiting_verification' && isOfficer && (
                  <button className="btn btn-primary" onClick={setStatus('verified')}>
                    <CheckCircle2 className="h-4 w-4" /> {t('act.verify')}
                  </button>
                )}
                {action.status === 'awaiting_verification' && isOfficer && (
                  <button className="btn btn-quiet" onClick={setStatus('in_progress')}>
                    {t('act.sendBack')}
                  </button>
                )}
                {!CLOSED_STATUSES.includes(action.status) && isOfficer && (
                  <button className="btn btn-quiet" onClick={setStatus('closed_not_implemented')}>
                    {t('act.closeNot')}
                  </button>
                )}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input
                  className="field w-28"
                  type="number"
                  placeholder={t('act.value')}
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                />
                <button
                  className="btn btn-quiet"
                  disabled={!value}
                  onClick={() => measureMutation.mutate('implementation')}
                >
                  {t('act.recordImpl')}
                </button>
                <button className="btn btn-quiet" disabled={!value} onClick={() => measureMutation.mutate('learning')}>
                  {t('act.recordLearn')}
                </button>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input
                  type="file"
                  className="text-[0.82rem]"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
                <button className="btn btn-quiet" disabled={!file} onClick={() => uploadMutation.mutate()}>
                  <Paperclip className="h-4 w-4" /> {t('act.upload')}
                </button>
              </div>
              {error && (
                <div className="mt-2">
                  <ErrorBox error={error} />
                </div>
              )}
            </div>
          )}
          <div>
            <div className="eyebrow mb-1.5 flex items-center gap-1">
              <History className="h-3.5 w-3.5" /> {t('act.audit')}
            </div>
            <ol className="space-y-1 border-l-2 border-line-2 pl-3 text-[0.84rem]">
              {action.updates.map((update) => (
                <li key={update.id}>
                  <span className="text-muted">{update.at.slice(0, 16).replace('T', ' ')}</span> ·{' '}
                  <b>{update.user_name}</b> — {update.note}
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </Drawer>
  )
}

/** [translation key, value, optional colour class] for the KPI strip. */
type Kpi = [string, number | undefined, string?]

function summaryKpis(summary: ActionSummary): Kpi[] {
  return [
    ['act.k.total', summary.total],
    ['act.k.overdue', summary.overdue, 'text-brick'],
    ['act.k.verify', summary.awaiting_verification],
    ['act.k.improved', summary.implemented_improved, 'text-good'],
    ['act.k.nochange', summary.implemented_no_change, 'text-mustard'],
    ['act.k.notdone', summary.not_implemented, 'text-brick'],
  ]
}

/** Actions page: KPI strip, kanban board and drafting entry point. */
export default function Actions() {
  const { unit, user, t } = useApp()
  const [mineOnly, setMineOnly] = useState(user?.role === 'block' || user?.role === 'headmaster')
  const [openActionId, setOpenActionId] = useState<number | null>(null)
  const [drafting, setDrafting] = useState(false)
  const query = unit.unit_type === 'state' ? '' : unitQs(unit)
  const actions = useQuery({
    queryKey: ['actions', query, mineOnly],
    queryFn: () => api.get<{ actions: Action[]; summary: ActionSummary }>(`/actions?${query}&mine=${mineOnly}`),
  })
  if (actions.isError) return <ErrorBox error={actions.error} />
  const summary = actions.data?.summary
  const canDraft = user?.role !== 'headmaster'

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('act.title')}
        sub={t('act.sub')}
        right={
          <>
            {canDraft && <UnitPicker />}
            <label className="btn btn-quiet cursor-pointer">
              <input
                type="checkbox"
                checked={mineOnly}
                onChange={(event) => setMineOnly(event.target.checked)}
                className="accent-[#1e4d36]"
              />{' '}
              {t('c.assignedToMe')}
            </label>
            {canDraft && (
              <button
                className="btn btn-primary"
                disabled={unit.unit_type === 'state'}
                onClick={() => setDrafting(true)}
              >
                <ClipboardPlus className="h-4 w-4" /> {t('act.draft')}
              </button>
            )}
            <InfoTip text={t('act.info')} />
          </>
        }
      />
      <HelpStrip k="help.actions" />
      {summary && (
        <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
          {summaryKpis(summary).map(([key, value, colorClass]) => (
            <div key={key} className="panel p-4">
              <div className="text-[0.8rem] font-semibold leading-tight text-ink-2">{t(key)}</div>
              <div className={clsx('num-xl mt-1.5', colorClass)}>{value}</div>
            </div>
          ))}
        </div>
      )}
      {!actions.data ? (
        <Spinner />
      ) : (
        <div className="grid gap-3 lg:grid-cols-5">
          {ACTION_COLUMNS.map((column) => {
            const items = actions.data.actions.filter((action) => actionColumn(action) === column)
            return (
              <div
                key={column}
                className={clsx(
                  'rounded-xl border p-3',
                  column === 'overdue' ? 'border-brick/25 bg-brick-50' : 'border-line bg-sunk',
                )}
              >
                <div className="mb-2.5 flex items-center justify-between px-1">
                  <span className="text-[0.9rem] font-semibold">{t(`act.col.${column}`)}</span>
                  <span className="tag">{items.length}</span>
                </div>
                <div className="space-y-2">
                  {items.map((action) => (
                    <ActionCard key={action.id} action={action} onClick={() => setOpenActionId(action.id)} />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
      <ActionDrawer id={openActionId} onClose={() => setOpenActionId(null)} />
      {unit.unit && (
        <DraftActions open={drafting} onClose={() => setDrafting(false)} unitType={unit.unit_type} unit={unit.unit} />
      )}
    </div>
  )
}
