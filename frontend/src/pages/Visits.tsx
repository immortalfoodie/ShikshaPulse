// School visits for Cluster Resource Coordinators — phone-first, works offline, syncs when back online.
import { useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { CheckCircle2, CloudOff, CloudUpload, FlaskConical, Wifi } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { PageHeader, UnitPicker } from '../components/Layout'
import { Card, HelpStrip, InfoTip, Spinner } from '../components/ui'
import { unitQs, useApp, useFocusBlock } from '../state'

const ITEMS = ['teacher_teaching', 'materials_used', 'level_groups', 'children_practice', 'checks_understanding', 'time_on_maths']
const QUEUE = 'sp_visit_queue'
type Visit = { client_id: string; udise_code: string; visit_date: string; answers: Record<string, string>; children_present?: number; children_enrolled?: number; notes?: string; recorded_offline?: boolean }
type School = { udise_code: string; school_name: string; cluster: string }
type VisitRow = { id: number; school_name: string; visit_date: string; score: number; visitor: string; is_simulated: boolean; answers: Record<string, string> }
type Summary = { n_visits: number; n_schools: number; avg_score: number; items: { item: string; pct_yes: number }[] } | null

const readQueue = (): Visit[] => JSON.parse(localStorage.getItem(QUEUE) || '[]')
const writeQueue = (q: Visit[]) => localStorage.setItem(QUEUE, JSON.stringify(q))

export function useVisitSync() {
  const qc = useQueryClient()
  const [pending, setPending] = useState(readQueue().length)
  const [online, setOnline] = useState(navigator.onLine)
  const sync = useCallback(async () => {
    const q = readQueue()
    if (!q.length || !navigator.onLine) return
    try {
      await api.post('/visits', { visits: q })
      writeQueue([])
      setPending(0)
      qc.invalidateQueries({ queryKey: ['visits'] })
      qc.invalidateQueries({ queryKey: ['diagnose'] })
    } catch { /* stay queued */ }
  }, [qc])
  useEffect(() => {
    const on = () => { setOnline(true); sync() }
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    sync()
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off) }
  }, [sync])
  return { pending, setPending, online, sync }
}

export default function Visits() {
  const { t, user, meta } = useApp()
  const today = meta?.today ?? new Date().toISOString().slice(0, 10)
  const block = useFocusBlock()
  const unitQ = block ? unitQs({ unit_type: 'block', unit: block }) : ''
  const schools = useQuery({ queryKey: ['schools', block], queryFn: () => api.get<School[]>(`/schools?${unitQ}`), enabled: !!block })
  const visits = useQuery({ queryKey: ['visits', block], queryFn: () => api.get<{ visits: VisitRow[]; summary: Summary }>(`/visits?${unitQ}`), enabled: !!block })
  const { pending, setPending, online, sync } = useVisitSync()
  const blank = () => ({ udise_code: '', visit_date: today, answers: {} as Record<string, string>, children_present: undefined as number | undefined, children_enrolled: undefined as number | undefined, notes: '' })
  const [form, setForm] = useState(blank())
  const [msg, setMsg] = useState<string | null>(null)
  const complete = form.udise_code && ITEMS.every((k) => form.answers[k])
  async function save() {
    const v: Visit = { ...form, client_id: `${user?.id}-${Date.now()}`, recorded_offline: !navigator.onLine }
    writeQueue([...readQueue(), v])
    setPending(readQueue().length)
    setForm(blank())
    if (navigator.onLine) { await sync(); setMsg(t('vis.saved')) } else setMsg(t('vis.savedOffline'))
    setTimeout(() => setMsg(null), 4000)
  }
  const s = visits.data?.summary
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHeader title={t('vis.title')} sub={t('vis.sub')} right={<><UnitPicker blocksOnly block={block} /><InfoTip text={t('vis.info')} /></>} />
      <div className="flex flex-wrap items-center gap-2">
        <span className={clsx('tag', online ? '!text-good' : '!text-brick')}>{online ? <Wifi className="h-3.5 w-3.5" /> : <CloudOff className="h-3.5 w-3.5" />}{t(online ? 'vis.online' : 'vis.offline')}</span>
        {pending > 0 && <><span className="tag !text-mustard">{t('vis.pending', { n: pending })}</span><button className="btn btn-quiet !min-h-8 !py-1" onClick={sync} disabled={!online}><CloudUpload className="h-4 w-4" /> {t('vis.sync')}</button></>}
      </div>
      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <Card title={t('vis.new')}>
          <label className="block"><span className="eyebrow">{t('vis.school')}</span>
            <select className="field mt-1 w-full !min-h-12 !text-[1rem]" value={form.udise_code} onChange={(e) => setForm({ ...form, udise_code: e.target.value })}>
              <option value="">{t('vis.pick')}</option>
              {schools.data?.map((x) => <option key={x.udise_code} value={x.udise_code}>{x.school_name} · {x.cluster}</option>)}
            </select></label>
          <ol className="mt-4 space-y-3">
            {ITEMS.map((k, i) => (
              <li key={k} className="panel-sunk p-3">
                <div className="text-[0.98rem] font-semibold"><span className="mr-1.5 text-muted">{i + 1}.</span>{t(`q.${k}`)}</div>
                <div className="mt-2 grid grid-cols-3 gap-2">
                  {(['yes', 'partly', 'no'] as const).map((v) => (
                    <button key={v} type="button" aria-pressed={form.answers[k] === v} onClick={() => setForm({ ...form, answers: { ...form.answers, [k]: v } })}
                      className={clsx('btn !min-h-12 justify-center !text-[1rem]', form.answers[k] === v ? (v === 'yes' ? 'bg-s1 text-surface' : v === 'partly' ? 'btn-accent' : 'bg-brick text-surface') : 'btn-quiet')}>
                      {t(`vis.${v}`)}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <label className="block"><span className="eyebrow">{t('vis.date')}</span><input type="date" className="field mt-1 w-full" value={form.visit_date} onChange={(e) => setForm({ ...form, visit_date: e.target.value })} /></label>
            <label className="block"><span className="eyebrow">{t('vis.present')}</span><input type="number" inputMode="numeric" className="field mt-1 w-full" value={form.children_present ?? ''} onChange={(e) => setForm({ ...form, children_present: e.target.value ? Number(e.target.value) : undefined })} /></label>
            <label className="block"><span className="eyebrow">{t('vis.enrolled')}</span><input type="number" inputMode="numeric" className="field mt-1 w-full" value={form.children_enrolled ?? ''} onChange={(e) => setForm({ ...form, children_enrolled: e.target.value ? Number(e.target.value) : undefined })} /></label>
          </div>
          <label className="mt-3 block"><span className="eyebrow">{t('vis.notes')}</span><textarea className="field mt-1 w-full" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button className="btn btn-primary !min-h-12 !px-6 !text-[1rem]" disabled={!complete} onClick={save}><CheckCircle2 className="h-5 w-5" /> {t('vis.save')}</button>
            {!complete && <span className="text-[0.84rem] text-muted">{t('vis.needAll')}</span>}
            {msg && <span className="text-[0.9rem] font-semibold text-good">{msg}</span>}
          </div>
        </Card>
        <div className="space-y-5">
          <Card title={t('vis.summary')} info={t('vis.scoreInfo')}>
            {!visits.data ? <Spinner /> : !s ? <div className="text-ink-2">{t('vis.none')}</div> : (
              <>
                <div className="flex items-end gap-3"><div className="num-xl">{s.avg_score}<span className="text-[1rem] font-medium text-muted">/100</span></div><div className="pb-1 text-[0.85rem] text-ink-2">{t('vis.score')}</div></div>
                <div className="mt-1 text-[0.85rem] text-muted">{t('vis.visits', { n: s.n_visits, s: s.n_schools })}</div>
                <div className="eyebrow mt-4 mb-1">{t('vis.weakest')}</div>
                <ul className="space-y-2">{s.items.map((it) => (
                  <li key={it.item}>
                    <div className="flex justify-between text-[0.86rem]"><span>{t(`i.${it.item}`)}</span><span className="tabnum font-semibold">{it.pct_yes}%</span></div>
                    <div className="mt-1 h-2 rounded-full bg-sunk"><div className="h-2 rounded-full" style={{ width: `${it.pct_yes}%`, background: it.pct_yes < 34 ? '#b4432a' : it.pct_yes < 67 ? '#dd8f22' : '#1f7a4a' }} /></div>
                  </li>
                ))}</ul>
              </>
            )}
          </Card>
          <Card title={t('vis.recent')}>
            {visits.data && visits.data.visits.length === 0 && <div className="text-ink-2">{t('vis.none')}</div>}
            <ul className="divide-y divide-line">{visits.data?.visits.slice(0, 8).map((v) => (
              <li key={v.id} className="flex items-center justify-between gap-2 py-2 text-[0.86rem]">
                <span className="min-w-0"><span className="block truncate font-semibold">{v.school_name}</span><span className="text-muted">{v.visit_date} · {t('vis.by', { v: v.visitor })}{v.is_simulated && <> · <FlaskConical className="inline h-3 w-3" /> {t('c.simulated')}</>}</span></span>
                <span className="tabnum shrink-0 font-semibold">{v.score}</span>
              </li>
            ))}</ul>
          </Card>
        </div>
      </div>
      <HelpStrip k="help.visits" />
    </div>
  )
}
