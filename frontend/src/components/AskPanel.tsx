// Ask ShikshaPulse — multilingual Q&A with voice input, read-aloud, evidence and the checker badge.
import { useMutation } from '@tanstack/react-query'
import clsx from 'clsx'
import { ChevronDown, Mic, MicOff, Send, ShieldAlert, ShieldCheck, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useListener } from '../speech'
import { useApp } from '../state'
import type { AskResult, Evidence, User } from '../types'
import { FindingLabel, Speak } from './ui'

type GuardReport = AskResult['guard'] & {
  unresolved_added?: number
  causal_softened?: number
  relabelled?: number
}

type HistoryEntry = {
  id: number
  question: string
  result?: AskResult
  error?: string
}

type SuggestionPrompt = [key: string, vars?: Record<string, string>]

/** Suggested starter questions tailored to the signed-in officer's scope. */
function suggestionsForUser(user: User | null): SuggestionPrompt[] {
  const myBlock = user?.block ?? user?.scope ?? ''
  switch (user?.role) {
    case 'headmaster':
      return [['ask.s7'], ['ask.s6']]
    case 'block':
      return [['ask.s1b'], ['ask.s3b', { b: myBlock }], ['ask.s4'], ['ask.s5'], ['ask.s6']]
    case 'state':
      return [['ask.s1st'], ['ask.s2'], ['ask.s3'], ['ask.s4'], ['ask.s5'], ['ask.s6']]
    default:
      return [['ask.s1'], ['ask.s2'], ['ask.s3'], ['ask.s4'], ['ask.s5'], ['ask.s6']]
  }
}

function EvidenceChip({ evidence }: { evidence: Evidence | undefined }) {
  const [open, setOpen] = useState(false)
  const { t } = useApp()
  if (!evidence) return null
  return (
    <span className="relative">
      <button className="tag !text-[0.7rem] hover:border-forest" onClick={() => setOpen(!open)} aria-expanded={open}>
        {evidence.id}
      </button>
      {open && (
        <div className="absolute left-0 top-6 z-10 w-72 rounded-lg border border-line-2 bg-surface p-3 text-[0.78rem] shadow-lg">
          <div className="font-semibold">{evidence.title}</div>
          {evidence.period && (
            <div className="text-muted">
              {t('c.period')}: {evidence.period}
            </div>
          )}
          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-sunk p-1.5 text-[0.72rem]">
            {JSON.stringify(evidence.data, null, 1)}
          </pre>
          {evidence.source && (
            <div className="mt-1 text-muted">
              {t('c.source')}: {Array.isArray(evidence.source) ? evidence.source.join(', ') : evidence.source}
            </div>
          )}
        </div>
      )}
    </span>
  )
}

function Answer({ result }: { result: AskResult }) {
  const { t } = useApp()
  const [showTools, setShowTools] = useState(false)
  const guard = result.guard as GuardReport
  const evidenceById = Object.fromEntries(result.evidence.map((item) => [item.id, item]))
  const spokenText = [
    result.answer.summary,
    ...result.answer.findings.map((finding) => finding.text),
    ...result.answer.next_steps,
  ].join(' ')
  const guardNotes = [
    guard.unresolved_added ? t('ask.note.guard', { n: guard.unresolved_added }) : null,
    guard.causal_softened ? t('ask.note.causal', { n: guard.causal_softened }) : null,
    guard.relabelled ? t('ask.note.label', { n: guard.relabelled }) : null,
  ].filter(Boolean)

  return (
    <div className="panel p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span
          className={clsx(
            'tag',
            guard.passed ? '!border-forest/25 !bg-forest-50 !text-forest' : '!border-brick/30 !bg-brick-50 !text-brick',
          )}
        >
          {guard.passed ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldAlert className="h-3.5 w-3.5" />}
          {guard.passed ? t('ask.verified', { a: guard.numbers_verified, b: guard.numbers_checked }) : t('ask.failed')}
        </span>
        <span className="text-[0.74rem] text-muted">
          {result.engine === 'llm' ? t('ask.engineLLM', { m: result.llm.model }) : t('ask.engineDet')} ·{' '}
          {(result.latency_ms / 1000).toFixed(1)}s
        </span>
        <Speak text={spokenText} className="!ml-auto !min-h-8 !px-2.5 !py-1 !text-[0.8rem]" />
      </div>
      <p className="text-[0.98rem] leading-relaxed">{result.answer.summary}</p>
      <ul className="mt-3 space-y-2">
        {result.answer.findings.map((finding, index) => (
          <li key={index} className="panel-sunk p-2.5 text-[0.9rem] leading-snug">
            <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
              <FindingLabel label={finding.label} />
              {finding.period && <span className="text-[0.72rem] text-muted">{finding.period}</span>}
              {finding.evidence.map((evidenceId) => (
                <EvidenceChip key={evidenceId} evidence={evidenceById[evidenceId]} />
              ))}
              {finding.added_by_guard && <span className="tag">{t('ask.byGuard')}</span>}
            </div>
            {finding.text}
          </li>
        ))}
      </ul>
      {result.answer.next_steps.length > 0 && (
        <div className="mt-3">
          <div className="eyebrow mb-1">{t('ask.next')}</div>
          <ul className="reasons">
            {result.answer.next_steps.map((step, index) => (
              <li key={index} className="!text-[0.9rem] !text-ink">
                {step}
              </li>
            ))}
          </ul>
        </div>
      )}
      {guardNotes.length > 0 && <div className="mt-2 text-[0.78rem] text-ink-2">{guardNotes.join(' ')}</div>}
      <button
        className="mt-2 inline-flex items-center gap-1 text-[0.76rem] text-muted hover:text-ink"
        onClick={() => setShowTools(!showTools)}
      >
        <ChevronDown className={clsx('h-3 w-3 transition', showTools && 'rotate-180')} />{' '}
        {t('ask.tools', { n: result.tool_calls.length })}
      </button>
      {showTools && (
        <ul className="mt-1 space-y-0.5 text-[0.74rem] text-ink-2">
          {result.tool_calls.map((call, index) => (
            <li key={index}>
              <code>{call.tool}</code>({JSON.stringify(call.args)})
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Slide-over assistant panel with evidence citations and numeric verification badge. */
export function AskPanel() {
  const { askOpen, setAskOpen, askSeed, lang, meta, user, t } = useApp()
  const [questionInput, setQuestionInput] = useState('')
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const endRef = useRef<HTMLDivElement>(null)
  const idRef = useRef(0)
  const lastSeedSentRef = useRef<string | null>(null)

  const askMutation = useMutation({
    mutationFn: ({ question }: { id: number; question: string }) => api.post<AskResult>('/ask', { question, lang }),
    onSuccess: (result, variables) =>
      setHistory((prev) => prev.map((entry) => (entry.id === variables.id ? { ...entry, result } : entry))),
    onError: (err, variables) =>
      setHistory((prev) => prev.map((entry) => (entry.id === variables.id ? { ...entry, error: String(err) } : entry))),
  })
  const { mutate: runAsk } = askMutation

  const sendQuestion = useCallback(
    (question: string) => {
      if (!question.trim()) return
      const id = ++idRef.current
      setHistory((prev) => [...prev, { id, question }])
      setQuestionInput('')
      runAsk({ id, question })
    },
    [runAsk],
  )

  const mic = useListener(lang, (transcript) => setQuestionInput(transcript))

  useEffect(() => {
    if (!askOpen) {
      lastSeedSentRef.current = null
      return
    }
    if (askSeed && lastSeedSentRef.current !== askSeed) {
      lastSeedSentRef.current = askSeed
      sendQuestion(askSeed)
    }
  }, [askOpen, askSeed, sendQuestion])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  if (!askOpen) return null
  const suggestions = suggestionsForUser(user)

  return (
    <aside className="no-print fixed right-0 top-0 z-40 flex h-full w-[480px] max-w-full flex-col border-l border-line bg-paper shadow-2xl">
      <div className="flex items-center justify-between border-b border-line bg-surface px-5 py-3">
        <div>
          <div className="text-[1.02rem] font-semibold">{t('ask.title')}</div>
          <div className="text-[0.74rem] text-muted">
            {meta?.llm.available ? t('ask.engineLLM', { m: meta.llm.model }) : t('ask.engineDet')} · {t('ask.checked')}
          </div>
        </div>
        <button className="btn btn-quiet !min-h-0 !p-1.5" onClick={() => setAskOpen(false)} aria-label={t('c.close')}>
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {history.length === 0 && (
          <div className="space-y-2">
            <p className="text-[0.88rem] text-ink-2">{t('ask.intro')}</p>
            {suggestions.map(([key, vars]) => (
              <button
                key={key}
                className="block w-full rounded-lg border border-line bg-surface p-3 text-left text-[0.9rem] hover:border-forest"
                onClick={() => sendQuestion(t(key, vars))}
              >
                {t(key, vars)}
              </button>
            ))}
          </div>
        )}
        {history.map((entry) => (
          <div key={entry.id} className="space-y-2">
            <div className="ml-12 rounded-lg bg-forest p-3 text-[0.92rem] text-surface">{entry.question}</div>
            {entry.result ? (
              <Answer result={entry.result} />
            ) : entry.error ? (
              <div className="text-[0.85rem] text-brick">{entry.error}</div>
            ) : (
              <div className="flex items-center gap-2 text-[0.85rem] text-ink-2">
                <span className="h-2 w-2 animate-pulse rounded-full bg-s2" /> {t('ask.running')}
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form
        className="flex gap-2 border-t border-line bg-surface p-3"
        onSubmit={(e) => {
          e.preventDefault()
          sendQuestion(questionInput)
        }}
      >
        <button
          type="button"
          className={clsx('btn', mic.listening ? 'btn-accent' : 'btn-quiet')}
          disabled={!mic.supported}
          onClick={() => (mic.listening ? mic.stop() : mic.start())}
          aria-label={mic.supported ? t('ask.mic') : t('ask.noMic')}
          title={mic.supported ? t('ask.mic') : t('ask.noMic')}
        >
          {mic.supported ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
        </button>
        <input
          className="field flex-1"
          value={questionInput}
          onChange={(e) => setQuestionInput(e.target.value)}
          placeholder={mic.listening ? t('ask.listening') : t('ask.placeholder')}
          aria-label={t('ask.placeholder')}
        />
        <button className="btn btn-primary" disabled={askMutation.isPending} aria-label={t('c.ask')}>
          <Send className="h-4 w-4" />
        </button>
      </form>
    </aside>
  )
}
