import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Database, KeyRound, Languages, Lock, ShieldCheck, XCircle } from 'lucide-react'
import { api } from '../api'
import { PageHeader } from '../components/Layout'
import { Card, Spinner } from '../components/ui'
import { useApp } from '../state'

type Report = {
  generated_at: string
  checks: { scenario: string; check: string; value: unknown; target: string; passed: boolean }[]
}
type ModelCard = { r2_heldout: number; mae_heldout: number; n: number }
type Sources = {
  adapters: { key: string; available: boolean; active: boolean; requirements: Record<string, string> }[]
}

export default function About() {
  const { meta, t } = useApp()
  const rep = useQuery({ queryKey: ['eval'], queryFn: () => api.get<Report>('/eval/report'), retry: false })
  const mc = useQuery({ queryKey: ['model'], queryFn: () => api.get<ModelCard>('/expected/model') })
  const src = useQuery({ queryKey: ['sources'], queryFn: () => api.get<Sources>('/ingest/sources') })
  const list = (k: string) => (
    <ul className="reasons">
      {t(k)
        .split('|')
        .map((s) => (
          <li key={s} className="!text-[0.9rem]">
            {s}
          </li>
        ))}
    </ul>
  )
  return (
    <div className="space-y-5">
      <PageHeader title={t('about.title')} sub={t('about.sub')} />
      <div className="grid gap-5 lg:grid-cols-[1.7fr_1fr]">
        <Card
          title={t('about.eval')}
          sub={
            rep.data
              ? t('about.evalSub', {
                  p: rep.data.checks.filter((c) => c.passed).length,
                  n: rep.data.checks.length,
                  d: rep.data.generated_at,
                })
              : 'python -m eval'
          }
          pad={false}
        >
          {rep.isLoading ? (
            <Spinner />
          ) : rep.isError ? (
            <div className="px-5 pb-5 text-muted">—</div>
          ) : (
            <div className="max-h-[520px] overflow-y-auto px-5 pb-4">
              <table className="w-full text-[0.84rem]">
                <thead className="sticky top-0 bg-surface text-left text-[0.74rem] text-muted">
                  <tr>
                    <th className="py-1.5 font-medium">{t('about.th.scenario')}</th>
                    <th className="font-medium">{t('about.th.check')}</th>
                    <th className="text-right font-medium">{t('about.th.value')}</th>
                    <th className="text-right font-medium">{t('about.th.target')}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rep.data!.checks.map((c, i) => (
                    <tr key={i} className="border-t border-line">
                      <td className="py-1.5 pr-2">{c.scenario}</td>
                      <td className="pr-2">{c.check}</td>
                      <td className="text-right tabnum">{JSON.stringify(c.value)}</td>
                      <td className="text-right">{c.target}</td>
                      <td className="pl-2">
                        {c.passed ? (
                          <CheckCircle2 className="h-4 w-4 text-good" aria-label="pass" />
                        ) : (
                          <XCircle className="h-4 w-4 text-brick" aria-label="fail" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <div className="space-y-5">
          <Card
            title={
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-good" />
                {t('about.guard')}
              </span>
            }
          >
            {list('about.guardList')}
            <div className="mt-3 text-[0.84rem]">
              {t('about.engine', {
                m: meta?.llm.available ? `${meta.llm.provider} · ${meta.llm.model}` : t('about.noLLM'),
              })}
            </div>
          </Card>
          {mc.data && (
            <Card title={t('about.model')}>
              <p className="text-[0.9rem] text-ink-2">
                {t('about.modelLine', { r2: mc.data.r2_heldout, mae: mc.data.mae_heldout, n: mc.data.n })}
              </p>
            </Card>
          )}
          <Card
            title={
              <span className="flex items-center gap-1.5">
                <Languages className="h-4 w-4 text-forest" />
                {t('about.access')}
              </span>
            }
          >
            {list('about.accessList')}
            <p className="mt-2 text-[0.78rem] text-muted">{t('app.translationNote')}</p>
          </Card>
        </div>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card
          title={
            <span className="flex items-center gap-1.5">
              <Database className="h-4 w-4" />
              {t('about.sources')}
            </span>
          }
          sub={t('about.sourcesSub')}
        >
          <div className="space-y-2">
            {src.data?.adapters.map((a) => (
              <div key={a.key} className="panel-sunk p-3 text-[0.82rem]">
                <div className="flex items-center gap-2 text-[0.92rem] font-semibold">
                  {a.available ? (
                    <CheckCircle2 className="h-4 w-4 text-good" />
                  ) : (
                    <Lock className="h-4 w-4 text-muted" />
                  )}
                  {t(`src.${a.key}`)}
                </div>
                {Object.entries(a.requirements).map(([k, v]) => (
                  <div key={k} className="mt-0.5">
                    <span className="text-muted">{k.replace('_', ' ')}:</span> {v}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Card>
        <Card
          title={
            <span className="flex items-center gap-1.5">
              <KeyRound className="h-4 w-4" />
              {t('about.tiers')}
            </span>
          }
        >
          {list('about.tierList')}
          <div className="rule my-4" />
          {list('about.controlList')}
        </Card>
      </div>
    </div>
  )
}
