import { useQuery } from '@tanstack/react-query'
import { Background, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { AlertTriangle, FileSpreadsheet, HelpCircle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { PageHeader, UnitPicker } from '../components/Layout'
import {
  C, Card, ClassBadge, Delta, Drawer, ErrorBox, HelpStrip, InfoTip, Speak, Spinner, VerdictBanner, pct, signed,
  useOpenQuestionText, useWarningText,
} from '../components/ui'
import { unitQs, useApp } from '../state'
import type { Diagnosis, Signal } from '../types'

type NodeData = { title: string; sub: string; kind: 'outcome' | 'signal' | 'context' | 'question' | 'gap'; cls?: string; clsLabel?: string; onClick?: () => void }
const EDGE: Record<string, string> = { HIGH: '#b4432a', MEDIUM: '#dd8f22', CONFLICTING: '#57524b', INSUFFICIENT_EVIDENCE: '#8a847b', NONE: '#cfc6b5' }

function EvNode({ data }: NodeProps<Node<NodeData>>) {
  const border = data.kind === 'outcome' ? '#1e4d36' : data.kind === 'context' ? '#1f7a4a' : data.kind === 'signal' ? EDGE[data.cls ?? 'NONE'] : '#b5ab98'
  return (
    <button onClick={data.onClick} className="w-56 rounded-lg border-2 bg-surface px-3 py-2.5 text-left hover:shadow-md"
      style={{ borderColor: border, borderStyle: data.kind === 'question' || data.kind === 'gap' ? 'dashed' : 'solid', background: data.kind === 'outcome' ? '#1e4d36' : undefined, color: data.kind === 'outcome' ? '#fffdf8' : undefined }}>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="text-[13px] font-semibold leading-tight">{data.title}</div>
      <div className="mt-0.5 text-[11.5px] leading-snug opacity-80">{data.sub}</div>
      {data.clsLabel && <div className="mt-1.5 inline-block rounded px-1.5 py-0.5 text-[10.5px] font-semibold" style={{ background: `${border}1f`, color: border }}>{data.clsLabel}</div>}
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </button>
  )
}
const nodeTypes = { ev: EvNode }

function EvidenceGraph({ d, onSignal }: { d: Diagnosis; onSignal: (s: Signal) => void }) {
  const { t } = useApp()
  const qText = useOpenQuestionText()
  const { nodes, edges } = useMemo(() => {
    const sig = d.signals.filter((s) => s.classification !== 'NONE' && s.classification !== 'INSUFFICIENT_EVIDENCE')
    const ctx = d.context.filter((c) => c.classification === 'CONTEXT')
    const qs = d.unresolved.slice(0, 3)
    const row1 = [...sig.map((s) => ({ k: 's' as const, s })), ...ctx.map((c) => ({ k: 'c' as const, c }))]
    const w = 246
    const n: Node<NodeData>[] = [{ id: 'o', type: 'ev', position: { x: Math.max(0, ((Math.max(row1.length, qs.length + 1) - 1) * w) / 2), y: 0 },
      data: { kind: 'outcome', title: t('why.outcomeBox', { metric: t('m.numeracy'), change: signed(d.outcome.change_pp) }), sub: `${pct(d.outcome.baseline)} → ${pct(d.outcome.latest)} · ${d.period}` } }]
    const e: Edge[] = []
    row1.forEach((r, i) => {
      if (r.k === 's') {
        const s = r.s
        n.push({ id: s.id, type: 'ev', position: { x: i * w, y: 160 }, data: { kind: 'signal', cls: s.classification, clsLabel: t(`cls.${s.classification}`),
          title: t(`fk.${s.factor}`), onClick: () => onSignal(s), sub: `${s.baseline} → ${s.latest} (${signed(s.change)}) · ${t('why.ofChange', { v: s.contribution_pp })}` } })
        e.push({ id: `e${s.id}`, source: 'o', target: s.id, animated: s.classification === 'HIGH', style: { stroke: EDGE[s.classification], strokeWidth: s.classification === 'HIGH' ? 3 : 2 } })
      } else {
        const c = r.c
        n.push({ id: c.id, type: 'ev', position: { x: i * w, y: 160 }, data: { kind: 'context', clsLabel: t('cls.CONTEXT'), title: t('why.context', { event: t(`ev.${c.event}`) }), sub: t('why.contextSub', { tdl: c.avg_teacher_days_lost }) } })
        e.push({ id: `e${c.id}`, source: 'o', target: c.id, style: { stroke: C.s1, strokeDasharray: '2 5', strokeWidth: 2 } })
      }
    })
    qs.forEach((q, i) => {
      n.push({ id: q.id, type: 'ev', position: { x: i * w, y: 330 }, data: { kind: 'question', title: t('why.openQ'), sub: qText(q) } })
      e.push({ id: `e${q.id}`, source: 'o', target: q.id, style: { stroke: '#b5ab98', strokeDasharray: '5 4' } })
    })
    const fo = d.field_observations
    if (fo) {
      n.push({ id: 'field', type: 'ev', position: { x: qs.length * w, y: 330 }, data: { kind: 'context', clsLabel: t('why.field'), title: t('why.fieldBox', { s: fo.avg_score }), sub: fo.items.slice(0, 2).map((i) => `${t(`i.${i.item}`)} ${i.pct_yes}%`).join(' · ') } })
      e.push({ id: 'efield', source: 'o', target: 'field', style: { stroke: C.s1, strokeWidth: 2 } })
    } else {
      n.push({ id: 'gap', type: 'ev', position: { x: qs.length * w, y: 330 }, data: { kind: 'gap', title: t('why.dataGaps'), sub: t(`gap.${d.data_gap_keys?.[0] ?? 'gap_observation'}`) } })
    }
    return { nodes: n, edges: e }
  }, [d, onSignal, t, qText])
  return (
    <div className="h-[440px] rounded-lg border border-line bg-sunk">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.06, maxZoom: 1.15 }} minZoom={0.25} proOptions={{ hideAttribution: true }} nodesDraggable={false} nodesConnectable={false} panOnScroll>
        <Background color="#e2dacb" gap={22} />
      </ReactFlow>
    </div>
  )
}

function SignalDrawer({ s, onClose }: { s: Signal | null; onClose: () => void }) {
  const { t } = useApp()
  if (!s) return null
  const stat = (k: string, v: string | number | undefined | null, info?: string) => (
    <div className="panel-sunk p-3"><div className="eyebrow flex items-center gap-1">{k}{info && <InfoTip text={info} />}</div><div className="mt-1 text-[1.15rem] font-semibold tabnum">{v ?? '—'}</div></div>
  )
  return (
    <Drawer open={!!s} onClose={onClose} title={<span className="flex items-center gap-2">{t(`fk.${s.factor}`)} <ClassBadge c={s.classification} withInfo /></span>}>
      <div className="space-y-5 text-[0.92rem]">
        <div className="grid grid-cols-3 gap-2">
          {stat(t('c.before'), s.baseline)}{stat(t('c.after'), s.latest)}{stat(t('c.change'), `${signed(s.change)} ${t('c.pts')}`)}
          {stat(t('why.assoc'), s.contribution_pp != null ? `≈ ${s.contribution_pp}` : null, t('why.assocNote'))}{stat(t('why.r'), s.assoc_r)}{stat(t('why.coverage'), `${Math.round(s.coverage * 100)}%`)}
        </div>
        <div className="rounded-lg border-l-4 border-s2 bg-saffron-50 p-3 text-[0.86rem] text-ink-2">{t('why.assocNote')}</div>
        <div>
          <div className="eyebrow mb-1">{t('why.sources')} · {s.period}</div>
          <ul className="space-y-0.5 text-[0.86rem]">{s.sources.map((f) => <li key={f} className="flex items-center gap-1.5"><FileSpreadsheet className="h-4 w-4 text-s1" />{f}</li>)}</ul>
        </div>
        {s.affected_units && s.affected_units.length > 0 && (
          <div>
            <div className="eyebrow mb-1">{t('why.where')}</div>
            <div className="h-44">
              <ResponsiveContainer>
                <BarChart data={s.affected_units} layout="vertical" margin={{ left: 10, right: 24 }}>
                  <CartesianGrid stroke={C.grid} horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 12, fill: C.muted }} domain={[(m: number) => Math.min(0, Math.floor(m)), (m: number) => Math.max(0, Math.ceil(m))]} />
                  <YAxis type="category" dataKey="unit" tick={{ fontSize: 12 }} width={84} />
                  <Tooltip formatter={(v) => `${v} ${t('c.pts')}`} />
                  <Bar dataKey="change" name={t('c.change')} fill={C.s1} radius={4} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
        {s.affected_schools && s.affected_schools.length > 0 && (
          <div>
            <div className="eyebrow mb-1">{t('why.affected')}</div>
            <table className="w-full text-[0.86rem]">
              <thead className="text-left text-muted"><tr><th className="py-1 font-medium">{t('c.schools')}</th><th className="font-medium">{t('c.block')}</th><th className="text-right font-medium">{t('c.before')}</th><th className="text-right font-medium">{t('c.after')}</th></tr></thead>
              <tbody className="tabnum">{s.affected_schools.map((x) => (
                <tr key={x.udise_code} className="border-t border-line"><td className="py-1.5">{x.school_name}<div className="text-[0.72rem] text-muted">{x.udise_code}</div></td><td>{x.block}</td><td className="text-right">{x.baseline}</td><td className="text-right">{x.latest}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>
    </Drawer>
  )
}

type Timeline = { series: { period: string; student: number; teacher: number }[]; events: { event: string; academic_year: string; start: string; end: string; avg_teacher_days_lost: number }[] }

function ContextTimeline({ q }: { q: string }) {
  const { t } = useApp()
  const tl = useQuery({ queryKey: ['context', q], queryFn: () => api.get<Timeline>(`/context?${q}`) })
  if (!tl.data) return <Spinner />
  const ev = tl.data.events.filter((e) => e.avg_teacher_days_lost > 0)
  return (
    <Card title={t('why.timeline')} sub={t('why.timelineSub')} info={t('why.timelineInfo')}>
      <div className="h-64">
        <ResponsiveContainer>
          <LineChart data={tl.data.series} margin={{ top: 12, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="period" tick={{ fontSize: 11, fill: C.muted }} interval={2} />
            <YAxis domain={['dataMin - 3', 100]} tick={{ fontSize: 12, fill: C.muted }} width={38} tickFormatter={(v) => `${Math.round(v)}%`} />
            <Tooltip formatter={(v) => `${v}%`} contentStyle={{ borderRadius: 8, borderColor: '#d6cdbd' }} />
            <Legend wrapperStyle={{ fontSize: 13 }} />
            {ev.map((e) => <ReferenceArea key={e.event + e.academic_year} x1={e.start.slice(0, 7)} x2={e.end.slice(0, 7)} fill="#dd8f22" fillOpacity={0.14} label={{ value: t(`ev.${e.event}`), position: 'insideTop', fontSize: 11, fill: '#8a5a0b' }} />)}
            <Line dataKey="student" name={t('m.student_att')} stroke={C.s1} strokeWidth={2.5} dot={false} isAnimationActive={false} />
            <Line dataKey="teacher" name={t('m.teacher_att')} stroke={C.s2} strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

export default function Why() {
  const { unit, ask, t } = useApp()
  const qText = useOpenQuestionText()
  const wText = useWarningText()
  const q = unitQs(unit)
  const [sig, setSig] = useState<Signal | null>(null)
  const d = useQuery({ queryKey: ['diagnose', q], queryFn: () => api.get<Diagnosis>(`/diagnose?${q}`) })
  if (d.isError) return <ErrorBox error={d.error} />
  if (!d.data) return <Spinner />
  const x = d.data
  const shown = x.signals.filter((s) => s.classification !== 'NONE')
  const name = x.unit_type === 'state' ? t('c.wholeState') : x.unit_type === 'district' ? t('c.districtLabel', { d: x.unit }) : t('c.blockLabel', { b: x.unit })
  const speech = [t(`v.${x.verdict}`), t(`vr.${x.verdict}`), ...shown.map((s) => `${t(`fk.${s.factor}`)}: ${t(`cls.${s.classification}`)}`), ...x.unresolved.map(qText)].join('. ')
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t('why.sub', { metric: t('m.numeracy'), period: x.period })} title={t('why.title', { unit: name })}
        right={<><UnitPicker /><Speak text={speech} /><button className="btn btn-primary" onClick={() => ask(t('ask.s1'))}>{t('c.askAI')}</button></>} />
      <HelpStrip k="help.why" />
      <VerdictBanner verdict={x.verdict} />
      <Card title={t('why.graph')} sub={t('why.graphSub')} info={t('why.graphInfo')}><EvidenceGraph d={x} onSignal={setSig} /></Card>
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="contents">
          <Card title={t('why.outcome')} info={t('mi.numeracy')}>
            <div className="flex items-end gap-3"><div className="num-xl">{pct(x.outcome.latest)}</div><Delta v={x.outcome.change_pp} className="mb-0.5" /></div>
            <div className="mt-1 text-[0.85rem] text-ink-2">{t('why.from', { v: pct(x.outcome.baseline) })} · {t('why.compared', { n: x.outcome.n_schools_compared })}</div>
          </Card>
          {x.field_observations && (
            <Card title={t('why.field')} sub={t('why.fieldSub', { n: x.field_observations.n_visits, d1: x.field_observations.first, d2: x.field_observations.last })} info={t('vis.scoreInfo')}>
              <div className="flex items-end gap-2"><div className="num-xl">{x.field_observations.avg_score}</div><div className="pb-1 text-muted">/100 · {t('vis.score')}</div></div>
              <ul className="mt-3 space-y-1.5">{x.field_observations.items.slice(0, 3).map((i) => (
                <li key={i.item} className="flex justify-between text-[0.86rem]"><span>{t(`i.${i.item}`)}</span><span className="tabnum font-semibold" style={{ color: i.pct_yes < 34 ? C.brick : C.ink }}>{i.pct_yes}%</span></li>
              ))}</ul>
              <p className="mt-2 text-[0.76rem] text-muted">{t('why.fieldNote')}{x.field_observations.simulated ? ` (${t('c.simulated')})` : ''}</p>
            </Card>
          )}
          <Card title={t('why.signals')}>
            <ul className="space-y-2">
              {shown.length === 0 && <li className="text-[0.9rem] text-muted">{t('why.noSignals')}</li>}
              {shown.map((s) => (
                <li key={s.id}>
                  <button className="panel-sunk w-full p-3 text-left hover:border-forest" onClick={() => setSig(s)}>
                    <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">{t(`fk.${s.factor}`)}</span><ClassBadge c={s.classification} /></div>
                    {s.change !== undefined && <div className="mt-0.5 text-[0.84rem] text-ink-2 tabnum">{s.baseline} → {s.latest} ({signed(s.change)} {t('c.pts')}) · {t('why.ofChange', { v: s.contribution_pp })}</div>}
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          <Card title={<span className="flex items-center gap-1.5"><HelpCircle className="h-4 w-4 text-ink-2" />{t('why.open')}</span>}>
            <ul className="space-y-2 text-[0.88rem]">
              {x.unresolved.map((u) => <li key={u.id} className="rounded-md border border-dashed border-line-2 bg-sunk p-2.5">{qText(u)}</li>)}
              {x.quality_warning_items?.map((w, i) => <li key={i} className="flex gap-1.5 text-mustard"><AlertTriangle className="h-4 w-4 shrink-0" />{wText(w)}</li>)}
            </ul>
            <ul className="reasons mt-3">{(x.data_gap_keys ?? []).map((g) => <li key={g}>{t(`gap.${g}`)}</li>)}</ul>
            <div className="mt-3 text-[0.76rem] text-muted">{t('why.model', { c: x.data_confidence, n: x.model.n })}</div>
          </Card>
        </div>
      </div>
      <ContextTimeline q={q} />
      <SignalDrawer s={sig} onClose={() => setSig(null)} />
    </div>
  )
}
