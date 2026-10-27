import clsx from 'clsx'
import {
  Accessibility, ArrowRight, BarChart3, BellRing, BookOpenCheck, CheckCircle2, ClipboardCheck, ClipboardList, Database,
  FileText, FlaskConical, GitCompareArrows, Home, MessageCircleQuestion, Presentation, School, SearchCheck, ShieldCheck,
  Stethoscope, Target, TrendingUp, UserRound, Users,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/Layout'
import { Card, Speak } from '../components/ui'
import { useApp } from '../state'

type RoleKey = 'state' | 'district' | 'block' | 'crc' | 'headmaster' | 'teacher'
type Feature = { k: string; name: string; icon: typeof Home; to?: (r: RoleKey) => string | null; ask?: boolean }

const OFFICER: RoleKey[] = ['state', 'district', 'block']
// Where each feature opens for each role (null = not part of that role's app).
const at = (path: string, roles: RoleKey[]) => (r: RoleKey) => (roles.includes(r) ? path : null)

export default function Guide() {
  const { t, user, ask } = useApp()
  const nav = useNavigate()
  if (!user) return null
  const role: RoleKey = user.role === 'headmaster' ? (user.teacher ? 'teacher' : 'headmaster') : user.crc ? 'crc' : user.role
  // Menu names, so the guide always uses the same words as the menu in every language.
  // Page names are quoted so they stand out inside a sentence; button labels are already quoted in the text.
  const q = (k: string) => `“${t(k)}”`
  const names = {
    home: q('nav.home'), why: q('nav.why'), block: q('nav.block'), peers: q('nav.peers'), radar: q('nav.radar'),
    visits: q('nav.visits'), actions: q('nav.actions'), review: q('nav.review'), brief: q('nav.brief'), data: q('nav.data'),
    mySchool: q('nav.mySchool'), instinct: q('home.instinct'), ask: q('c.askAI'), reportCard: q('g.n.reportCard'),
    started: t('my.started'), done: t('my.done'), listen: t('c.listen'),
  }
  const g = (k: string) => t(k, names)
  const home = role === 'crc' ? '/overview' : '/'

  const groups: { title: string; items: Feature[] }[] = [
    { title: t('nav.group.understand'), items: [
      { k: 'home', name: t('nav.home'), icon: Home, to: (r) => (OFFICER.includes(r) || r === 'crc' ? home : null) },
      { k: 'early', name: t('g.n.early'), icon: BellRing, to: (r) => (OFFICER.includes(r) || r === 'crc' ? home : null) },
      { k: 'why', name: t('nav.why'), icon: Stethoscope, to: at('/why', [...OFFICER, 'crc']) },
      { k: 'block', name: t('nav.block'), icon: BarChart3, to: at('/block', OFFICER) },
      { k: 'peers', name: t('nav.peers'), icon: GitCompareArrows, to: at('/peers', OFFICER) },
    ] },
    { title: t('nav.group.act'), items: [
      { k: 'radar', name: t('nav.radar'), icon: SearchCheck, to: at('/radar', [...OFFICER, 'crc']) },
      { k: 'visits', name: t('nav.visits'), icon: ClipboardCheck, to: (r) => (r === 'crc' ? '/' : OFFICER.includes(r) ? '/visits' : null) },
      { k: 'actions', name: t('nav.actions'), icon: ClipboardList, to: () => '/actions' },
      { k: 'review', name: t('nav.review'), icon: Presentation, to: at('/review', ['state', 'district']) },
      { k: 'brief', name: t('nav.brief'), icon: FileText, to: at('/brief', OFFICER) },
    ] },
    { title: t('g.group.school'), items: [
      { k: 'mySchool', name: t('nav.mySchool'), icon: School, to: at('/', ['headmaster', 'teacher']) },
      { k: 'reportCard', name: t('g.n.reportCard'), icon: Users, to: (r) => (['headmaster', 'teacher'].includes(r) && user.scope ? `/report-card/${user.scope}` : null) },
    ] },
    { title: t('nav.group.data'), items: [
      { k: 'data', name: t('nav.data'), icon: Database, to: at('/data', OFFICER) },
      { k: 'lab', name: t('nav.lab'), icon: FlaskConical, to: at('/lab', ['state', 'district']) },
      { k: 'about', name: t('nav.about'), icon: BookOpenCheck, to: () => '/about' },
    ] },
    { title: t('g.group.everywhere'), items: [
      { k: 'ask', name: t('c.askAI'), icon: MessageCircleQuestion, ask: true },
      { k: 'access', name: t('g.n.access'), icon: Accessibility },
    ] },
  ]
  const journey = [
    { icon: Database, k: 'g.j1' }, { icon: Stethoscope, k: 'g.j2' }, { icon: Target, k: 'g.j3' },
    { icon: ClipboardList, k: 'g.j4' }, { icon: CheckCircle2, k: 'g.j5' }, { icon: TrendingUp, k: 'g.j6' },
  ]
  const roles: RoleKey[] = ['district', 'block', 'crc', 'headmaster', 'teacher', 'state']
  const RoleCard = ({ r, mine }: { r: RoleKey; mine?: boolean }) => (
    <div className={clsx('rounded-lg border p-4', mine ? 'border-forest bg-surface' : 'border-line bg-sunk')}>
      <div className="mb-2 flex items-center gap-2 font-semibold">
        <UserRound className="h-4 w-4 text-forest" /> {t(`g.r.${r}`)}
        {mine && <span className="tag !py-0 !text-forest">{t('g.you')}</span>}
      </div>
      <ol className={clsx('space-y-1.5', mine ? 'text-[0.98rem]' : 'text-[0.86rem] text-ink-2')}>
        {g(`g.r.${r}.steps`).split('|').map((s, i) => (
          <li key={i} className="flex gap-2"><span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-forest text-[0.7rem] font-bold text-surface">{i + 1}</span>{s}</li>
        ))}
      </ol>
    </div>
  )

  return (
    <div className="mx-auto max-w-[1100px] space-y-6">
      <PageHeader eyebrow={t('g.eyebrow')} title={t('g.title')} sub={t('g.sub')}
        right={<Speak text={[t('g.title'), t('g.what'), t('g.forWhom'), g(`g.r.${role}.steps`).replace(/\|/g, '. ')].join(' ')} />} />

      <Card title={t('g.oneMin')}>
        <p className="text-[1.02rem] leading-relaxed">{t('g.what')}</p>
        <p className="mt-2 text-[0.95rem] text-ink-2">{t('g.forWhom')}</p>
        <ol className="mt-5 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {journey.map((j, i) => (
            <li key={j.k} className="rounded-lg bg-sunk p-3">
              <div className="flex items-center gap-2 text-[0.95rem] font-semibold text-forest">
                <span className="tabnum text-[0.78rem] text-muted">{i + 1}</span><j.icon className="h-4 w-4" />{t(j.k)}
              </div>
              <div className="mt-1 text-[0.84rem] text-ink-2">{t(`${j.k}t`)}</div>
            </li>
          ))}
        </ol>
      </Card>

      <Card title={t('g.startTitle')} sub={t('g.startSub')}>
        <RoleCard r={role} mine />
        <div className="eyebrow mb-2 mt-5">{t('g.otherRoles')}</div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">{roles.filter((r) => r !== role).map((r) => <RoleCard key={r} r={r} />)}</div>
      </Card>

      <Card title={t('g.problemTitle')}>
        <ul className="divide-y divide-line">
          {[1, 2, 3, 4].map((i) => (
            <li key={i} className="grid gap-2 py-3 md:grid-cols-2 md:gap-6">
              <div><div className="eyebrow mb-0.5 !text-brick">{t('g.problem')}</div><p className="text-[0.95rem]">{g(`g.p${i}`)}</p></div>
              <div><div className="eyebrow mb-0.5 !text-forest">{t('g.answer')}</div><p className="text-[0.95rem]">{g(`g.a${i}`)}</p></div>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={t('g.featTitle')} sub={t('g.featSub')}>
        <div className="space-y-6">
          {groups.map((grp) => (
            <section key={grp.title}>
              <h3 className="eyebrow mb-2">{grp.title}</h3>
              <ul className="grid gap-3 md:grid-cols-2">
                {grp.items.map((f) => {
                  const to = f.to?.(role) ?? null
                  return (
                    <li key={f.k} className="flex flex-col rounded-lg border border-line bg-surface p-4">
                      <div className="flex items-center gap-2 text-[1rem] font-semibold"><f.icon className="h-[18px] w-[18px] text-forest" />{f.name}</div>
                      <dl className="mt-2 flex-1 space-y-1.5 text-[0.9rem]">
                        <div><dt className="inline font-semibold">{t('g.whatL')}: </dt><dd className="inline text-ink-2">{g(`g.f.${f.k}.what`)}</dd></div>
                        <div><dt className="inline font-semibold">{t('g.whyL')}: </dt><dd className="inline text-ink-2">{g(`g.f.${f.k}.why`)}</dd></div>
                      </dl>
                      {(to || f.ask) && (
                        <button className="btn btn-quiet mt-3 self-start" onClick={() => (f.ask ? ask() : nav(to!))}>
                          {t('g.open')} <ArrowRight className="h-4 w-4" />
                        </button>
                      )}
                    </li>
                  )
                })}
              </ul>
            </section>
          ))}
        </div>
      </Card>

      <Card title={t('g.trustTitle')}>
        <ul className="grid gap-3 md:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <li key={i} className="flex gap-2.5 text-[0.95rem]"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-forest" />{t(`g.t${i}`)}</li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
