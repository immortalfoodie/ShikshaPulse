// Ask ShikshaPulse — multilingual Q&A with voice input, read-aloud, evidence and the checker badge.
import { useMutation } from '@tanstack/react-query'
import clsx from 'clsx'
import { ChevronDown, Mic, MicOff, Send, ShieldAlert, ShieldCheck, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useListener } from '../speech'
import { useApp } from '../state'
import type { AskResult, Evidence } from '../types'
import { FindingLabel, Speak } from './ui'

type Guard = AskResult['guard'] & { unresolved_added?: number; causal_softened?: number; relabelled?: number }

function EvidenceChip({ ev }: { ev: Evidence | undefined }) {
  const [open, setOpen] = useState(false)
  const { t } = useApp()
  if (!ev) return null
  return (
    <span className="relative">
      <button className="tag !text-[0.7rem] hover:border-forest" onClick={() => setOpen(!open)} aria-expanded={open}>{ev.id}</button>
      {open && (
        <div className="absolute left-0 top-6 z-10 w-72 rounded-lg border border-line-2 bg-surface p-3 text-[0.78rem] shadow-lg">
          <div className="font-semibold">{ev.title}</div>
          {ev.period && <div className="text-muted">{t('c.period')}: {ev.period}</div>}
          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-sunk p-1.5 text-[0.72rem]">{JSON.stringify(ev.data, null, 1)}</pre>
          {ev.source && <div className="mt-1 text-muted">{t('c.source')}: {Array.isArray(ev.source) ? ev.source.join(', ') : ev.source}</div>}
        </div>
      )}
    </span>
  )
}

function Answer({ r }: { r: AskResult }) {
  const { t } = useApp()
  const [showTools, setShowTools] = useState(false)
  const g = r.guard as Guard
  const evById = Object.fromEntries(r.evidence.map((e) => [e.id, e]))
  const spoken = [r.answer.summary, ...r.answer.findings.map((f) => f.text), ...r.answer.next_steps].join(' ')
  const notes = [
    g.unresolved_added ? t('ask.note.guard', { n: g.unresolved_added }) : null,
    g.causal_softened ? t('ask.note.causal', { n: g.causal_softened }) : null,
    g.relabelled ? t('ask.note.label', { n: g.relabelled }) : null,
  ].filter(Boolean)
  return (
    <div className="panel p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className={clsx('tag', g.passed ? '!border-forest/25 !bg-forest-50 !text-forest' : '!border-brick/30 !bg-brick-50 !text-brick')}>
          {g.passed ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldAlert className="h-3.5 w-3.5" />}
          {g.passed ? t('ask.verified', { a: g.numbers_verified, b: g.numbers_checked }) : t('ask.failed')}
        </span>
        <span className="text-[0.74rem] text-muted">{r.engine === 'llm' ? t('ask.engineLLM', { m: r.llm.model }) : t('ask.engineDet')} · {(r.latency_ms / 1000).toFixed(1)}s</span>
        <Speak text={spoken} className="!ml-auto !min-h-8 !px-2.5 !py-1 !text-[0.8rem]" />
      </div>
      <p className="text-[0.98rem] leading-relaxed">{r.answer.summary}</p>
      <ul className="mt-3 space-y-2">
        {r.answer.findings.map((f, i) => (
          <li key={i} className="panel-sunk p-2.5 text-[0.9rem] leading-snug">
            <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
              <FindingLabel label={f.label} />
              {f.period && <span className="text-[0.72rem] text-muted">{f.period}</span>}
              {f.evidence.map((e) => <EvidenceChip key={e} ev={evById[e]} />)}
              {f.added_by_guard && <span className="tag">{t('ask.byGuard')}</span>}
            </div>
            {f.text}
          </li>
        ))}
      </ul>
      {r.answer.next_steps.length > 0 && (
        <div className="mt-3">
          <div className="eyebrow mb-1">{t('ask.next')}</div>
          <ul className="reasons">{r.answer.next_steps.map((s, i) => <li key={i} className="!text-[0.9rem] !text-ink">{s}</li>)}</ul>
        </div>
      )}
      {notes.length > 0 && <div className="mt-2 text-[0.78rem] text-ink-2">{notes.join(' ')}</div>}
      <button className="mt-2 inline-flex items-center gap-1 text-[0.76rem] text-muted hover:text-ink" onClick={() => setShowTools(!showTools)}>
        <ChevronDown className={clsx('h-3 w-3 transition', showTools && 'rotate-180')} /> {t('ask.tools', { n: r.tool_calls.length })}
      </button>
      {showTools && <ul className="mt-1 space-y-0.5 text-[0.74rem] text-ink-2">{r.tool_calls.map((x, i) => <li key={i}><code>{x.tool}</code>({JSON.stringify(x.args)})</li>)}</ul>}
    </div>
  )
}

export function AskPanel() {
  const { askOpen, setAskOpen, askSeed, lang, meta, user, t } = useApp()
  const [q, setQ] = useState('')
  const [history, setHistory] = useState<{ id: number; q: string; r?: AskResult; err?: string }[]>([])
  const endRef = useRef<HTMLDivElement>(null)
  const idRef = useRef(0)
  const m = useMutation({
    mutationFn: ({ question }: { id: number; question: string }) => api.post<AskResult>('/ask', { question, lang }),
    onSuccess: (r, v) => setHistory((h) => h.map((x) => (x.id === v.id ? { ...x, r } : x))),
    onError: (e, v) => setHistory((h) => h.map((x) => (x.id === v.id ? { ...x, err: String(e) } : x))),
  })
  const send = useCallback((question: string) => {
    if (!question.trim()) return
    const id = ++idRef.current
    setHistory((h) => [...h, { id, q: question }])
    setQ('')
    m.mutate({ id, question })
  }, [m])
  const mic = useListener(lang, (text) => setQ(text))
  useEffect(() => {
    if (askOpen && askSeed) send(askSeed)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [askOpen, askSeed])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [history])
  if (!askOpen) return null
  // Questions that fit the person: a school, one block, a district, or the whole state.
  const myBlock = user?.block ?? user?.scope ?? ''
  const suggestions: [string, Record<string, string>?][] = user?.role === 'headmaster' ? [['ask.s7'], ['ask.s6']]
    : user?.role === 'block' ? [['ask.s1b'], ['ask.s3b', { b: myBlock }], ['ask.s4'], ['ask.s5'], ['ask.s6']]
    : user?.role === 'state' ? [['ask.s1st'], ['ask.s2'], ['ask.s3'], ['ask.s4'], ['ask.s5'], ['ask.s6']]
    : [['ask.s1'], ['ask.s2'], ['ask.s3'], ['ask.s4'], ['ask.s5'], ['ask.s6']]
  return (
    <aside className="no-print fixed right-0 top-0 z-40 flex h-full w-[480px] max-w-full flex-col border-l border-line bg-paper shadow-2xl">
      <div className="flex items-center justify-between border-b border-line bg-surface px-5 py-3">
        <div>
          <div className="text-[1.02rem] font-semibold">{t('ask.title')}</div>
          <div className="text-[0.74rem] text-muted">{meta?.llm.available ? t('ask.engineLLM', { m: meta.llm.model }) : t('ask.engineDet')} · {t('ask.checked')}</div>
        </div>
        <button className="btn btn-quiet !min-h-0 !p-1.5" onClick={() => setAskOpen(false)} aria-label={t('c.close')}><X className="h-4 w-4" /></button>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {history.length === 0 && (
          <div className="space-y-2">
            <p className="text-[0.88rem] text-ink-2">{t('ask.intro')}</p>
            {suggestions.map(([s, v]) => (
              <button key={s} className="block w-full rounded-lg border border-line bg-surface p-3 text-left text-[0.9rem] hover:border-forest" onClick={() => send(t(s, v))}>{t(s, v)}</button>
            ))}
          </div>
        )}
        {history.map((h) => (
          <div key={h.id} className="space-y-2">
            <div className="ml-12 rounded-lg bg-forest p-3 text-[0.92rem] text-surface">{h.q}</div>
            {h.r ? <Answer r={h.r} /> : h.err ? <div className="text-[0.85rem] text-brick">{h.err}</div> : (
              <div className="flex items-center gap-2 text-[0.85rem] text-ink-2"><span className="h-2 w-2 animate-pulse rounded-full bg-s2" /> {t('ask.running')}</div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form className="flex gap-2 border-t border-line bg-surface p-3" onSubmit={(e) => { e.preventDefault(); send(q) }}>
        <button type="button" className={clsx('btn', mic.listening ? 'btn-accent' : 'btn-quiet')} disabled={!mic.supported}
          onClick={() => (mic.listening ? mic.stop() : mic.start())} aria-label={mic.supported ? t('ask.mic') : t('ask.noMic')} title={mic.supported ? t('ask.mic') : t('ask.noMic')}>
          {mic.supported ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
        </button>
        <input className="field flex-1" value={q} onChange={(e) => setQ(e.target.value)} placeholder={mic.listening ? t('ask.listening') : t('ask.placeholder')} aria-label={t('ask.placeholder')} />
        <button className="btn btn-primary" disabled={m.isPending} aria-label={t('c.ask')}><Send className="h-4 w-4" /></button>
      </form>
    </aside>
  )
}
