import clsx from 'clsx'
import {
  BarChart3, BookOpenCheck, ClipboardCheck, ClipboardList, Presentation, Database, FileText, FlaskConical, GitCompareArrows, Home, Languages,
  LifeBuoy, LogOut, Menu, MessageCircleQuestion, School, SearchCheck, Stethoscope, X,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { LANGS, type Lang } from '../i18n'
import { useApp, type Unit } from '../state'
import { AskPanel } from './AskPanel'
import { InfoTip } from './ui'

export function Mark({ size = 36 }: { size?: number }) {
  // Slate with a rising line: learning moving upward.
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <rect x="1" y="1" width="38" height="38" rx="9" fill="#1e4d36" />
      <rect x="7" y="9" width="26" height="18" rx="2" fill="none" stroke="#f4efe5" strokeOpacity=".55" strokeWidth="1.6" />
      <path d="M10 23 L16 18 L21 21 L30 12" fill="none" stroke="#dd8f22" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 31h12" stroke="#f4efe5" strokeOpacity=".55" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

type NavItem = { to: string; key: string; icon: typeof Home; roles?: string[] }
const GROUPS: { key: string; items: NavItem[] }[] = [
  { key: 'nav.group.understand', items: [
    { to: '/', key: 'nav.home', icon: Home },
    { to: '/why', key: 'nav.why', icon: Stethoscope },
    { to: '/block', key: 'nav.block', icon: BarChart3 },
    { to: '/peers', key: 'nav.peers', icon: GitCompareArrows },
  ] },
  { key: 'nav.group.act', items: [
    { to: '/radar', key: 'nav.radar', icon: SearchCheck },
    { to: '/visits', key: 'nav.visits', icon: ClipboardCheck },
    { to: '/actions', key: 'nav.actions', icon: ClipboardList },
    { to: '/review', key: 'nav.review', icon: Presentation, roles: ['state', 'district'] },
    { to: '/brief', key: 'nav.brief', icon: FileText },
  ] },
  { key: 'nav.group.data', items: [
    { to: '/data', key: 'nav.data', icon: Database },
    { to: '/lab', key: 'nav.lab', icon: FlaskConical, roles: ['state', 'district'] },
    { to: '/about', key: 'nav.about', icon: BookOpenCheck },
    { to: '/guide', key: 'nav.guide', icon: LifeBuoy },
  ] },
]
// Cluster coordinators start on school visits; the overview stays one tap away.
const CRC_GROUPS: { key: string; items: NavItem[] }[] = [
  { key: 'nav.group.act', items: [
    { to: '/', key: 'nav.visits', icon: ClipboardCheck },
    { to: '/actions', key: 'nav.actions', icon: ClipboardList },
  ] },
  { key: 'nav.group.understand', items: [
    { to: '/overview', key: 'nav.home', icon: Home },
    { to: '/why', key: 'nav.why', icon: Stethoscope },
    { to: '/radar', key: 'nav.radar', icon: SearchCheck },
  ] },
  { key: 'nav.group.data', items: [{ to: '/about', key: 'nav.about', icon: BookOpenCheck }, { to: '/guide', key: 'nav.guide', icon: LifeBuoy }] },
]
const SCHOOL_NAV: NavItem[] = [
  { to: '/', key: 'nav.mySchool', icon: School },
  { to: '/actions', key: 'nav.actions', icon: ClipboardList },
  { to: '/about', key: 'nav.about', icon: BookOpenCheck },
  { to: '/guide', key: 'nav.guide', icon: LifeBuoy },
]

export function UnitPicker({ blocksOnly = false, block }: { blocksOnly?: boolean; block?: string | null }) {
  const { meta, unit, setUnit, t } = useApp()
  if (!meta?.tree) return null
  const value = block ? `block:${block}` : `${unit.unit_type}:${unit.unit ?? ''}`
  return (
    <label className="flex items-center gap-2">
      <span className="sr-only">{t('c.selectUnit')}</span>
      <select className="field min-w-56" value={value} aria-label={t('c.selectUnit')}
        onChange={(e) => { const [ty, u] = e.target.value.split(':'); setUnit({ unit_type: ty as Unit['unit_type'], unit: u || null }) }}>
        {!blocksOnly && <option value="state:">{t('c.wholeState')}</option>}
        {Object.entries(meta.tree).map(([d, blocks]) => (
          <optgroup key={d} label={t('c.districtLabel', { d })}>
            {!blocksOnly && <option value={`district:${d}`}>{t('c.districtLabel', { d })}</option>}
            {blocks.map((b) => <option key={b} value={`block:${b}`}>{'  '}{t('c.blockLabel', { b })}</option>)}
          </optgroup>
        ))}
      </select>
    </label>
  )
}

export function LangSwitch() {
  const { lang, setLang, t } = useApp()
  return (
    <label className="flex items-center gap-1.5">
      <Languages className="h-4 w-4 text-ink-2" aria-hidden />
      <span className="sr-only">{t('lang.choose')}</span>
      <select className="field !min-h-9 !py-1" value={lang} onChange={(e) => setLang(e.target.value as Lang)} aria-label={t('lang.choose')}>
        {LANGS.map((l) => <option key={l.code} value={l.code}>{l.native}</option>)}
      </select>
    </label>
  )
}

function TextSize() {
  const { textSize, setTextSize, t } = useApp()
  return (
    <div className="seg" role="group" aria-label={t('c.textSize')} title={t('c.textSize')}>
      {['A', 'A+', 'A++'].map((l, i) => (
        <button key={l} aria-pressed={textSize === i} onClick={() => setTextSize(i)} style={{ fontSize: `${0.78 + i * 0.1}rem` }}>{l}</button>
      ))}
    </div>
  )
}

/** True on laptop/desktop widths (Tailwind lg). Phones/tablets get the compact header instead. */
function useIsDesktop() {
  const q = '(min-width: 1024px)'
  const [desk, setDesk] = useState(() => typeof window === 'undefined' || window.matchMedia(q).matches)
  useEffect(() => {
    const m = window.matchMedia(q)
    const on = () => setDesk(m.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [])
  return desk
}

/** One-time note for first-time visitors (judges, new officers): where to learn what everything is. */
function GuideNudge() {
  const { t } = useApp()
  const loc = useLocation()
  const [seen, setSeen] = useState(() => localStorage.getItem('sp_guide_seen') === '1')
  if (seen || loc.pathname === '/guide') return null
  const close = () => { localStorage.setItem('sp_guide_seen', '1'); setSeen(true) }
  return (
    <div className="no-print mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-forest/30 bg-surface px-4 py-2.5 text-[0.92rem]">
      <LifeBuoy className="h-4 w-4 text-forest" /> {t('g.nudge')}
      <NavLink to="/guide" onClick={close} className="font-semibold text-forest hover:underline">{t('g.nudgeOpen')}</NavLink>
      <button className="ml-auto text-muted hover:text-ink" onClick={close} aria-label={t('c.close')}><X className="h-4 w-4" /></button>
    </div>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  const { user, meta, logout, ask, askOpen, t } = useApp()
  // Phones/tablets (< lg): the sidebar is a slide-in menu. Desktop (lg+) is unchanged.
  const [menuOpen, setMenuOpen] = useState(false)
  const isDesktop = useIsDesktop()
  const loc = useLocation()
  useEffect(() => { setMenuOpen(false) }, [loc.pathname])
  if (!user) return null
  const schoolView = user.role === 'headmaster'
  const navLink = (n: NavItem) => (
    <NavLink key={n.to} to={n.to} end={n.to === '/'}
      className={({ isActive }) => clsx('flex items-center gap-3 rounded-md px-3 py-2 text-[0.92rem] font-medium transition',
        isActive ? 'bg-paper text-forest' : 'text-[#e9e3d6] hover:bg-white/10')}>
      <n.icon className="h-[18px] w-[18px] shrink-0" /> <span className="leading-tight">{t(n.key)}</span>
    </NavLink>
  )
  return (
    <div className="flex h-full">
      {menuOpen && <div className="no-print fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={() => setMenuOpen(false)} aria-hidden />}
      <aside className={clsx('no-print fixed inset-y-0 left-0 z-50 flex w-64 shrink-0 flex-col bg-forest text-[#f4efe5] transition-transform lg:static lg:z-auto lg:translate-x-0',
        menuOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full')} aria-label={t('c.menu')}>
        <div className="flex items-center gap-3 px-5 pb-5 pt-6">
          <Mark />
          <div>
            <div className="text-[1.08rem] font-bold leading-tight tracking-tight">ShikshaPulse</div>
            <div className="text-[0.74rem] text-[#cfd9cf]">{t('app.tagline')}</div>
          </div>
          <button className="ml-auto rounded-md p-1.5 text-[#e9e3d6] hover:bg-white/10 lg:hidden" onClick={() => setMenuOpen(false)} aria-label={t('c.close')}><X className="h-5 w-5" /></button>
        </div>
        <nav className="flex-1 space-y-5 overflow-y-auto px-3">
          {schoolView ? <div className="space-y-0.5">{SCHOOL_NAV.map(navLink)}</div> : (user.crc ? CRC_GROUPS : GROUPS).map((g) => (
            <div key={g.key}>
              <div className="mb-1 px-3 text-[0.68rem] font-semibold uppercase tracking-[.1em] text-[#a9bcae]">{t(g.key)}</div>
              <div className="space-y-0.5">{g.items.filter((n) => !n.roles || n.roles.includes(user.role)).map(navLink)}</div>
            </div>
          ))}
        </nav>
        <div className="m-3 rounded-lg bg-white/[.07] p-3 text-[0.82rem]">
          <div className="font-semibold">{user.name}</div>
          <div className="text-[#cfd9cf]">{user.title}</div>
          <button className="mt-2 inline-flex items-center gap-1 font-semibold text-s2 hover:underline" onClick={logout}><LogOut className="h-3.5 w-3.5" /> {t('c.switch')}</button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile header: menu, name, guide and ask on top; language and text size below; demo-data label always visible */}
        {!isDesktop && <div className="no-print border-b border-line bg-surface px-3 py-2 lg:hidden">
          <div className="flex items-center gap-2">
            <button className="btn btn-quiet !min-h-10 !px-2.5" onClick={() => setMenuOpen(true)} aria-label={t('c.menu')} aria-expanded={menuOpen}><Menu className="h-5 w-5" /></button>
            <span className="text-[1rem] font-bold tracking-tight text-forest">ShikshaPulse</span>
            <div className="ml-auto flex items-center gap-1.5">
              <NavLink to="/guide" className="btn btn-quiet !min-h-10 !px-2.5" aria-label={t('nav.guide')}><LifeBuoy className="h-5 w-5" /></NavLink>
              {!askOpen && <button className="btn btn-accent !min-h-10 !px-3" onClick={() => ask()} aria-label={t('c.askAI')}><MessageCircleQuestion className="h-5 w-5" /></button>}
            </div>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <LangSwitch />
            <TextSize />
            <InfoTip text={t('app.translationNote')} />
          </div>
          {meta?.synthetic && (
            <div className="mt-2 inline-flex items-start gap-1.5 rounded-md bg-mustard-50 px-2 py-1 text-[0.74rem] font-semibold leading-snug text-mustard">
              <FlaskConical className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {t('app.synthetic')}
            </div>
          )}
        </div>}
        <div className="no-print hidden flex-wrap items-center gap-3 border-b border-line bg-surface px-6 py-2.5 lg:flex">
          {meta?.synthetic && (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-mustard-50 px-2.5 py-1 text-[0.78rem] font-semibold text-mustard">
              <FlaskConical className="h-3.5 w-3.5" /> {t('app.synthetic')}
            </span>
          )}
          <div className="ml-auto flex items-center gap-3">
            <LangSwitch />
            <TextSize />
            <InfoTip text={t('app.translationNote')} />
            <NavLink to="/guide" className="btn btn-quiet"><LifeBuoy className="h-4 w-4" /> {t('nav.guide')}</NavLink>
            {!askOpen && <button className="btn btn-accent" onClick={() => ask()}><MessageCircleQuestion className="h-4 w-4" /> {t('c.askAI')}</button>}
          </div>
        </div>
        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[1380px] px-3 py-4 sm:px-4 lg:px-6 lg:py-6"><GuideNudge />{children}</div>
        </main>
      </div>
      <AskPanel />
    </div>
  )
}

export function PageHeader({ title, sub, right, eyebrow }: { title: string; sub?: ReactNode; right?: ReactNode; eyebrow?: string }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
        <h1 className="h-page">{title}</h1>
        {sub && <p className="mt-1 text-[0.95rem] text-ink-2">{sub}</p>}
      </div>
      {right && <div className="no-print flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  )
}
