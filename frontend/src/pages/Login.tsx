import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowRight, Building2, Check, Landmark, MapPin, School, UserRound } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import { LangSwitch, Mark } from '../components/Layout'
import { ErrorBox } from '../components/ui'
import { LANGS } from '../i18n'
import { useApp } from '../state'
import type { User } from '../types'

const ICON = { state: Landmark, district: Building2, block: MapPin, headmaster: School }

function LanguageFirst() {
  const { setLang, lang } = useApp()
  return (
    <div className="grid min-h-full place-items-center bg-paper px-4 py-8 lg:px-6 lg:py-12">
      <div className="w-full max-w-3xl">
        <div className="mb-8 flex items-center gap-3">
          <Mark size={44} />
          <div className="text-[1.5rem] font-bold text-forest">ShikshaPulse</div>
        </div>
        <h1 className="text-[1.5rem] font-bold leading-tight lg:text-[1.9rem]">
          अपनी भाषा चुनें · Choose your language
        </h1>
        <p className="mt-1 text-ink-2">மொழியைத் தேர்ந்தெடுக்கவும் · భాషను ఎంచుకోండి · ভাষা বেছে নিন · भाषा निवडा</p>
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {LANGS.map((l) => (
            <button
              key={l.code}
              onClick={() => setLang(l.code)}
              lang={l.code}
              className={clsx(
                'panel flex flex-col items-start gap-1 p-5 text-left transition hover:border-forest',
                lang === l.code && '!border-forest',
              )}
            >
              <span className="text-[1.6rem] font-semibold leading-none">{l.native}</span>
              <span className="text-[0.85rem] text-ink-2">
                {l.sample} · {l.english}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function Login() {
  const { login, t, langChosen } = useApp()
  const [err, setErr] = useState<unknown>(null)
  const personas = useQuery({ queryKey: ['personas'], queryFn: () => api.get<User[]>('/personas') })
  if (!langChosen) return <LanguageFirst />
  const flow = t('login.flow').split(',')
  return (
    <div className="min-h-full bg-paper">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-6 lg:grid-cols-[1.1fr_1fr] lg:gap-10 lg:px-6 lg:py-10">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Mark size={44} />
              <div className="text-[1.5rem] font-bold text-forest">ShikshaPulse</div>
            </div>
            <LangSwitch />
          </div>
          <h1 className="mt-6 text-[1.6rem] font-bold leading-[1.2] tracking-tight lg:mt-10 lg:text-[2.1rem] lg:leading-[1.15]">
            {t('login.title')}
          </h1>
          <p className="mt-4 max-w-xl text-[1.05rem] leading-relaxed text-ink-2">{t('login.text')}</p>
          <ol className="mt-8 grid max-w-xl grid-cols-3 gap-2 sm:grid-cols-6">
            {flow.map((f, i) => (
              <li key={f} className="flex flex-col items-start">
                <span className="grid h-7 w-7 place-items-center rounded-full border-2 border-forest text-[0.8rem] font-bold text-forest">
                  {i + 1}
                </span>
                <span className="mt-1 text-[0.85rem] font-semibold leading-tight">{f}</span>
              </li>
            ))}
          </ol>
          <p className="mt-6 text-[0.82rem] text-muted lg:mt-10">
            {t('login.demo')} {t('app.translationNote')}
          </p>
        </div>
        <div className="min-w-0">
          <h2 className="eyebrow mb-3">{t('login.signin')}</h2>
          {err ? (
            <div className="mb-3">
              <ErrorBox error={err} />
            </div>
          ) : null}
          <div className="space-y-2.5">
            {personas.data?.map((p) => {
              const Icon = p.teacher ? UserRound : (ICON[p.role] ?? UserRound)
              return (
                <button
                  key={p.id}
                  onClick={() => login(p.id).catch(setErr)}
                  className="panel group flex w-full items-center gap-4 p-4 text-left transition hover:border-forest"
                >
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-forest-50 text-forest">
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[1.02rem] font-semibold">{p.name}</span>
                    <span className="block truncate text-[0.86rem] text-ink-2">{p.title}</span>
                    <span className="mt-0.5 block text-[0.76rem] text-muted">
                      {t(p.teacher ? 'role.teacher' : `role.${p.role}`)}
                    </span>
                  </span>
                  <ArrowRight className="h-5 w-5 text-muted transition group-hover:translate-x-0.5 group-hover:text-forest" />
                </button>
              )
            })}
            {personas.isLoading && <div className="text-ink-2">{t('c.loading')}</div>}
            {personas.isError && <ErrorBox error={personas.error} />}
          </div>
          <div className="mt-4 flex items-center gap-2 text-[0.8rem] text-muted">
            <Check className="h-4 w-4 text-s1" /> {t('app.synthetic')}
          </div>
        </div>
      </div>
    </div>
  )
}
