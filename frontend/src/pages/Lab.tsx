import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { FlaskConical, Play } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { PageHeader } from '../components/Layout'
import { Card, ErrorBox, Spinner } from '../components/ui'
import { useApp } from '../state'

type Scenario = { name: string; description: string; seed: number; mess: Record<string, number>; randomized: boolean; blocks?: Record<string, { district: string; effects: string[]; status: string }> }
type Job = { status: string; progress: number; error: string | null }
const KNOBS = [['missing_months_pct', 0.5], ['duplicate_pct', 0.1], ['name_variant_pct', 0.15], ['incomplete_rows_pct', 0.1]] as const

export default function Lab() {
  const { t, meta } = useApp()
  const qc = useQueryClient()
  const sc = useQuery({ queryKey: ['scenarios'], queryFn: () => api.get<{ scenarios: Scenario[]; active: string }>('/lab/scenarios') })
  const [name, setName] = useState<string | null>(null)
  const [seed, setSeed] = useState('')
  const [mess, setMess] = useState<Record<string, number>>({})
  const [jobId, setJobId] = useState<string | null>(null)
  const cur = sc.data ? sc.data.scenarios.find((s) => s.name === (name ?? sc.data!.active)) ?? sc.data.scenarios[0] : null
  const gen = useMutation({ mutationFn: () => api.post<{ job_id: string }>('/lab/generate', { scenario: cur?.name, seed: seed ? Number(seed) : null, mess, ingest: true }), onSuccess: (r) => setJobId(r.job_id) })
  const job = useQuery({ queryKey: ['labjob', jobId], queryFn: () => api.get<Job>(`/ingest/jobs/${jobId}`), enabled: !!jobId, refetchInterval: (q) => (q.state.data?.status === 'running' ? 800 : false) })
  useEffect(() => { if (job.data?.status === 'done') { setJobId(null); qc.invalidateQueries() } }, [job.data?.status, qc])
  if (!sc.data || !cur) return <Spinner />
  const m = { ...cur.mess, ...mess }
  return (
    <div className="space-y-5">
      <PageHeader title={t('lab.title')} sub={t('lab.sub')} />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card title={t('lab.scenario')} sub={t('lab.active', { s: sc.data.active })}>
          <div className="space-y-2">{sc.data.scenarios.map((s) => (
            <label key={s.name} className={clsx('block cursor-pointer rounded-lg border p-3 text-[0.9rem]', cur.name === s.name ? 'border-forest bg-forest-50' : 'border-line')}>
              <input type="radio" className="mr-2 accent-[#1e4d36]" checked={cur.name === s.name} onChange={() => { setName(s.name); setMess({}) }} />
              <b>{s.name}</b> {s.randomized && <span className="tag ml-1">{t('lab.random')}</span>}
              <div className="mt-1 text-[0.8rem] text-ink-2">{s.description}</div>
            </label>
          ))}</div>
        </Card>
        <Card title={t('lab.knobs')} sub={t('lab.knobsSub')}>
          {KNOBS.map(([k, max]) => (
            <label key={k} className="mb-3 block text-[0.9rem]">
              <div className="flex justify-between"><span>{t(`lab.k.${k}`)}</span><span className="font-semibold tabnum">{Math.round((m[k] ?? 0) * 100)}%</span></div>
              <input type="range" className="w-full accent-[#1e4d36]" min={0} max={max} step={0.01} value={m[k] ?? 0} onChange={(e) => setMess({ ...mess, [k]: Number(e.target.value) })} />
            </label>
          ))}
          <label className="block text-[0.9rem]">{t('lab.seed')} <input className="field ml-2 w-28" placeholder={String(cur.seed)} value={seed} onChange={(e) => setSeed(e.target.value)} /></label>
          <button className="btn btn-primary mt-4" disabled={gen.isPending || !!jobId || meta?.public_demo} onClick={() => gen.mutate()}><Play className="h-4 w-4" /> {t('lab.generate')}</button>
          {meta?.public_demo && <p className="mt-2 text-[0.86rem] text-ink-2">{t('lab.publicOff')}</p>}
          {jobId && <div className="mt-2 text-[0.88rem] text-ink-2"><FlaskConical className="mr-1 inline h-4 w-4 animate-pulse" />{t('lab.running', { p: Math.round((job.data?.progress ?? 0) * 100) })}</div>}
          {gen.isError && <ErrorBox error={gen.error} />}{job.data?.error && <ErrorBox error={job.data.error} />}
        </Card>
        <Card title={t('lab.truth')} sub={t('lab.truthSub')}>
          {cur.blocks ? (
            <div className="max-h-96 overflow-y-auto"><table className="w-full text-[0.84rem]">
              <thead className="text-left text-[0.76rem] text-muted"><tr><th className="py-1 font-medium">{t('lab.th.block')}</th><th className="font-medium">{t('lab.th.planted')}</th><th className="font-medium">{t('lab.th.status')}</th></tr></thead>
              <tbody>{Object.entries(cur.blocks).map(([b, v]) => <tr key={b} className="border-t border-line"><td className="py-1.5 font-semibold">{b}<div className="text-[0.7rem] font-normal text-muted">{v.district}</div></td><td>{v.effects.join(', ') || '—'}</td><td>{v.status}</td></tr>)}</tbody>
            </table></div>
          ) : <div className="text-muted">—</div>}
        </Card>
      </div>
    </div>
  )
}
