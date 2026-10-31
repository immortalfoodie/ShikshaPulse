import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  CheckCircle2,
  Clock,
  Eye,
  FileSpreadsheet,
  GitMerge,
  Lock,
  Play,
  ScanSearch,
  Upload,
  XCircle,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { PageHeader } from '../components/Layout'
import { Card, ErrorBox, HelpStrip, InfoTip, Modal, Spinner } from '../components/ui'
import { useApp } from '../state'

type Col = {
  source: string
  target: string | null
  confidence: number
  method: string
  reason?: string
  sample: string[]
}
type FilePreview = {
  file: string
  kind: string
  kind_confidence: number
  year_hint: string | null
  columns: Col[]
  wide_month_columns: string[]
  required_missing: string[]
  ai_note: string | null
}
type Preview = { preview_id: string; files: FilePreview[]; llm: { available: boolean } }
type Job = {
  status: string
  progress: number
  steps: { step: string; detail: string; t: number }[]
  result: Summary | null
  error: string | null
}
type Summary = {
  seconds: number | null
  files: number
  schools: number
  years: string[]
  rows_in: number
  rows_out: number
  duplicates_removed: number
  matched_by_name: number
  review_groups: number
  review_rows: number
}
type Review = {
  id: number
  source_file: string
  kind: string
  academic_year: string
  block: string
  name_variant: string
  n_rows: number
  candidates: { udise_code: string; school_name: string; block: string; score: number }[]
}
type Sources = {
  adapters: { key: string; available: boolean; requirements: Record<string, string> }[]
  files: Record<string, { name: string; size_kb: number }[]>
  scenario: string
}
type Quality = {
  ready: boolean
  completeness_by_year: Record<string, Record<string, number>>
  comparability_flags: { unit_type: string; unit: string; from_year: string; to_year: string; reason: string }[]
  files: {
    file: string
    kind: string
    academic_year: string
    rows_in: number
    rows_out: number
    exact_duplicates: number
    key_duplicates: number
    matched_by_name: number
    review_rows: number
    transforms: string[]
    mapping_version: string
  }[]
  confidence: number
}

const TARGETS: Record<string, string[]> = {
  assessment: [
    'udise_code',
    'school_name',
    'district',
    'block',
    'academic_year',
    'grade',
    'subject',
    'score',
    'score_maths',
    'score_language',
    'max_marks',
    'students_assessed',
    'assessment_type',
  ],
  attendance: ['udise_code', 'school_name', 'block', 'month', 'cal_year', 'student_att', 'teacher_att', 'days_open'],
  teachers: ['udise_code', 'school_name', 'block', 'subject', 'sanctioned', 'working', 'vacant', 'snapshot_date'],
  udise: [
    'udise_code',
    'school_name',
    'district',
    'block',
    'cluster',
    'management',
    'location',
    'enrolment',
    'grade3_enrolment',
    'electricity',
    'drinking_water',
    'functional_toilet',
    'adequate_classrooms',
    'library',
    'ramp',
    'academic_year',
  ],
  context: ['district', 'block', 'event', 'start', 'end', 'teacher_days_lost', 'source'],
}
const METHOD: Record<string, string> = {
  dictionary: 'bg-sunk text-ink-2',
  fuzzy: 'bg-forest-50 text-forest',
  profile: 'bg-good-50 text-good',
  ai: 'bg-saffron-50 text-mustard',
  manual: 'bg-mustard-50 text-mustard',
  unmapped: 'bg-brick-50 text-brick',
}

function RawPreview({ adapter, file, onClose }: { adapter: string; file: string | null; onClose: () => void }) {
  const { t } = useApp()
  const r = useQuery({
    queryKey: ['raw', adapter, file],
    queryFn: () =>
      api.get<{ columns: string[]; rows: string[][] }>(
        `/ingest/raw?adapter=${adapter}&file=${encodeURIComponent(file!)}`,
      ),
    enabled: !!file,
  })
  return (
    <Modal open={!!file} onClose={onClose} title={t('data.rawTitle', { f: file })}>
      {!r.data ? (
        <Spinner />
      ) : (
        <div className="overflow-auto rounded-md border border-line">
          <table className="text-[0.76rem]">
            <thead>
              <tr>
                {r.data.columns.map((c) => (
                  <th
                    key={c}
                    className="whitespace-nowrap border-b border-line bg-sunk px-2 py-1.5 text-left font-semibold"
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.data.rows.map((row, i) => (
                <tr key={i}>
                  {row.map((v, j) => (
                    <td
                      key={j}
                      className={clsx(
                        'whitespace-nowrap border-b border-line px-2 py-1',
                        !v && 'bg-brick-50 text-brick',
                      )}
                    >
                      {v || '∅'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  )
}

function ReviewQueue() {
  const { t } = useApp()
  const qc = useQueryClient()
  const rv = useQuery({ queryKey: ['review'], queryFn: () => api.get<Review[]>('/ingest/review') })
  const resolve = useMutation({
    mutationFn: ({ id, code }: { id: number; code: string | null }) =>
      api.post(`/ingest/review/${id}`, { udise_code: code }),
    onSuccess: () => qc.invalidateQueries(),
  })
  const bulk = useMutation({
    mutationFn: () => api.post<{ accepted: number; remaining: number }>('/ingest/review-bulk', { min_score: 90 }),
    onSuccess: () => qc.invalidateQueries(),
  })
  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <GitMerge className="h-4 w-4 text-forest" />
          {t('data.review')}
        </span>
      }
      sub={t('data.reviewSub')}
      info={t('data.reviewInfo')}
      right={
        <button className="btn btn-quiet" disabled={bulk.isPending || !rv.data?.length} onClick={() => bulk.mutate()}>
          {t('data.acceptTop')}
        </button>
      }
    >
      {bulk.data && (
        <div className="mb-2 text-[0.86rem] text-good">
          {t('data.accepted', { a: bulk.data.accepted, r: bulk.data.remaining })}
        </div>
      )}
      {!rv.data ? (
        <Spinner />
      ) : rv.data.length === 0 ? (
        <div className="flex items-center gap-2 text-good">
          <CheckCircle2 className="h-4 w-4" />
          {t('data.queueEmpty')}
        </div>
      ) : (
        <div className="max-h-96 divide-y divide-line overflow-y-auto">
          {rv.data.map((r) => (
            <div key={r.id} className="py-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <b className="text-[0.98rem]">“{r.name_variant}”</b>
                <span className="text-[0.78rem] text-muted">
                  {r.block} · {t(`kind.${r.kind}`)} {r.academic_year} · {r.n_rows} · {r.source_file}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {r.candidates.map((c) => (
                  <button
                    key={c.udise_code}
                    className="btn btn-quiet !min-h-9 !py-1 !text-[0.84rem] hover:!border-forest"
                    onClick={() => resolve.mutate({ id: r.id, code: c.udise_code })}
                  >
                    <CheckCircle2 className="h-4 w-4 text-s1" /> {c.school_name}{' '}
                    <span className="text-muted">
                      ({c.block} · {c.score})
                    </span>
                  </button>
                ))}
                <button
                  className="btn btn-quiet !min-h-9 !py-1 !text-[0.84rem] !text-brick"
                  onClick={() => resolve.mutate({ id: r.id, code: null })}
                >
                  <XCircle className="h-4 w-4" /> {t('data.noMatch')}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function QualityReport() {
  const { t } = useApp()
  const q = useQuery({ queryKey: ['quality'], queryFn: () => api.get<Quality>('/quality') })
  if (!q.data?.ready) return null
  const years = Object.keys(q.data.completeness_by_year)
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_2fr]">
      <Card title={t('data.quality')} sub={t('data.qualitySub', { c: q.data.confidence })} info={t('data.qualityInfo')}>
        <table className="w-full text-[0.9rem] tabnum">
          <thead className="text-left text-[0.78rem] text-muted">
            <tr>
              <th className="py-1 font-medium" />
              {years.map((y) => (
                <th key={y} className="text-right font-medium">
                  {y}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {['assessment', 'attendance', 'teachers', 'udise'].map((k) => (
              <tr key={k} className="border-t border-line">
                <td className="py-2">{t(`src.${k}`)}</td>
                {years.map((y) => {
                  const v = q.data!.completeness_by_year[y][k]
                  return (
                    <td key={y} className={clsx('text-right', v < 0.8 && 'font-semibold text-brick')}>
                      {Math.round(v * 100)}%
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="eyebrow mt-4">{t('data.flags')}</div>
        <ul className="reasons mt-1">
          {q.data.comparability_flags.map((f, i) => (
            <li key={i}>
              <b>{f.unit}</b> · {t('w.comparability', { from: f.from_year, to: f.to_year })}
            </li>
          ))}
        </ul>
      </Card>
      <Card title={t('data.perFile')} pad={false}>
        <div className="max-h-96 overflow-y-auto px-5 pb-4">
          <table className="w-full text-[0.82rem] tabnum">
            <thead className="sticky top-0 bg-surface text-left text-[0.74rem] text-muted">
              <tr>
                {[
                  'data.th.file',
                  'data.th.kind',
                  'data.th.year',
                  'data.th.rows',
                  'data.th.dupes',
                  'data.th.name',
                  'data.th.review',
                  'data.th.map',
                ].map((k) => (
                  <th key={k} className="py-1.5 pr-2 font-medium">
                    {t(k)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {q.data.files.map((f) => (
                <tr key={f.file} className="border-t border-line align-top" title={f.transforms.join('\n')}>
                  <td className="py-2 pr-2">
                    <FileSpreadsheet className="mr-1 inline h-3.5 w-3.5 text-s1" />
                    {f.file}
                    <div className="text-[0.7rem] text-muted">{f.transforms.slice(0, 2).join(' · ')}</div>
                  </td>
                  <td>{t(`kind.${f.kind}`)}</td>
                  <td>{f.academic_year}</td>
                  <td>
                    {f.rows_in}→{f.rows_out}
                  </td>
                  <td>{f.exact_duplicates + f.key_duplicates}</td>
                  <td>{f.matched_by_name}</td>
                  <td>{f.review_rows}</td>
                  <td className="font-mono text-[0.7rem]">{f.mapping_version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

export default function DataStudio() {
  const qc = useQueryClient()
  const { user, meta, t } = useApp()
  const [adapter, setAdapter] = useState<'synthetic_files' | 'upload'>('synthetic_files')
  const [raw, setRaw] = useState<string | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [overrides, setOverrides] = useState<Record<string, Record<string, string | null>>>({})
  const [jobId, setJobId] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const src = useQuery({ queryKey: ['sources'], queryFn: () => api.get<Sources>('/ingest/sources') })
  const summary = useQuery({ queryKey: ['ingest-summary'], queryFn: () => api.get<Summary>('/ingest/summary') })
  const mPreview = useMutation({
    mutationFn: () => api.post<Preview>('/ingest/preview', { adapter, use_ai: true }),
    onSuccess: (p) => {
      setPreview(p)
      setOverrides({})
    },
  })
  const mRun = useMutation({
    mutationFn: () =>
      api.post<{ job_id: string }>('/ingest/run', {
        adapter,
        preview_id: preview?.preview_id,
        overrides,
        use_ai: true,
      }),
    onSuccess: (r) => {
      setJobId(r.job_id)
      setElapsed(0)
    },
  })
  const mUpload = useMutation({
    mutationFn: (files: FileList) => {
      const f = new FormData()
      Array.from(files).forEach((x) => f.append('files', x))
      return api.upload('/ingest/upload', f)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })
  const job = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.get<Job>(`/ingest/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 600 : false),
  })
  useEffect(() => {
    if (job.data?.status !== 'running') return
    const iv = setInterval(() => setElapsed((e) => e + 0.1), 100)
    return () => clearInterval(iv)
  }, [job.data?.status])
  useEffect(() => {
    if (job.data?.status === 'done') qc.invalidateQueries()
  }, [job.data?.status, qc])
  const canRun = user && ['district', 'state'].includes(user.role)
  const files = src.data?.files[adapter] ?? []
  const done = job.data?.status === 'done' ? job.data.result : null
  const nonDict = preview?.files.flatMap((f) => f.columns).filter((c) => c.method !== 'dictionary').length ?? 0
  const s = done ?? summary.data
  return (
    <div className="space-y-5">
      <PageHeader title={t('data.title')} sub={t('data.sub')} />
      <HelpStrip k="help.data" />
      {!meta?.ready && <div className="rounded-lg border-l-4 border-s2 bg-saffron-50 p-3">{t('data.empty')}</div>}
      <div className="grid gap-5 lg:grid-cols-[1fr_2fr]">
        <Card title={t('data.s1')} sub={t('data.s1sub')}>
          <div className="space-y-2">
            {src.data?.adapters.map((a) => (
              <label
                key={a.key}
                className={clsx(
                  'flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-[0.9rem]',
                  !a.available && 'cursor-not-allowed opacity-60',
                  adapter === a.key ? 'border-forest bg-forest-50' : 'border-line',
                )}
              >
                <input
                  type="radio"
                  disabled={!a.available}
                  checked={adapter === a.key}
                  onChange={() => {
                    setAdapter(a.key as 'upload')
                    setPreview(null)
                  }}
                  className="mt-1 accent-[#1e4d36]"
                />
                <div>
                  <div className="font-semibold">
                    {t(`src.${a.key}`)} {!a.available && <Lock className="ml-1 inline h-3.5 w-3.5" />}
                  </div>
                  {!a.available && (
                    <div className="mt-0.5 text-[0.78rem] text-muted">
                      {t('data.locked', { r: a.requirements.access })}
                    </div>
                  )}
                </div>
              </label>
            ))}
          </div>
          {adapter === 'upload' && (
            <label className="mt-3 flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 border-dashed border-line-2 p-5 text-center text-[0.9rem] text-ink-2 hover:bg-sunk">
              <Upload className="h-5 w-5" /> {t('data.drop')}
              <input
                type="file"
                multiple
                accept=".csv,.xlsx,.xls"
                className="hidden"
                onChange={(e) => e.target.files && mUpload.mutate(e.target.files)}
              />
            </label>
          )}
        </Card>
        <Card
          title={t('data.s2', { n: files.length })}
          sub={adapter === 'synthetic_files' ? t('data.s2sub') : ''}
          info={t('data.s2info')}
          right={
            <button
              className="btn btn-primary"
              disabled={!files.length || mPreview.isPending}
              onClick={() => mPreview.mutate()}
            >
              <ScanSearch className="h-4 w-4" /> {mPreview.isPending ? t('data.analysing') : t('data.analyse')}
            </button>
          }
        >
          <div className="grid gap-1.5 sm:grid-cols-2">
            {files.map((f) => (
              <button
                key={f.name}
                className="flex items-center justify-between rounded-md border border-line bg-sunk px-3 py-2 text-left text-[0.86rem] hover:border-forest"
                onClick={() => setRaw(f.name)}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4 shrink-0 text-s1" />
                  <span className="truncate">{f.name}</span>
                </span>
                <span className="flex shrink-0 items-center gap-1 text-[0.74rem] text-muted">
                  {f.size_kb} KB <Eye className="h-3.5 w-3.5" />
                </span>
              </button>
            ))}
          </div>
          {mPreview.isError && (
            <div className="mt-2">
              <ErrorBox error={mPreview.error} />
            </div>
          )}
        </Card>
      </div>

      {preview && (
        <Card
          title={t('data.s3')}
          sub={t('data.s3sub', { files: preview.files.length, n: nonDict })}
          info={t('data.s3info')}
          right={
            <button
              className="btn btn-accent"
              disabled={!canRun || mRun.isPending || job.data?.status === 'running'}
              onClick={() => mRun.mutate()}
            >
              <Play className="h-4 w-4" /> {t('data.build')}
            </button>
          }
        >
          {!canRun && <div className="mb-2 text-[0.86rem] text-mustard">{t('data.onlyOfficers')}</div>}
          <div className="grid gap-3 xl:grid-cols-2">
            {[...preview.files]
              .sort(
                (a, b) =>
                  Number(b.columns.some((c) => c.method !== 'dictionary') || b.wide_month_columns.length > 0) -
                  Number(a.columns.some((c) => c.method !== 'dictionary') || a.wide_month_columns.length > 0),
              )
              .map((f) => (
                <div key={f.file} className="min-w-0 overflow-hidden rounded-lg border border-line p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <FileSpreadsheet className="h-4 w-4 text-s1" />
                    <b className="text-[0.92rem]">{f.file}</b>
                    <span className="tag">{t(`kind.${f.kind}`)}</span>
                    <span className="tag">{f.year_hint ?? '—'}</span>
                    {f.wide_month_columns.length > 0 && (
                      <span className="tag !bg-good-50 !text-good">
                        {t('data.monthCols', { n: f.wide_month_columns.length })}
                      </span>
                    )}
                    {f.required_missing.length > 0 && (
                      <span className="tag !text-brick">{t('data.missing', { f: f.required_missing.join(', ') })}</span>
                    )}
                  </div>
                  {f.ai_note && <div className="mt-1 text-[0.76rem] text-mustard">{f.ai_note}</div>}
                  <table className="mt-2 w-full text-[0.82rem]">
                    <tbody>
                      {f.columns.map((c) => {
                        const ov = overrides[f.file]?.[c.source]
                        const method = ov !== undefined ? 'manual' : c.method
                        return (
                          <tr key={c.source} className="border-t border-line">
                            <td className="py-1.5 pr-2 font-mono text-[0.78rem]">{c.source}</td>
                            <td className="pr-2">
                              <select
                                className="rounded border border-line-2 bg-surface px-1 py-0.5 text-[0.8rem]"
                                value={ov ?? c.target ?? ''}
                                onChange={(e) =>
                                  setOverrides({
                                    ...overrides,
                                    [f.file]: { ...(overrides[f.file] ?? {}), [c.source]: e.target.value || null },
                                  })
                                }
                              >
                                <option value="">{t('data.ignore')}</option>
                                {TARGETS[f.kind].map((x) => (
                                  <option key={x} value={x}>
                                    {x}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td>
                              <span
                                className={clsx('rounded px-1.5 py-0.5 text-[0.7rem] font-semibold', METHOD[method])}
                              >
                                {method} {Math.round(c.confidence * 100)}%
                              </span>
                            </td>
                            <td
                              className="max-w-[150px] truncate pl-2 text-[0.74rem] text-muted"
                              title={c.reason || c.sample.join(', ')}
                            >
                              {c.reason || c.sample.slice(0, 2).join(', ')}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ))}
          </div>
        </Card>
      )}

      {job.data && (
        <Card
          title={t('data.s4')}
          right={
            <span className="flex items-center gap-1 text-[1.2rem] font-bold tabnum">
              <Clock className="h-4 w-4" />
              {(job.data.result?.seconds ?? elapsed).toFixed(1)}s
            </span>
          }
        >
          <div className="h-2.5 w-full rounded-full bg-sunk">
            <div
              className="h-2.5 rounded-full bg-forest transition-all"
              style={{ width: `${job.data.progress * 100}%` }}
            />
          </div>
          <ol className="mt-3 max-h-40 space-y-0.5 overflow-y-auto text-[0.82rem] text-ink-2">
            {job.data.steps.map((st, i) => (
              <li key={i}>
                <span className="text-muted tabnum">{st.t.toFixed(1)}s</span> · {st.detail}
              </li>
            ))}
          </ol>
          {job.data.error && <ErrorBox error={job.data.error} />}
        </Card>
      )}

      {s?.files ? (
        <div className="panel grid gap-5 border-l-4 !border-l-s1 p-5 md:grid-cols-4">
          <div className="md:row-span-2">
            <div className="eyebrow">{t('data.manual')}</div>
            <div className="text-[1.2rem] font-semibold text-brick line-through decoration-2">
              {t('data.manualVal')}
            </div>
            <div className="eyebrow mt-3">{t('data.us')}</div>
            <div className="text-[2.4rem] font-bold leading-none text-good">
              {s.seconds ? `${s.seconds}s` : t('data.ready')}
            </div>
          </div>
          {(
            [
              ['data.filesJoined', s.files],
              ['data.rows', `${s.rows_in.toLocaleString()} → ${s.rows_out.toLocaleString()}`],
              ['data.schoolsYears', `${s.schools} · ${s.years.length}`],
              ['data.dupes', s.duplicates_removed],
              ['data.matched', s.matched_by_name],
              ['data.needReview', `${s.review_groups} (${s.review_rows})`],
            ] as [string, string | number][]
          ).map(([k, v]) => (
            <div key={k}>
              <div className="eyebrow flex items-center gap-1">
                {t(k)}
                {k === 'data.needReview' && <InfoTip text={t('data.reviewInfo')} />}
              </div>
              <div className="mt-0.5 text-[1.2rem] font-semibold">{v}</div>
            </div>
          ))}
        </div>
      ) : null}

      <ReviewQueue />
      <QualityReport />
      <RawPreview adapter={adapter} file={raw} onClose={() => setRaw(null)} />
    </div>
  )
}
